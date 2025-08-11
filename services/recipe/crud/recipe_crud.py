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
from common.logger import get_logger

# 로거 초기화
logger = get_logger("recipe_crud")

def get_recipe_url(recipe_id: int) -> str:
    """
    만개의 레시피 상세페이지 URL 동적 생성
    """
    return f"https://www.10000recipe.com/recipe/{recipe_id}"


async def get_recipe_detail(db: AsyncSession, recipe_id: int) -> Optional[Dict]:
    """
    레시피 상세정보(+재료 리스트, recipe_url 포함) 반환
    """
    logger.info(f"레시피 상세정보 조회 시작: recipe_id={recipe_id}")
    
    stmt = select(Recipe).where(Recipe.recipe_id == recipe_id) # type: ignore
    recipe_row = await db.execute(stmt)
    recipe = recipe_row.scalar_one_or_none()
    if not recipe:
        logger.warning(f"레시피를 찾을 수 없음: recipe_id={recipe_id}")
        return None

    mats_row = await db.execute(select(Material).where(Material.recipe_id == recipe_id)) # type: ignore
    materials = [m.__dict__ for m in mats_row.scalars().all()]
    recipe_url = get_recipe_url(recipe_id)
    result_dict = {**recipe.__dict__, "materials": materials, "recipe_url": recipe_url}
    
    logger.info(f"레시피 상세정보 조회 완료: recipe_id={recipe_id}, 재료 개수={len(materials)}")
    return result_dict


async def recommend_recipes_by_ingredients(
    db: AsyncSession,
    ingredients: List[str],
    amounts: Optional[List[float]] = None,
    units: Optional[List[str]] = None,
    page: int = 1,
    size: int = 10
) -> Tuple[List[Dict], int]:
    """
    재료명, 분량, 단위 기반 레시피 추천 (matched_ingredient_count 포함)
    - 소진횟수 파라미터 없이 동작
    - 페이지네이션(page, size)과 전체 개수(total) 반환
    - 순차적 재고 소진 알고리즘 적용 (amount/unit이 있는 경우)
    - 효율적인 DB 쿼리로 타임아웃 방지
    """
    logger.info(f"재료 기반 레시피 추천 시작: 재료={ingredients}, 페이지={page}, 크기={size}")
    
    # 기본 쿼리 (인기순)
    base_stmt = (
        select(Recipe)
        .join(Material, Recipe.recipe_id == Material.recipe_id) # type: ignore
        .where(Material.material_name.in_(ingredients))
        .group_by(Recipe.recipe_id)
        .order_by(desc(Recipe.scrap_count))
    )
    
    # 1. amount/unit이 없으면 단순 재료 포함 레시피 반환 (DB 레벨 페이지네이션)
    if not amounts or not units:
        logger.info("단순 재료 포함 레시피 추천 모드")
        
        # total 계산: DISTINCT 레시피 개수
        total_stmt = (
            select(func.count(func.distinct(Recipe.recipe_id)))
            .join(Material, Recipe.recipe_id == Material.recipe_id)
            .where(Material.material_name.in_(ingredients))
        )
        total = (await db.execute(total_stmt)).scalar() or 0
        logger.info(f"전체 레시피 개수: {total}")
        
        # 페이지네이션 적용하여 데이터 조회
        offset = (page - 1) * size
        page_stmt = base_stmt.offset(offset).limit(size)
        page_result = await db.execute(page_stmt)
        page_recipes = page_result.scalars().unique().all()
        logger.info(f"현재 페이지 레시피 개수: {len(page_recipes)}")
        
        # 해당 페이지 레시피에 대해서만 재료 집계와 결과 구성
        recipe_materials_map = {}
        for recipe in page_recipes:
            mats_stmt = select(Material).where(Material.recipe_id == recipe.recipe_id) # type: ignore
            mats = (await db.execute(mats_stmt)).scalars().all()
            recipe_materials_map[recipe.recipe_id] = mats
        
        filtered = []
        for r in page_recipes:
            matched_count = len(set(ingredients) & {m.material_name for m in recipe_materials_map.get(r.recipe_id, [])})
            
            # 사용된 재료 정보 구성
            used_ingredients = []
            for mat in recipe_materials_map.get(r.recipe_id, []):
                if mat.material_name in ingredients:
                    # measure_amount를 float로 변환
                    try:
                        measure_amount = float(mat.measure_amount) if mat.measure_amount is not None else None
                    except (ValueError, TypeError):
                        measure_amount = None
                    
                    used_ingredients.append({
                        "material_name": mat.material_name,
                        "measure_amount": measure_amount,
                        "measure_unit": mat.measure_unit
                    })
            
            recipe_dict = {
                "recipe_id": r.recipe_id,
                "recipe_title": r.recipe_title,
                "cooking_name": r.cooking_name,
                "scrap_count": r.scrap_count,
                "cooking_case_name": r.cooking_case_name,
                "cooking_category_name": r.cooking_category_name,
                "cooking_introduction": r.cooking_introduction,
                "number_of_serving": r.number_of_serving,
                "thumbnail_url": r.thumbnail_url,
                "recipe_url": get_recipe_url(r.recipe_id),
                "matched_ingredient_count": matched_count,
                "total_ingredients_count": len(recipe_materials_map.get(r.recipe_id, [])),  # 레시피 전체 재료 개수
                "used_ingredients": used_ingredients
            }
            filtered.append(recipe_dict)
            logger.info(f"레시피 {r.recipe_id} ({r.cooking_name}) 추가됨, matched_count: {matched_count}, used_ingredients: {len(used_ingredients)}개")
        return filtered, total
    
    # 2. amount/unit 모두 있으면, 순차적 재고 소진 알고리즘 적용
    logger.info("순차적 재고 소진 알고리즘 모드")
    
    # 2-1. 초기 재고 설정
    initial_ingredients = []
    for i in range(len(ingredients)):
        try:
            amount = float(amounts[i]) if amounts[i] is not None else 0
        except (ValueError, TypeError):
            amount = 0
        initial_ingredients.append({
            'name': ingredients[i],
            'amount': amount,
            'unit': units[i] if units[i] else ''
        })
    
    # 2-2. 전체 후보 레시피를 한 번에 조회 (페이지네이션을 위해)
    logger.info("전체 후보 레시피 조회 시작")
    candidate_recipes = (await db.execute(base_stmt)).scalars().unique().all()
    logger.info(f"전체 후보 레시피 개수: {len(candidate_recipes)}")
    
    # 2-3. 레시피별 재료 정보를 효율적으로 조회
    recipe_ids = [r.recipe_id for r in candidate_recipes]
    materials_stmt = (
        select(Material)
        .where(Material.recipe_id.in_(recipe_ids))
    )
    all_materials = (await db.execute(materials_stmt)).scalars().all()
    
    # 레시피별 재료 맵 구성
    recipe_material_map = {}
    for mat in all_materials:
        if mat.recipe_id not in recipe_material_map:
            recipe_material_map[mat.recipe_id] = []
        
        try:
            amt = float(mat.measure_amount) if mat.measure_amount is not None else 0
        except (ValueError, TypeError):
            amt = 0
        
        recipe_material_map[mat.recipe_id].append({
            'mat': mat.material_name,
            'amt': amt,
            'unit': mat.measure_unit if mat.measure_unit else ''
        })
    
    # 2-4. 레시피 정보를 DataFrame 형태로 변환
    recipe_df = []
    for recipe in candidate_recipes:
        recipe_dict = {
            'RECIPE_ID': recipe.recipe_id,
            'RECIPE_TITLE': recipe.recipe_title,
            'COOKING_NAME': recipe.cooking_name,
            'SCRAP_COUNT': recipe.scrap_count,
            'RECIPE_URL': get_recipe_url(recipe.recipe_id),
            'THUMBNAIL_URL': recipe.thumbnail_url,
            'COOKING_CASE_NAME': recipe.cooking_case_name,
            'COOKING_CATEGORY_NAME': recipe.cooking_category_name,
            'COOKING_INTRODUCTION': recipe.cooking_introduction,
            'NUMBER_OF_SERVING': recipe.number_of_serving
        }
        recipe_df.append(recipe_dict)
    
    # DataFrame으로 변환 (measure_amount가 None인 경우 처리)
    try:
        recipe_df = pd.DataFrame(recipe_df)
        logger.info(f"DataFrame 생성 완료: {len(recipe_df)}행")
    except Exception as e:
        logger.error(f"DataFrame 생성 실패: {e}")
        # 에러 발생 시 빈 DataFrame 반환
        return [], remaining_stock, False
    
    # 2-5. 순차적 재고 소진 알고리즘 실행 (요청 페이지의 끝까지 생성하면 조기 중단)
    max_results_needed = page * size
    logger.info(f"알고리즘 실행: 최대 {max_results_needed}개까지 생성")
    
    recommended, remaining_stock, early_stopped = recommend_sequentially_for_inventory(
        initial_ingredients,
        recipe_material_map,
        recipe_df,
        max_results=max_results_needed
    )
    
    logger.info(f"알고리즘 완료: {len(recommended)}개 생성, 조기중단: {early_stopped}")
    
    # 2-6. 페이지네이션 적용
    start, end = (page-1)*size, (page-1)*size + size
    paginated_recommended = recommended[start:end]
    
    # 2-7. 전체 개수 계산
    if early_stopped:
        # 조기중단이면 정확한 total 계산이 어려우므로 근사값 반환
        approx_total = (page - 1) * size + len(paginated_recommended) + 1
        logger.info(f"조기중단으로 인한 근사 total: {approx_total}")
        return paginated_recommended, approx_total
    else:
        total = len(recommended)
        logger.info(f"정확한 total: {total}")
        return paginated_recommended, total


def recommend_sequentially_for_inventory(initial_ingredients, recipe_material_map, recipe_df, max_results: Optional[int] = None):
    """
    순차적 재고 소진 알고리즘으로 레시피 추천
    - 재료를 가장 효율적으로 사용하는 레시피를 순서대로 추천
    - max_results에 도달하면 조기 중단하여 성능 최적화
    """
    # 내부 함수: 단위를 정규화 (소문자 + 앞뒤 공백 제거)
    def _norm(u):
        return (u or "").strip().lower()

    # RECIPE_ID 컬럼을 int형으로 강제 변환 (정확한 비교를 위해)
    try:
        recipe_df['RECIPE_ID'] = recipe_df['RECIPE_ID'].astype(int)
        logger.info("RECIPE_ID 컬럼을 int형으로 변환 완료")
    except Exception as e:
        logger.error(f"RECIPE_ID 컬럼 변환 실패: {e}")
        return [], remaining_stock, False

    # 초기 재고를 딕셔너리 형태로 가공: {재료명: {'amount': 수량, 'unit': 단위}}
    remaining_stock = {
        ing['name']: {'amount': ing['amount'], 'unit': ing['unit']}
        for ing in initial_ingredients
    }

    # 추천된 레시피 리스트
    recommended = []
    # 이미 사용된 레시피 ID를 저장하는 집합
    used_recipe_ids = set()

    # 가능한 재료가 남아 있는 한 반복
    while True:
        # 현재 재고 중 양이 0.001 이상인 재료 목록
        current_ingredients = [k for k, v in remaining_stock.items() if v.get('amount', 0) > 1e-3]
        if not current_ingredients:
            break  # 재료가 다 떨어졌으면 종료

        best_recipe = None         # 이번 라운드에서 추천할 최고의 레시피 ID
        best_usage = {}            # 그 레시피에서 실제 사용된 재료들
        max_used = 0               # 가장 많은 종류의 재료를 사용한 수치

        # 모든 레시피를 하나씩 탐색
        for rid, materials in recipe_material_map.items():
            try:
                rid = int(rid)
            except (ValueError, TypeError) as e:
                logger.error(f"레시피 ID 변환 실패: {rid}, 에러: {e}")
                continue
            
            if rid in used_recipe_ids:
                continue  # 이미 추천된 레시피는 스킵

            temp_stock = copy.deepcopy(remaining_stock)  # 재고 복사본 (시뮬레이션용)
            used_ingredients = {}  # 현재 레시피에서 사용된 재료

            # 이 레시피에 필요한 모든 재료를 순회
            for m in materials:
                mat = m['mat']      # 재료 이름
                req_amt = m['amt']  # 필요한 양
                req_unit = m['unit']  # 단위

                                # 조건:
                # - 재고에 그 재료가 있음
                # - 필요한 양이 명시되어 있음
                # - 재고 수량이 충분함
                # - 단위가 일치하거나 둘 중 하나라도 명시되지 않았음
                if (
                    mat in temp_stock and
                    req_amt is not None and
                    temp_stock[mat].get('amount', 0) > 1e-3 and
                    (not temp_stock[mat].get('unit') or not req_unit
                     or _norm(temp_stock[mat]['unit']) == _norm(req_unit))
                ):
                    # 실제 사용할 양은 현재 재고와 필요량 중 작은 값
                    try:
                        used_amt = min(req_amt, temp_stock[mat]['amount'])
                        if used_amt > 1e-3:
                            temp_stock[mat]['amount'] -= used_amt  # 재고에서 차감
                            used_ingredients[mat] = {'amount': used_amt, 'unit': req_unit}
                    except (ValueError, TypeError) as e:
                        logger.error(f"재료 사용량 계산 실패: {mat}, req_amt: {req_amt}, stock: {temp_stock[mat]}, 에러: {e}")
                        continue

            # 현재 레시피가 지금까지 중 가장 많은 재료를 사용했다면 선택
            if used_ingredients and len(used_ingredients) > max_used:
                best_recipe = rid
                best_usage = used_ingredients
                max_used = len(used_ingredients)

        # 이번 라운드에 추천할 레시피가 없다면 종료
        if not best_recipe:
            break

        # 선택된 레시피의 재료를 실제 재고에서 차감
        for mat, detail in best_usage.items():
            try:
                amount_to_subtract = float(detail.get('amount', 0)) if detail.get('amount') is not None else 0
                remaining_stock[mat]['amount'] -= amount_to_subtract
            except (ValueError, TypeError) as e:
                logger.error(f"재료 수량 차감 실패: {mat}, detail: {detail}, 에러: {e}")
                continue

        # 레시피 정보 조회
        try:
            rid_int = int(best_recipe)
            row = recipe_df[recipe_df['RECIPE_ID'] == rid_int]
        except (ValueError, TypeError) as e:
            logger.error(f"레시피 ID 변환 실패: {best_recipe}, 에러: {e}")
            used_recipe_ids.add(best_recipe)
            continue
        if row.empty:
            # 레시피 정보가 없으면 무시하고 다음으로 진행
            used_recipe_ids.add(best_recipe)
            continue

        # 레시피 정보 딕셔너리로 변환하고 사용된 재료 정보 추가
        recipe_info = row.iloc[0].to_dict()
        
        # Pydantic 스키마에 맞게 필드명 변환
        total_ingredients = len(recipe_material_map.get(best_recipe, []))
        logger.info(f"레시피 {best_recipe}의 전체 재료 개수: {total_ingredients}")
        
        formatted_recipe = {
            "recipe_id": recipe_info.get('RECIPE_ID'),
            "recipe_title": recipe_info.get('RECIPE_TITLE'),
            "cooking_name": recipe_info.get('COOKING_NAME'),
            "scrap_count": recipe_info.get('SCRAP_COUNT'),
            "cooking_case_name": recipe_info.get('COOKING_CASE_NAME'),
            "cooking_category_name": recipe_info.get('COOKING_CATEGORY_NAME'),
            "cooking_introduction": recipe_info.get('COOKING_INTRODUCTION'),
            "number_of_serving": recipe_info.get('NUMBER_OF_SERVING'),
            "thumbnail_url": recipe_info.get('THUMBNAIL_URL'),
            "recipe_url": recipe_info.get('RECIPE_URL'),
            "matched_ingredient_count": len(best_usage),  # 사용된 재료 개수
            "total_ingredients_count": total_ingredients,  # 레시피 전체 재료 개수
            "used_ingredients": []
        }
        
        logger.info(f"formatted_recipe 생성 완료: {formatted_recipe}")
        
        # 사용된 재료 정보를 API 명세서 형식으로 변환
        for mat_name, detail in best_usage.items():
            try:
                measure_amount = float(detail.get('amount', 0)) if detail.get('amount') is not None else None
            except (ValueError, TypeError):
                measure_amount = None
            
            formatted_recipe["used_ingredients"].append({
                "material_name": mat_name,
                "measure_amount": measure_amount,
                "measure_unit": detail.get('unit', '')
            })
        
        recipe_info = formatted_recipe

        # 최종 추천 목록에 추가
        logger.info(f"추천 목록에 추가: recipe_id={formatted_recipe['recipe_id']}, total_ingredients_count={formatted_recipe.get('total_ingredients_count')}")
        logger.info(f"formatted_recipe 전체 내용: {formatted_recipe}")
        recommended.append(formatted_recipe)  # recipe_info가 아닌 formatted_recipe를 추가
        used_recipe_ids.add(best_recipe)  # 재사용 방지

        # 최대 결과 수에 도달하면 조기 중단
        if max_results is not None and len(recommended) >= max_results:
            return recommended, remaining_stock, True

    # 추천된 레시피와 남은 재고를 반환
    return recommended, remaining_stock, False


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
    logger.info(f"레시피 키워드 검색 시작: keyword={keyword}, page={page}, size={size}, method={method}")
    
    if method == "ingredient":
        # 쉼표로 분리된 재료 파싱
        ingredients = [i.strip() for i in keyword.split(",") if i.strip()]
        if not ingredients:
            logger.warning("입력된 재료가 없어 검색 중단")
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
            logger.warning(f"입력된 재료로 레시피를 찾을 수 없음: ingredients={ingredients}")
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
        logger.info(f"재료 기반 레시피 검색 완료: 총 {total}개, 페이지네이션 후 {len(paginated)}개")
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
        
        logger.info(f"COOKING_NAME 일치 총 개수: {total_cooking_name_count}")
        logger.info(f"요청된 size: {size}")
        
        # 2. 요청된 개수만큼 COOKING_NAME 일치 결과 가져오기
        cooking_name_stmt = (
            select(Recipe)
            .where(Recipe.cooking_name.contains(keyword))
            .order_by(desc(Recipe.scrap_count))
            .limit(size)
        )
        logger.info(f"실행할 SQL 쿼리: {cooking_name_stmt}")
        
        cooking_name_result = await db.execute(cooking_name_stmt)
        cooking_name_matches = cooking_name_result.scalars().all()
        
        logger.info(f"실제 반환된 COOKING_NAME 일치 개수: {len(cooking_name_matches)}")
        
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
        logger.info(f"COOKING_NAME 일치: {cooking_name_k}개, 요청: {size}개, 부족: {remaining_after_cooking}개")
        
        if remaining_after_cooking > 0:
            logger.info("벡터 유사도 검색 실행 시작")
            
            try:
                # PostgreSQL 세션을 새로 생성하여 사용
                from common.database.postgres_recommend import SessionLocal
                async with SessionLocal() as postgres_session:
                    # PostgreSQL에서 벡터 데이터 조회 (seen_ids 제외)
                    logger.info(f"seen_ids: {seen_ids}")
                    if seen_ids:
                        vec_stmt = (
                            select(RecipeVector.recipe_id, RecipeVector.vector_name)
                            .where(~RecipeVector.recipe_id.in_(seen_ids))
                        )
                    else:
                        vec_stmt = (
                            select(RecipeVector.recipe_id, RecipeVector.vector_name)
                        )
                    
                    logger.info("PostgreSQL 벡터 데이터 조회 시작")
                    vec_result = await postgres_session.execute(vec_stmt)
                    vec_data = vec_result.all()
                    logger.info(f"PostgreSQL에서 가져온 벡터 데이터 개수: {len(vec_data)}")
                    
                    if vec_data:
                        logger.info("SentenceTransformer 모델 로딩 시작")
                        # SentenceTransformer 모델 로드
                        from services.recommend.recommend_service import get_model
                        model = await get_model()
                        query_vec = model.encode(keyword, normalize_embeddings=True)
                        logger.info(f"쿼리 벡터 생성 완료, 차원: {len(query_vec)}")
                        
                        # 코사인 유사도 계산
                        similarities = []
                        logger.info("코사인 유사도 계산 시작")
                        
                        for i, (rid, vector_data) in enumerate(vec_data):
                            if vector_data is None:
                                continue
                            
                            try:
                                # pgvector Vector 타입을 numpy 배열로 변환
                                import numpy as np
                                
                                # 디버깅: 벡터 데이터 타입과 내용 확인
                                if i < 3:  # 처음 3개만 출력
                                    logger.debug(f"레시피 {rid} 벡터 데이터 타입: {type(vector_data)}")
                                    logger.debug(f"레시피 {rid} 벡터 데이터 내용: {str(vector_data)[:100]}...")
                                
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
                                        logger.debug(f"레시피 {rid}: 유사도 {similarity:.4f}")
                            except Exception as e:
                                if i < 5:  # 처음 5개만 출력
                                    logger.debug(f"레시피 {rid} 벡터 처리 실패: {e}")
                                continue
                        
                        logger.info(f"계산된 유사도 개수: {len(similarities)}")
                        
                        # 유사도 높은 순으로 정렬하고 상위 remaining_after_cooking개 선택
                        if similarities:
                            similarities.sort(key=lambda x: x[1], reverse=True)
                            top_similar = similarities[:remaining_after_cooking]
                            logger.info(f"상위 유사도 레시피 개수: {len(top_similar)}")
                            
                            # 선택된 유사 레시피들의 상세 정보를 MariaDB에서 조회
                            similar_ids = [rid for rid, _ in top_similar]
                            logger.info(f"MariaDB에서 조회할 유사 레시피 ID들: {similar_ids}")
                            
                            if similar_ids:
                                similar_detail_stmt = (
                                    select(Recipe)
                                    .where(Recipe.recipe_id.in_(similar_ids))
                                )
                                similar_detail_result = await db.execute(similar_detail_stmt)
                                similar_recipes = similar_detail_result.scalars().all()
                                logger.info(f"MariaDB에서 조회된 유사 레시피 개수: {len(similar_recipes)}")
                                
                                similar_list = [
                                    {
                                        **r.__dict__,
                                        "recipe_url": get_recipe_url(r.recipe_id),
                                        "RANK_TYPE": 1  # 1은 '벡터 유사도 기반 추천'을 의미
                                    }
                                    for r in similar_recipes
                                ]
                                logger.info(f"최종 similar_list 개수: {len(similar_list)}")
                            else:
                                logger.warning("similar_ids가 비어있음")
                        else:
                            logger.warning("계산된 유사도가 없음")
                    else:
                        logger.warning("PostgreSQL에서 벡터 데이터를 가져오지 못함")
                    
            except Exception as e:
                # 벡터 검색 실패 시 로그만 남기고 계속 진행
                logger.error(f"벡터 검색 중 오류 발생: {e}")
                import traceback
                traceback.print_exc()
                pass
        else:
            if remaining_after_cooking <= 0:
                logger.info(f"벡터 검색 불필요: 부족한 개수가 {remaining_after_cooking}개")
        
        # 4. 2단계 결과를 우선순위 순서로 합치기
        final_list = cooking_name_list + similar_list
        
        logger.info(f"최종 결과: COOKING_NAME 일치 {len(cooking_name_list)}개 + 유사도 기반 {len(similar_list)}개 = 총 {len(final_list)}개")
        
        if not final_list:
            return [], 0
        
        # 4. 페이지네이션 적용
        start, end = (page - 1) * size, (page - 1) * size + size
        paginated = final_list[start:end]
        
        logger.info(f"페이지네이션: page={page}, size={size}, start={start}, end={end}")
        logger.info(f"페이지네이션 후 최종 반환 개수: {len(paginated)}")
        
        # 5. 전체 개수 계산 (정확한 total은 어려우므로 근사값)
        total = (page - 1) * size + len(paginated)
        if len(final_list) > end:
            total += 1
        
        logger.info(f"=== search_recipes_by_keyword 완료: 총 {len(paginated)}개 반환, total={total} ===")
        
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