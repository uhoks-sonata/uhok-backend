from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd

from common.dependencies import get_current_user
from common.database.mariadb_service import get_maria_service_db
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger

from services.kok.models.interaction_model import KokCart
from services.user.schemas.profile_schema import UserOut
from services.kok.schemas.interaction_schema import (
    KokCartItemsResponse,
    KokCartAddRequest,
    KokCartAddResponse,
    KokCartUpdateRequest,
    KokCartUpdateResponse,
    KokCartDeleteResponse,
    KokCartRecipeRecommendResponse,
)
from services.kok.crud.cart_crud import (
    get_kok_cart_items,
    add_kok_cart,
    update_kok_cart_quantity,
    delete_kok_cart_item,
    get_ingredients_from_cart_product_ids,
)
from services.recipe.crud.recipe_search_crud import recommend_by_recipe_pgvector_v2

logger = get_logger("kok_router")
router = APIRouter()

@router.post("/carts", response_model=KokCartAddResponse, status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    request: Request,
    cart_data: KokCartAddRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니에 상품 추가
    """
    logger.debug(f"장바구니 추가 시작: user_id={current_user.user_id}, kok_product_id={cart_data.kok_product_id}, kok_quantity={cart_data.kok_quantity}, recipe_id={cart_data.recipe_id}")
    logger.info(f"장바구니 추가 요청: user_id={current_user.user_id}, kok_product_id={cart_data.kok_product_id}, kok_quantity={cart_data.kok_quantity}, recipe_id={cart_data.recipe_id}")
    
    try:
        result = await add_kok_cart(
            db,
            current_user.user_id,
            cart_data.kok_product_id,
            cart_data.kok_quantity,
            cart_data.recipe_id,
        )
        await db.commit()
        
        # commit 후에 새로 생성된 cart_id를 조회
        stmt = select(KokCart).where(
            KokCart.user_id == current_user.user_id,
            KokCart.kok_product_id == cart_data.kok_product_id
        ).order_by(KokCart.kok_cart_id.desc()).limit(1)
        
        cart_result = await db.execute(stmt)
        new_cart = cart_result.scalar_one()
        actual_cart_id = new_cart.kok_cart_id if new_cart else 0
        logger.debug(f"장바구니 추가 성공: user_id={current_user.user_id}, kok_cart_id={actual_cart_id}")
        logger.info(f"장바구니 추가 완료: user_id={current_user.user_id}, kok_cart_id={actual_cart_id}, message={result['message']}")
        
        # 장바구니 추가 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=201)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_cart_add", 
                event_data={
                    "kok_product_id": cart_data.kok_product_id,
                    "kok_quantity": cart_data.kok_quantity,
                    "kok_cart_id": actual_cart_id,
                    "recipe_id": cart_data.recipe_id
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return KokCartAddResponse(
            kok_cart_id=actual_cart_id,
            message=result["message"]
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"장바구니 추가 실패: user_id={current_user.user_id}, kok_product_id={cart_data.kok_product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="장바구니 추가 중 오류가 발생했습니다.")
    

@router.get("/carts", response_model=KokCartItemsResponse)
async def get_cart_items(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="조회할 장바구니 상품 개수"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니 상품 목록 조회
    """
    logger.debug(f"장바구니 상품 목록 조회 시작: user_id={current_user.user_id}, limit={limit}")
    
    try:
        cart_items = await get_kok_cart_items(db, current_user.user_id, limit)
        logger.debug(f"장바구니 상품 목록 조회 성공: user_id={current_user.user_id}, 결과 수={len(cart_items)}")
    except Exception as e:
        logger.error(f"장바구니 상품 목록 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="장바구니 상품 목록 조회 중 오류가 발생했습니다.")
    
    # 장바구니 상품 목록 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_cart_items_view", 
            event_data={
                "limit": limit,
                "item_count": len(cart_items)
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return {"cart_items": cart_items}


@router.patch("/carts/{kok_cart_id}", response_model=KokCartUpdateResponse)
async def update_cart_quantity(
    request: Request,
    kok_cart_id: int,
    update_data: KokCartUpdateRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니 상품 수량 변경
    """
    logger.debug(f"장바구니 수량 변경 시작: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}, quantity={update_data.kok_quantity}")
    
    try:
        result = await update_kok_cart_quantity(db, current_user.user_id, kok_cart_id, update_data.kok_quantity)
        await db.commit()
        logger.debug(f"장바구니 수량 변경 성공: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}")
        
        # 장바구니 수량 변경 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_cart_update", 
                event_data={
                    "kok_cart_id": kok_cart_id,
                    "quantity": update_data.kok_quantity
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return KokCartUpdateResponse(
            kok_cart_id=result["kok_cart_id"],
            kok_quantity=result["kok_quantity"],
            message=result["message"]
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"장바구니 수량 변경 실패: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="장바구니 수량 변경 중 오류가 발생했습니다.")


@router.delete("/carts/{kok_cart_id}", response_model=KokCartDeleteResponse)
async def delete_cart_item(
    request: Request,
    kok_cart_id: int,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니에서 상품 삭제
    """
    logger.debug(f"장바구니 삭제 시작: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}")
    
    try:
        deleted = await delete_kok_cart_item(db, current_user.user_id, kok_cart_id)
        
        if deleted:
            await db.commit()
            logger.debug(f"장바구니 삭제 성공: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}")
            
            # 장바구니 삭제 로그 기록
            if background_tasks:
                http_info = extract_http_info(request, response_code=200)
                background_tasks.add_task(
                    send_user_log, 
                    user_id=current_user.user_id, 
                    event_type="kok_cart_delete", 
                    event_data={"kok_cart_id": kok_cart_id},
                    **http_info  # HTTP 정보를 키워드 인자로 전달
                )
            
            return KokCartDeleteResponse(message="장바구니에서 상품이 삭제되었습니다.")
        else:
            logger.warning(f"장바구니 항목을 찾을 수 없음: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}")
            raise HTTPException(status_code=404, detail="장바구니 항목을 찾을 수 없습니다.")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"장바구니 삭제 실패: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="장바구니 삭제 중 오류가 발생했습니다.")


@router.get("/carts/recipe-recommend", response_model=KokCartRecipeRecommendResponse)
async def recommend_recipes_from_cart_items(
    request: Request,
    product_ids: str = Query(..., description="상품 ID 목록 (쉼표로 구분) - KOK 또는 홈쇼핑 상품 ID 혼용 가능"),
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(10, ge=1, le=100, description="페이지당 레시피 수"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니에서 선택한 상품들의 product_ids를 받아서 키워드 추출 후 레시피 추천
    - KOK 상품: KOK_CLASSIFY 테이블에서 cls_ing이 1인 상품만 필터링
    - 홈쇼핑 상품: HOMESHOPPING_CLASSIFY 테이블에서 cls_ing이 1인 상품만 필터링
    - 해당 상품들의 product_name에서 키워드 추출
    - recipe 폴더 내에서 식재료명 기반 레시피 추천 로직을 사용
    """
    logger.debug(f"레시피 추천 시작: user_id={current_user.user_id}, product_ids={product_ids}, page={page}, size={size}")
    
    try:
        # 통합 상품 ID 파싱 (KOK 또는 홈쇼핑 상품 ID 혼용 가능)
        all_product_ids = [int(pid.strip()) for pid in product_ids.split(",") if pid.strip().isdigit()]
        
        if not all_product_ids:
            logger.warning(f"유효한 상품 ID가 없음: product_ids={product_ids}")
            raise HTTPException(status_code=400, detail="유효한 상품 ID가 없습니다.")
        
        logger.info(f"레시피 추천 요청: user_id={current_user.user_id}, product_ids={all_product_ids}, page={page}, size={size}")
        
        # KOK와 홈쇼핑 상품에서 재료명 추출
        logger.debug("상품에서 재료명 추출 시작")
        ingredients = await get_ingredients_from_cart_product_ids(
            db, [], [], all_product_ids
        )
        
        if not ingredients:
            logger.warning(f"추출된 재료가 없음: user_id={current_user.user_id}")
            return KokCartRecipeRecommendResponse(
                recipes=[],
                total_count=0,
                page=page,
                size=size,
                total_pages=0,
                keyword_extraction=[]
            )
        
        logger.info(f"재료 추출 성공: {ingredients}")
        
        # 추출된 재료를 기반으로 레시피 추천 (pgvector 기반 ingredient 방식)
        # 쉼표로 구분된 재료명을 하나의 문자열로 결합
        ingredients_query = ",".join(ingredients)
        logger.debug(f"레시피 추천 쿼리 생성: {ingredients_query}")
        
        # recommend_by_recipe_pgvector 함수 호출 (method="ingredient")
        # ingredient 모드에서는 vector_searcher가 필요하지 않지만 함수 시그니처상 필수
        # None을 전달하여 실제 사용하지 않음을 표시
        logger.debug("레시피 추천 실행 시작")
        recipes_df = await recommend_by_recipe_pgvector_v2(
            mariadb=db,
            postgres=db,  # MariaDB를 postgres로도 사용 (ingredient 모드에서는 pgvector 사용 안함)
            query=ingredients_query,
            method="ingredient",
            page=page,
            size=size,
            include_materials=True,
            vector_searcher=None  # ingredient 모드에서는 사용하지 않음
        )
        logger.debug(f"레시피 추천 결과: DataFrame 크기={len(recipes_df)}")
        
        # DataFrame을 응답 형식에 맞게 변환
        logger.debug("DataFrame을 응답 형식으로 변환 시작")
        recipes = []
        if not recipes_df.empty:
            logger.debug(f"레시피 데이터 변환: {len(recipes_df)}개 레시피 처리")
            for _, row in recipes_df.iterrows():
                recipe_dict = {
                    "recipe_id": int(row["RECIPE_ID"]),
                    "recipe_title": str(row.get("RECIPE_TITLE", "")) if row.get("RECIPE_TITLE") else None,
                    "cooking_name": str(row.get("COOKING_NAME", "")) if row.get("COOKING_NAME") else None,
                    "description": str(row.get("COOKING_INTRODUCTION", "")) if row.get("COOKING_INTRODUCTION") else None,
                    "scrap_count": int(row["SCRAP_COUNT"]) if row["SCRAP_COUNT"] is not None and not (isinstance(row["SCRAP_COUNT"], float) and pd.isna(row["SCRAP_COUNT"])) else 0,
                    "recipe_url": f"https://www.10000recipe.com/recipe/{int(row['RECIPE_ID'])}",
                    "number_of_serving": str(row.get("NUMBER_OF_SERVING", "")) if row.get("NUMBER_OF_SERVING") else None,
                    "ingredients": []
                }
                
                # 재료 정보가 있으면 ingredients 배열에 재료명만 추가
                if "MATERIALS" in row and row["MATERIALS"] is not None:
                    try:
                        # pandas의 NaN 값 체크를 안전하게 수행
                        if not (isinstance(row["MATERIALS"], float) and pd.isna(row["MATERIALS"])):
                            for material in row["MATERIALS"]:
                                material_name = material.get("MATERIAL_NAME", "")
                                if material_name:
                                    recipe_dict["ingredients"].append(material_name)
                    except:
                        # 에러가 발생하면 재료 정보를 추가하지 않음
                        pass
                
                recipes.append(recipe_dict)
        else:
            logger.debug("추천된 레시피가 없음")
        
        total_count = len(recipes)
        total_pages = (total_count + size - 1) // size
        logger.info(f"레시피 추천 완료: {len(recipes)}개 레시피, 총 {total_count}개")
        
        # 레시피 추천 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_cart_recipe_recommend", 
                event_data={
                    "product_ids": all_product_ids,
                    "extracted_ingredients": ingredients,
                    "recommended_recipes_count": len(recipes),
                    "page": page,
                    "size": size
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return KokCartRecipeRecommendResponse(
            recipes=recipes,
            total_count=total_count,
            page=page,
            size=size,
            total_pages=total_pages,
            keyword_extraction=ingredients
        )
    except ValueError as e:
        logger.warning(f"레시피 추천 검증 오류: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"레시피 추천 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="레시피 추천 중 오류가 발생했습니다.")
