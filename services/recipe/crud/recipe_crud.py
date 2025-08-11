"""
레시피/재료/별점 DB 접근(CRUD) 함수
- 모든 recipe_url 생성은 get_recipe_url 함수로 일원화
- 중복 dict 변환 등 최소화
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional, Dict, Tuple
import pandas as pd
import copy

from services.recipe.models.recipe_model import Recipe, Material, RecipeRating, RecipeVector
from common.database.mariadb_service import get_maria_service_db

def get_recipe_url(recipe_id: int) -> str:
    """
    만개의 레시피 상세페이지 URL 동적 생성
    """
    return f"https://www.10000recipe.com/recipe/{recipe_id}"


async def get_recipe_detail(db: AsyncSession, recipe_id: int) -> Optional[Dict]:
    """
    레시피 상세정보(+재료 리스트, recipe_url 포함) 반환
    """
    stmt = select(Recipe).where(Recipe.recipe_id == recipe_id) # type: ignore
    recipe_row = await db.execute(stmt)
    recipe = recipe_row.scalar_one_or_none()
    if not recipe:
        return None

    mats_row = await db.execute(select(Material).where(Material.recipe_id == recipe_id)) # type: ignore
    materials = [m.__dict__ for m in mats_row.scalars().all()]
    recipe_url = get_recipe_url(recipe_id)
    result_dict = {**recipe.__dict__, "materials": materials, "recipe_url": recipe_url}
    return result_dict


async def recommend_recipes_by_ingredients(
    db: AsyncSession,
    ingredients: List[str],
    amounts: Optional[List[str]] = None,
    units: Optional[List[str]] = None,
    page: int = 1,
    size: int = 3
) -> Tuple[List[Dict], int]:
    """
    재료명, 분량, 단위 기반 레시피 추천 (matched_ingredient_count 포함)
    - 소진횟수 파라미터 없이 동작
    - 페이지네이션(page, size)과 전체 개수(total) 반환
    - 순차적 재고 소진 알고리즘 적용
    """
    # 공통: 기본 쿼리 (인기순)
    base_stmt = (
        select(Recipe)
        .join(Material, Recipe.recipe_id == Material.recipe_id) # type: ignore
        .where(Material.material_name.in_(ingredients))
        .group_by(Recipe.recipe_id)
        .order_by(desc(Recipe.scrap_count))
    )
    offset = (page - 1) * size

    # 2. 레시피별 실제 들어간 재료(Material) 리스트 미리 조회(map 저장, 최적화)
    # (단, 단순 검색 모드에서는 DB 레벨 페이지네이션을 적용)

    # 3. 입력한 재료가 실제로 들어간 개수 반환 함수
    def get_matched_count(recipe_id):
        mats = recipe_materials_map[recipe_id]
        return len(set(ingredients) & {m.material_name for m in mats})

    # 4. amount/unit이 없으면 단순 재료 포함 레시피 반환(페이지네이션: DB 레벨 적용)
    if not amounts or not units:
        # total 계산: DISTINCT 레시피 개수
        total_stmt = (
            select(func.count(func.distinct(Recipe.recipe_id)))
            .join(Material, Recipe.recipe_id == Material.recipe_id)
            .where(Material.material_name.in_(ingredients))
        )
        total = (await db.execute(total_stmt)).scalar() or 0

        # 페이지네이션 적용하여 데이터 조회
        page_stmt = base_stmt.offset(offset).limit(size)
        page_result = await db.execute(page_stmt)
        page_recipes = page_result.scalars().unique().all()

        # 해당 페이지 레시피에 대해서만 재료 집계와 결과 구성
        recipe_materials_map = {}
        for recipe in page_recipes:
            mats_stmt = select(Material).where(Material.recipe_id == recipe.recipe_id) # type: ignore
            mats = (await db.execute(mats_stmt)).scalars().all()
            recipe_materials_map[recipe.recipe_id] = mats

        filtered = [
            {
                **r.__dict__,
                "recipe_url": get_recipe_url(r.recipe_id),
                "matched_ingredient_count": len(set(ingredients) & {m.material_name for m in recipe_materials_map.get(r.recipe_id, [])}),
            }
            for r in page_recipes
        ]
        return filtered, total

    # 5. amount/unit 모두 있으면, 순차적 재고 소진 알고리즘 적용
    # 5-1. 초기 재고 설정
    initial_ingredients = []
    for i in range(len(ingredients)):
        try:
            amount = float(amounts[i]) if amounts[i] else 0
        except (ValueError, TypeError):
            amount = 0
        initial_ingredients.append({
            'name': ingredients[i],
            'amount': amount,
            'unit': units[i] if units[i] else ''
        })

    # 5-2. 레시피 재료 맵을 알고리즘에 맞는 형태로 변환
    recipe_material_map = {}
    for recipe_id, materials in recipe_materials_map.items():
        recipe_material_map[recipe_id] = []
        for mat in materials:
            try:
                amt = float(mat.measure_amount) if mat.measure_amount else 0
            except (ValueError, TypeError):
                amt = 0
            recipe_material_map[recipe_id].append({
                'mat': mat.material_name,
                'amt': amt,
                'unit': mat.measure_unit if mat.measure_unit else ''
            })

    # 5-3. 레시피 정보를 DataFrame 형태로 변환
    recipe_df = []
    # 후보는 인기순 전체 후보를 사용 (알고리즘에서 조기중단)
    candidate_recipes = (await db.execute(base_stmt)).scalars().unique().all()
    for recipe in candidate_recipes:
        recipe_dict = {
            'RECIPE_ID': recipe.recipe_id,
            'COOKING_NAME': recipe.cooking_name,
            'SCRAP_COUNT': recipe.scrap_count,
            'RECIPE_URL': get_recipe_url(recipe.recipe_id),
            'MATCHED_INGREDIENT_COUNT': get_matched_count(recipe.recipe_id)
        }
        recipe_df.append(recipe_dict)
    
    # DataFrame으로 변환
    recipe_df = pd.DataFrame(recipe_df)

    # 5-4. 순차적 재고 소진 알고리즘 실행 (요청 페이지의 끝까지 생성하면 조기 중단)
    max_results_needed = page * size
    recommended, remaining_stock, early_stopped = recommend_sequentially_for_inventory(
        initial_ingredients,
        recipe_material_map,
        recipe_df,
        max_results=max_results_needed
    )

    # 5-5. 페이지네이션 적용
    start, end = (page-1)*size, (page-1)*size + size
    paginated_recommended = recommended[start:end]

    # 전체 개수: 조기중단이면 정확한 total 계산이 어려우므로 최소치 + has_more 힌트 반영
    if early_stopped:
        # 요청한 페이지 범위까지는 존재하며, 그 이후가 더 있을 가능성을 1 더해 표현
        approx_total = (page - 1) * size + len(paginated_recommended) + 1
        return paginated_recommended, approx_total
    else:
        return paginated_recommended, len(recommended)


def recommend_sequentially_for_inventory(initial_ingredients, recipe_material_map, recipe_df, max_results: Optional[int] = None):
    def _norm(u):
        return (u or "").strip().lower()

    recipe_df['RECIPE_ID'] = recipe_df['RECIPE_ID'].astype(int)

    remaining_stock = {
        ing['name']: {'amount': ing['amount'], 'unit': ing['unit']}
        for ing in initial_ingredients
    }

    recommended = []
    used_recipe_ids = set()

    early_stopped = False
    while True:
        current_ingredients = [k for k, v in remaining_stock.items() if v['amount'] > 1e-3]
        if not current_ingredients:
            break

        best_recipe = None
        best_usage = {}
        max_used = 0

        for rid, materials in recipe_material_map.items():
            rid = int(rid)
            if rid in used_recipe_ids:
                continue

            temp_stock = copy.deepcopy(remaining_stock)
            used_ingredients = {}

            for m in materials:
                mat = m['mat']
                req_amt = m['amt']
                req_unit = m['unit']

                if (
                    mat in temp_stock and
                    req_amt is not None and
                    temp_stock[mat]['amount'] > 1e-3 and
                    (
                        not temp_stock[mat].get('unit') or
                        not req_unit or
                        _norm(temp_stock[mat]['unit']) == _norm(req_unit)
                    )
                ):
                    used_amt = min(req_amt, temp_stock[mat]['amount'])
                    if used_amt > 1e-3:
                        temp_stock[mat]['amount'] -= used_amt
                        used_ingredients[mat] = {'amount': used_amt, 'unit': req_unit}

            if used_ingredients and len(used_ingredients) > max_used:
                best_recipe = rid
                best_usage = used_ingredients
                max_used = len(used_ingredients)

        if not best_recipe:
            break

        for mat, detail in best_usage.items():
            remaining_stock[mat]['amount'] -= detail['amount']

        row = recipe_df[recipe_df['RECIPE_ID'] == best_recipe]
        if row.empty:
            used_recipe_ids.add(best_recipe)
            continue

        recipe_info = recipe_df[recipe_df['RECIPE_ID'] == best_recipe].iloc[0].to_dict()
        # 프론트 렌더링 안전성을 위해 문자열 리스트로 변환
        recipe_info['used_ingredients'] = [
            f"{mat} {detail.get('amount', '')} {detail.get('unit', '')}".strip()
            for mat, detail in best_usage.items()
        ]
        recommended.append(recipe_info)
        used_recipe_ids.add(best_recipe)

        # 최대 결과 수에 도달하면 조기 중단
        if max_results is not None and len(recommended) >= max_results:
            early_stopped = True
            break

    return recommended, remaining_stock, early_stopped


async def search_recipes_by_keyword(
    db: AsyncSession,
    keyword: str,
    page: int = 1,
    size: int = 5,
    method: str = "recipe",
) -> Tuple[List[dict], int]:
    """
    레시피 검색 (페이지네이션)
    - method == 'recipe': COOKING_NAME 기반 부분일치 검색 + 벡터 유사도 보완
    - method == 'ingredient': 식재료명(쉼표 구분) 포함 레시피 검색(모든 재료 포함)
    """
    print(f"=== search_recipes_by_keyword 시작 ===")
    print(f"keyword: {keyword}, page: {page}, size: {size}, method: {method}")
    
    if method == "ingredient":
        # 쉼표로 분리된 재료 파싱
        ingredients = [i.strip() for i in keyword.split(",") if i.strip()]
        if not ingredients:
            return [], 0

        # 모든 입력 재료를 포함하는 레시피 추출
        from sqlalchemy import func as sa_func
        ids_stmt = (
            select(Material.recipe_id)
            .where(Material.material_name.in_(ingredients))
            .group_by(Material.recipe_id)
            .having(sa_func.count(sa_func.distinct(Material.material_name)) == len(ingredients))
        )
        ids_rows = await db.execute(ids_stmt)
        recipe_ids = [rid for (rid,) in ids_rows.all()]
        if not recipe_ids:
            return [], 0

        # 상세 정보 로드 (정렬은 스크랩수 기준)
        rec_stmt = (
            select(Recipe)
            .where(Recipe.recipe_id.in_(recipe_ids))
            .order_by(desc(Recipe.scrap_count))
        )
        rec_rows = await db.execute(rec_stmt)
        recipes = rec_rows.scalars().all()

        result_list = [{**r.__dict__, "recipe_url": get_recipe_url(r.recipe_id)} for r in recipes]
        total = len(result_list)
        start, end = (page-1)*size, (page-1)*size + size
        paginated = result_list[start:end]
        return paginated, total
    
    else:  # method == "recipe"
        # 1. MariaDB에서 COOKING_NAME 기반 정확 일치 우선 추천
        # 먼저 전체 개수를 확인
        total_cooking_name_stmt = (
            select(func.count(Recipe.recipe_id))
            .where(Recipe.cooking_name.contains(keyword))
        )
        total_cooking_name_result = await db.execute(total_cooking_name_stmt)
        total_cooking_name_count = total_cooking_name_result.scalar() or 0
        
        print(f"COOKING_NAME 일치 총 개수: {total_cooking_name_count}")
        print(f"요청된 size: {size}")
        
        # 2. 요청된 개수만큼 COOKING_NAME 일치 결과 가져오기
        cooking_name_stmt = (
            select(Recipe)
            .where(Recipe.cooking_name.contains(keyword))
            .order_by(desc(Recipe.scrap_count))
            .limit(size)
        )
        print(f"실행할 SQL 쿼리: {cooking_name_stmt}")
        
        cooking_name_result = await db.execute(cooking_name_stmt)
        cooking_name_matches = cooking_name_result.scalars().all()
        
        print(f"실제 반환된 COOKING_NAME 일치 개수: {len(cooking_name_matches)}")
        
        cooking_name_list = [
            {
                **r.__dict__,
                "recipe_url": get_recipe_url(r.recipe_id),
                "RANK_TYPE": 0  # 0은 'COOKING_NAME 정확 일치'를 의미
            }
            for r in cooking_name_matches
        ]
        
        cooking_name_k = len(cooking_name_list)
        seen_ids = {item["recipe_id"] for item in cooking_name_list}
        
        # 3. COOKING_NAME 일치가 부족한 경우 PostgreSQL에서 벡터 유사도 기반 보완 추천
        remaining_after_cooking = size - cooking_name_k
        
        # 3. PostgreSQL에서 벡터 유사도 기반 보완 추천 (여전히 부족한 경우)
        similar_list = []
        
        # 디버깅을 위한 간단한 로그
        print(f"COOKING_NAME 일치: {cooking_name_k}개, 요청: {size}개, 부족: {remaining_after_cooking}개")
        
        if remaining_after_cooking > 0:
            print("벡터 유사도 검색 실행 시작")
            
            try:
                # PostgreSQL 세션을 새로 생성하여 사용
                from common.database.postgres_recommend import SessionLocal
                async with SessionLocal() as postgres_session:
                    # PostgreSQL에서 벡터 데이터 조회 (seen_ids 제외)
                    print(f"seen_ids: {seen_ids}")
                    if seen_ids:
                        vec_stmt = (
                            select(RecipeVector.recipe_id, RecipeVector.vector_name)
                            .where(~RecipeVector.recipe_id.in_(seen_ids))
                        )
                    else:
                        vec_stmt = (
                            select(RecipeVector.recipe_id, RecipeVector.vector_name)
                        )
                    
                    print("PostgreSQL 벡터 데이터 조회 시작")
                    vec_result = await postgres_session.execute(vec_stmt)
                    vec_data = vec_result.all()
                    print(f"PostgreSQL에서 가져온 벡터 데이터 개수: {len(vec_data)}")
                    
                    if vec_data:
                        print("SentenceTransformer 모델 로딩 시작")
                        # SentenceTransformer 모델 로드
                        from services.recommend.recommend_service import get_model
                        model = await get_model()
                        query_vec = model.encode(keyword, normalize_embeddings=True)
                        print(f"쿼리 벡터 생성 완료, 차원: {len(query_vec)}")
                        
                        # 코사인 유사도 계산
                        similarities = []
                        print("코사인 유사도 계산 시작")
                        
                        for i, (rid, vector_data) in enumerate(vec_data):
                            if vector_data is None:
                                continue
                            
                            try:
                                # pgvector Vector 타입을 numpy 배열로 변환
                                import numpy as np
                                
                                # 디버깅: 벡터 데이터 타입과 내용 확인
                                if i < 3:  # 처음 3개만 출력
                                    print(f"레시피 {rid} 벡터 데이터 타입: {type(vector_data)}")
                                    print(f"레시피 {rid} 벡터 데이터 내용: {str(vector_data)[:100]}...")
                                
                                # pgvector Vector 객체의 경우 to_list() 메서드 사용
                                if hasattr(vector_data, 'to_list'):
                                    vector_array = np.array(vector_data.to_list())
                                else:
                                    # 문자열인 경우 파싱 (공백 또는 쉼표로 구분)
                                    vector_str = str(vector_data)
                                    if vector_str.startswith('[') and vector_str.endswith(']'):
                                        vector_str = vector_str[1:-1]
                                    
                                    # 공백과 쉼표 모두 처리
                                    if ',' in vector_str:
                                        # 쉼표로 구분된 경우
                                        vector_values = [float(x.strip()) for x in vector_str.split(',')]
                                    else:
                                        # 공백으로 구분된 경우 (새줄 문자도 제거)
                                        vector_str = vector_str.replace('\n', ' ').replace('\r', ' ')
                                        vector_values = [float(x.strip()) for x in vector_str.split() if x.strip()]
                                    
                                    vector_array = np.array(vector_values)
                                
                                # 코사인 유사도 계산
                                dot_product = np.dot(query_vec, vector_array)
                                norm_query = np.linalg.norm(query_vec)
                                norm_vector = np.linalg.norm(vector_array)
                                
                                if norm_query > 0 and norm_vector > 0:
                                    similarity = dot_product / (norm_query * norm_vector)
                                    similarities.append((rid, similarity))
                                    
                                    if i < 5:  # 처음 5개만 출력
                                        print(f"레시피 {rid}: 유사도 {similarity:.4f}")
                            except Exception as e:
                                if i < 5:  # 처음 5개만 출력
                                    print(f"레시피 {rid} 벡터 처리 실패: {e}")
                                continue
                        
                        print(f"계산된 유사도 개수: {len(similarities)}")
                        
                        # 유사도 높은 순으로 정렬하고 상위 remaining_after_cooking개 선택
                        if similarities:
                            similarities.sort(key=lambda x: x[1], reverse=True)
                            top_similar = similarities[:remaining_after_cooking]
                            print(f"상위 유사도 레시피 개수: {len(top_similar)}")
                            
                            # 선택된 유사 레시피들의 상세 정보를 MariaDB에서 조회
                            similar_ids = [rid for rid, _ in top_similar]
                            print(f"MariaDB에서 조회할 유사 레시피 ID들: {similar_ids}")
                            
                            if similar_ids:
                                similar_detail_stmt = (
                                    select(Recipe)
                                    .where(Recipe.recipe_id.in_(similar_ids))
                                )
                                similar_detail_result = await db.execute(similar_detail_stmt)
                                similar_recipes = similar_detail_result.scalars().all()
                                print(f"MariaDB에서 조회된 유사 레시피 개수: {len(similar_recipes)}")
                                
                                similar_list = [
                                    {
                                        **r.__dict__,
                                        "recipe_url": get_recipe_url(r.recipe_id),
                                        "RANK_TYPE": 1  # 1은 '벡터 유사도 기반 추천'을 의미
                                    }
                                    for r in similar_recipes
                                ]
                                print(f"최종 similar_list 개수: {len(similar_list)}")
                            else:
                                print("similar_ids가 비어있음")
                        else:
                            print("계산된 유사도가 없음")
                    else:
                        print("PostgreSQL에서 벡터 데이터를 가져오지 못함")
                    
            except Exception as e:
                # 벡터 검색 실패 시 로그만 남기고 계속 진행
                print(f"벡터 검색 중 오류 발생: {e}")
                import traceback
                traceback.print_exc()
                pass
        else:
            if remaining_after_cooking <= 0:
                print(f"벡터 검색 불필요: 부족한 개수가 {remaining_after_cooking}개")
        
        # 4. 2단계 결과를 우선순위 순서로 합치기
        final_list = cooking_name_list + similar_list
        
        print(f"최종 결과: COOKING_NAME 일치 {len(cooking_name_list)}개 + 유사도 기반 {len(similar_list)}개 = 총 {len(final_list)}개")
        
        if not final_list:
            return [], 0
        
        # 4. 페이지네이션 적용
        start, end = (page - 1) * size, (page - 1) * size + size
        paginated = final_list[start:end]
        
        print(f"페이지네이션: page={page}, size={size}, start={start}, end={end}")
        print(f"페이지네이션 후 최종 반환 개수: {len(paginated)}")
        
        # 5. 전체 개수 계산 (정확한 total은 어려우므로 근사값)
        total = (page - 1) * size + len(paginated)
        if len(final_list) > end:
            total += 1
        
        print(f"=== search_recipes_by_keyword 완료: 총 {len(paginated)}개 반환, total={total} ===")
        
        return paginated, total


async def get_recipe_rating(db: AsyncSession, recipe_id: int) -> float:
    """
    해당 레시피의 별점 평균값을 반환
    """
    stmt = (
        select(func.avg(RecipeRating.rating)).where(RecipeRating.recipe_id == recipe_id) # type: ignore
    )
    avg_rating = (await db.execute(stmt)).scalar()
    return float(avg_rating) if avg_rating is not None else 0.0


async def set_recipe_rating(db: AsyncSession, recipe_id: int, user_id: int, rating: int) -> int:
    """
    새로운 별점을 등록(0~5 int)하고 저장된 값을 반환
    """
    new_rating = RecipeRating(recipe_id=recipe_id, user_id=user_id, rating=rating)
    db.add(new_rating)
    await db.commit()
    return rating


###########################################################
# async def get_recipe_comments(
#         db: AsyncSession,
#         recipe_id: int,
#         page: int,
#         size: int
# ) -> Tuple[List[dict], int]:
#     """
#         주어진 레시피의 후기 목록(페이지네이션)과 총 개수를 반환
#     """
#     offset = (page - 1) * size
#     stmt = (
#         select(RecipeComment)
#         .where(RecipeComment.recipe_id == recipe_id) # type: ignore
#         .offset(offset)
#         .limit(size)
#     )
#     comments = (await db.execute(stmt)).scalars().all()
#     count_stmt = (
#         select(func.count()).where(RecipeComment.recipe_id == recipe_id) # type: ignore
#     )
#     total = (await db.execute(count_stmt)).scalar()
#     return [c.__dict__ for c in comments], total
#
# async def add_recipe_comment(
#         db: AsyncSession,
#         recipe_id: int,
#         user_id: int,
#         comment: str
# ) -> dict:
#     """
#         새로운 후기(코멘트)를 등록하고 저장된 내용을 반환
#     """
#     new_comment = RecipeComment(recipe_id=recipe_id, user_id=user_id, comment=comment)
#     db.add(new_comment)
#     await db.commit()
#     await db.refresh(new_comment)
#     return new_comment.__dict__
#
# # 소진횟수 포함
# async def recommend_recipes_by_ingredients(
#     db: AsyncSession,
#     ingredients: List[str],
#     amounts: Optional[List[str]] = None,
#     units: Optional[List[str]] = None,
#     consume_count: Optional[int] = None,
#     page: int = 1,
#     size: int = 5
# ) -> Tuple[List[Dict], int]:
#     """
#     - 페이지네이션(page, size)과 전체 개수(total) 반환
#     - matched_ingredient_count(입력 재료 중 실제로 들어간 개수) 포함
#     """
#
#     # 1. 입력 재료 중 하나 이상을 포함하는 레시피 후보 전체 추출(인기순)
#     stmt = (
#         select(Recipe)
#         .join(Material, Recipe.recipe_id == Material.recipe_id) # type: ignore
#         .where(Material.material_name.in_(ingredients))
#         .group_by(Recipe.recipe_id)
#         .order_by(desc(Recipe.scrap_count))
#     )
#     result = await db.execute(stmt)
#     candidate_recipes = result.scalars().all()
#     total = len(candidate_recipes)  # 전체 후보 개수
#
#     # 2. 레시피별 실제 들어간 재료(Material) 리스트 미리 조회(map 저장, 최적화)
#     recipe_materials_map = {}
#     for recipe in candidate_recipes:
#         mats_stmt = select(Material).where(Material.recipe_id == recipe.recipe_id) # type: ignore
#         mats = (await db.execute(mats_stmt)).scalars().all()
#         recipe_materials_map[recipe.recipe_id] = mats
#
#     # 3. 입력한 재료가 실제로 들어간 개수 반환 함수
#     def get_matched_count(recipe_id):
#         mats = recipe_materials_map[recipe_id]
#         return len(set(ingredients) & {m.material_name for m in mats})
#
#     # 4. case2: 소진조건 미입력 → 단순 재료 포함 레시피 반환
#     if not amounts or not units or not consume_count:
#         filtered = [
#             {
#                 **r.__dict__,
#                 "recipe_url": get_recipe_url(r.recipe_id),
#                 "matched_ingredient_count": get_matched_count(r.recipe_id),
#             }
#             for r in candidate_recipes
#         ]
#         # 페이지네이션
#         start, end = (page-1)*size, (page-1)*size + size
#         return filtered[start:end], total
#
#     # 5. case1: amounts, units, consume_count 모두 있을 때 소진조건 체크
#     usable_total = {
#         (ingredients[i], units[i]): float(amounts[i]) * consume_count
#         for i in range(len(ingredients))
#     }
#     filtered = []
#     for recipe in candidate_recipes:
#         mats = recipe_materials_map[recipe.recipe_id]
#         ok = True
#         for m in mats:
#             key = (m.material_name, m.measure_unit)
#             if key in usable_total:
#                 try:
#                     recipe_required = float(m.measure_amount) if m.measure_amount else 0
#                 except Exception:
#                     recipe_required = 0
#                 if recipe_required > usable_total[key]:
#                     ok = False
#                     break
#         if ok:
#             filtered.append({
#                 **recipe.__dict__,
#                 "recipe_url": get_recipe_url(recipe.recipe_id),
#                 "matched_ingredient_count": get_matched_count(recipe.recipe_id),
#             })
#         if len(filtered) >= (page * size):  # 성능 최적화: 필요한 개수만 필터링
#             break
#     # 페이지네이션
#     start, end = (page-1)*size, (page-1)*size + size
#     return filtered[start:end], len(filtered)