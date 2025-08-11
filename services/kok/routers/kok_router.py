"""
콕 쇼핑몰 API 라우터 (MariaDB)
- 메인화면 상품정보, 상품 상세, 검색, 찜, 장바구니 기능
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from common.dependencies import get_current_user
from services.user.schemas.user_schema import UserOut
from services.kok.schemas.kok_schema import (
    # 제품 관련 스키마
    KokProductDetailResponse,
    KokProductInfoResponse,
    KokProductTabsResponse,
    
    # 리뷰 관련 스키마      
    KokReviewResponse,
    
    # 상품 상세정보 스키마
    KokProductDetailsResponse,
    
    # 메인화면 상품 리스트 스키마
    KokDiscountedProductsResponse,
    KokTopSellingProductsResponse,
    KokStoreBestProductsResponse,
    
    # 찜 관련 스키마
    KokLikesToggleRequest,
    KokLikesToggleResponse,
    KokLikedProductsResponse,
    
    # 장바구니 관련 스키마
    KokCartItemsResponse,
    KokCartOrderRequest,
    KokCartOrderResponse,
    KokCartAddRequest,
    KokCartAddResponse,
    KokCartUpdateRequest,
    KokCartUpdateResponse,
    KokCartDeleteResponse,
    KokCartRecipeRecommendRequest,
    KokCartRecipeRecommendResponse,
    
    # 검색 관련 스키마
    KokSearchResponse,
    KokSearchHistoryResponse,
    KokSearchHistoryCreate,
    KokSearchHistoryDeleteResponse
)

from services.kok.crud.kok_crud import (
    # 제품 관련 CRUD
    get_kok_product_full_detail,
    get_kok_product_info,
    get_kok_product_tabs,
    get_kok_product_seller_details,
    
    # 리뷰 관련 CRUD
    get_kok_review_data,
    
    # 메인화면 상품 리스트 CRUD
    get_kok_discounted_products,
    get_kok_top_selling_products,
    get_kok_store_best_items,
    
    # 찜 관련 CRUD
    toggle_kok_likes,
    get_kok_liked_products,
    
    # 장바구니 관련 CRUD
    get_kok_cart_items,
    create_orders_from_selected_carts,
    add_kok_cart,
    update_kok_cart_quantity,
    delete_kok_cart_item,
    get_ingredients_from_selected_cart_items,
    
    # 검색 관련 CRUD
    search_kok_products,
    get_kok_search_history,
    add_kok_search_history,
    delete_kok_search_history
)

from common.database.mariadb_service import get_maria_service_db
from common.log_utils import send_user_log
from common.logger import get_logger

router = APIRouter(prefix="/api/kok", tags=["kok"])
logger = get_logger("kok_router")

# ================================
# 메인화면 상품정보
# ================================

@router.get("/discounted", response_model=KokDiscountedProductsResponse)
async def get_discounted_products(
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    할인 특가 상품 리스트 조회
    """
    products = await get_kok_discounted_products(db, page=page, size=size)
    
    # 할인 상품 목록 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="discounted_products_view", 
            event_data={"product_count": len(products)}
        )
    
    return {"products": products}

@router.get("/top-selling", response_model=KokTopSellingProductsResponse)
async def get_top_selling_products(
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    판매율 높은 상품 리스트 조회
    """
    products = await get_kok_top_selling_products(db, page=page, size=size)
    
    # 인기 상품 목록 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="top_selling_products_view", 
            event_data={"product_count": len(products)}
        )
    
    return {"products": products}
    
@router.get("/store-best-items", response_model=KokStoreBestProductsResponse)
async def get_store_best_items(
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    구매한 스토어의 리뷰 많은 상품 리스트 조회
    """
    products = await get_kok_store_best_items(db, current_user.user_id)
    
    # 스토어 베스트 상품 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="store_best_items_view", 
            event_data={"product_count": len(products)}
        )
    
    return {"products": products}

# ================================
# 상품 상세 설명
# ================================

@router.get("/product/{product_id}/info", response_model=KokProductInfoResponse)
async def get_product_info(
        product_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 기본 정보 조회
    """
    product = await get_kok_product_info(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
    
    # 상품 기본 정보 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="product_info_view", 
            event_data={"product_id": product_id}
        )
    
    return product

@router.get("/product/{product_id}/tabs", response_model=KokProductTabsResponse)
async def get_product_tabs(
        product_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 설명 탭 정보 조회
    """
    images = await get_kok_product_tabs(db, product_id)
    if images is None:
        raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
    
    # 상품 탭 정보 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="product_tabs_view", 
            event_data={"product_id": product_id, "tab_count": len(images)}
        )
    
    return {
        "images": images
    }

@router.get("/product/{product_id}/reviews", response_model=KokReviewResponse)
async def get_product_reviews(
        product_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 리뷰 탭 정보 조회
    - KOK_PRODUCT_INFO 테이블에서 리뷰 통계 정보
    - KOK_REVIEW_EXAMPLE 테이블에서 개별 리뷰 목록
    """
    review_data = await get_kok_review_data(db, product_id)
    if review_data is None:
        raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
    
    # 상품 리뷰 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="product_reviews_view", 
            event_data={"product_id": product_id}
        )
    
    return review_data


# ================================
# 제품 상세 정보
# ================================

@router.get("/product/{product_id}/seller-details", response_model=KokProductDetailsResponse)
async def get_product_details(
        product_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 판매자 정보 및 상세정보 조회
    """
    product_details = await get_kok_product_seller_details(db, product_id)
    if not product_details:
        raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
    
    # 상품 상세 정보 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="product_details_view", 
            event_data={"product_id": product_id}
        )
    
    return product_details

@router.get("/product/{product_id}/full-detail", response_model=KokProductDetailResponse)
async def get_product_detail(
        product_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    제품 상세 정보 조회
    """
    product = await get_kok_product_full_detail(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
    
    # 상품 상세 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="product_view", 
            event_data={"product_id": product_id, "kok_product_name": product.get("kok_product_name", "")}
        )
    
    return product


# ================================
# 검색 관련 API
# ================================

@router.get("/search", response_model=KokSearchResponse)
async def search_products(
    keyword: str = Query(..., description="검색 키워드"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    키워드 기반으로 콕 쇼핑몰 내에 있는 상품을 검색
    """
    logger.info(f"상품 검색 요청: user_id={current_user.user_id}, keyword='{keyword}', page={page}, size={size}")
    
    products, total = await search_kok_products(db, keyword, page, size)
    
    logger.info(f"상품 검색 완료: user_id={current_user.user_id}, keyword='{keyword}', 결과 수={len(products)}, 총 개수={total}")
    
    # 검색 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="product_search", 
            event_data={"keyword": keyword, "result_count": len(products)}
        )
    
    return {
        "total": total,
        "page": page,
        "size": size,
        "products": products
    }

@router.get("/search/history", response_model=KokSearchHistoryResponse)
async def get_search_history(
    limit: int = Query(10, ge=1, le=50, description="조회할 이력 개수"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    사용자의 검색 이력을 조회
    """
    history = await get_kok_search_history(db, current_user.user_id, limit)
    
    # 검색 이력 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="search_history_view", 
            event_data={"history_count": len(history)}
        )
    
    return {"history": history}

@router.post("/search/history", response_model=dict)
async def add_search_history(
    search_data: KokSearchHistoryCreate,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    사용자의 검색 이력을 저장
    """
    logger.info(f"검색 이력 추가 요청: user_id={current_user.user_id}, keyword='{search_data.keyword}'")
    
    saved_history = await add_kok_search_history(db, current_user.user_id, search_data.keyword)
    
    logger.info(f"검색 이력 추가 완료: user_id={current_user.user_id}, history_id={saved_history['kok_history_id']}")
    
    # 검색 이력 저장 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="search_history_save", 
            event_data={"keyword": search_data.keyword}
        )
    
    return {
        "message": "검색 이력이 저장되었습니다.",
        "saved": saved_history
    }

@router.delete("/search/history/{history_id}", response_model=KokSearchHistoryDeleteResponse)
async def delete_search_history(
    history_id: int,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    사용자의 검색 이력을 삭제
    """
    logger.info(f"검색 이력 삭제 요청: user_id={current_user.user_id}, history_id={history_id}")
    
    deleted = await delete_kok_search_history(db, current_user.user_id, history_id)
    
    if deleted:
        logger.info(f"검색 이력 삭제 완료: user_id={current_user.user_id}, history_id={history_id}")
        
        # 검색 이력 삭제 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="search_history_delete", 
                event_data={"history_id": history_id}
            )
        
        return {"message": f"검색 이력 ID {history_id}가 삭제되었습니다."}
    else:
        logger.warning(f"검색 이력을 찾을 수 없음: user_id={current_user.user_id}, history_id={history_id}")
        raise HTTPException(status_code=404, detail="해당 검색 이력을 찾을 수 없습니다.")

# ================================
# 찜 관련 API
# ================================

@router.post("/likes/toggle", response_model=KokLikesToggleResponse)
async def toggle_likes(
    like_data: KokLikesToggleRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 찜 등록/해제
    """
    logger.info(f"찜 토글 요청: user_id={current_user.user_id}, product_id={like_data.kok_product_id}")
    
    liked = await toggle_kok_likes(db, current_user.user_id, like_data.kok_product_id)
    
    logger.info(f"찜 토글 완료: user_id={current_user.user_id}, product_id={like_data.kok_product_id}, liked={liked}")
    
    # 찜 토글 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="likes_toggle", 
            event_data={
                "product_id": like_data.kok_product_id,
                "liked": liked
            }
        )
    
    if liked:
        return {
            "liked": True,
            "message": "상품을 찜했습니다."
        }
    else:
        return {
            "liked": False,
            "message": "찜이 취소되었습니다."
        }

@router.get("/likes", response_model=KokLikedProductsResponse)
async def get_liked_products(
    limit: int = Query(50, ge=1, le=100, description="조회할 찜 상품 개수"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    찜한 상품 목록 조회
    """
    liked_products = await get_kok_liked_products(db, current_user.user_id, limit)
    
    # 찜한 상품 목록 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="liked_products_view", 
            event_data={
                "limit": limit,
                "product_count": len(liked_products)
            }
        )
    
    return {"liked_products": liked_products}

# ================================
# 장바구니 관련 API
# ================================

@router.post("/carts", response_model=KokCartAddResponse, status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    cart_data: KokCartAddRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니에 상품 추가
    """
    logger.info(f"장바구니 추가 요청: user_id={current_user.user_id}, product_id={cart_data.kok_product_id}, quantity={cart_data.kok_quantity}, recipe_id={cart_data.recipe_id}")
    
    result = await add_kok_cart(
        db,
        current_user.user_id,
        cart_data.kok_product_id,
        cart_data.kok_quantity,
        cart_data.recipe_id,
    )
    
    logger.info(f"장바구니 추가 완료: user_id={current_user.user_id}, cart_id={result['kok_cart_id']}, message={result['message']}")
    
    # 장바구니 추가 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="cart_add", 
            event_data={
                "product_id": cart_data.kok_product_id,
                "quantity": cart_data.kok_quantity,
                "cart_id": result["kok_cart_id"],
                "recipe_id": cart_data.recipe_id
            }
        )
    
    return KokCartAddResponse(
        kok_cart_id=result["kok_cart_id"],
        message=result["message"]
    )
    
@router.get("/carts", response_model=KokCartItemsResponse)
async def get_cart_items(
    limit: int = Query(50, ge=1, le=200, description="조회할 장바구니 상품 개수"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니 상품 목록 조회
    """
    cart_items = await get_kok_cart_items(db, current_user.user_id, limit)
    
    # 장바구니 상품 목록 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="cart_items_view", 
            event_data={
                "limit": limit,
                "item_count": len(cart_items)
            }
        )
    
    return {"cart_items": cart_items}

@router.patch("/carts/{cart_id}", response_model=KokCartUpdateResponse)
async def update_cart_quantity(
    cart_id: int,
    update_data: KokCartUpdateRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니 상품 수량 변경
    """
    try:
        result = await update_kok_cart_quantity(db, current_user.user_id, cart_id, update_data.kok_quantity)
        
        # 장바구니 수량 변경 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="cart_update", 
                event_data={
                    "cart_id": cart_id,
                    "quantity": update_data.kok_quantity
                }
            )
        
        return KokCartUpdateResponse(
            kok_cart_id=result["kok_cart_id"],
            kok_quantity=result["kok_quantity"],
            message=result["message"]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/carts/{cart_id}", response_model=KokCartDeleteResponse)
async def delete_cart_item(
    cart_id: int,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니에서 상품 삭제
    """
    deleted = await delete_kok_cart_item(db, current_user.user_id, cart_id)
    
    if deleted:
        # 장바구니 삭제 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="cart_delete", 
                event_data={"cart_id": cart_id}
            )
        
        return KokCartDeleteResponse(message="장바구니에서 상품이 삭제되었습니다.")
    else:
        raise HTTPException(status_code=404, detail="장바구니 항목을 찾을 수 없습니다.")
    

# ================================
# 주문 관련 API
# ================================

# 단일 상품 주문 API는 사용하지 않습니다. (멀티 카트 주문 API 사용)

@router.post("/carts/order", response_model=KokCartOrderResponse, status_code=status.HTTP_201_CREATED)
async def order_from_selected_carts(
    request: KokCartOrderRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
):
    logger.info(f"장바구니 주문 시작: user_id={current_user.user_id}, selected_items_count={len(request.selected_items)}")
    
    if not request.selected_items:
        logger.warning(f"선택된 항목이 없음: user_id={current_user.user_id}")
        raise HTTPException(status_code=400, detail="선택된 항목이 없습니다.")

    result = await create_orders_from_selected_carts(
        db, current_user.user_id, [i.model_dump() for i in request.selected_items]
    )

    logger.info(f"장바구니 주문 완료: user_id={current_user.user_id}, order_id={result['order_id']}, order_count={result['order_count']}")

    if background_tasks:
        background_tasks.add_task(
            send_user_log,
            user_id=current_user.user_id,
            event_type="cart_order_create",
            event_data=result,
        )

    return KokCartOrderResponse(
        order_id=result["order_id"],
        order_count=result["order_count"],
        message=result["message"],
    )

@router.post("/carts/recipe-recommend", response_model=KokCartRecipeRecommendResponse)
async def recommend_recipes_from_cart_items(
    recommend_request: KokCartRecipeRecommendRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    선택된 장바구니 상품들의 재료로 레시피 추천
    """
    try:
        logger.info(f"레시피 추천 요청: user_id={current_user.user_id}, cart_ids={recommend_request.selected_cart_ids}")
        
        # 선택된 장바구니 상품들에서 재료명 추출
        ingredients = await get_ingredients_from_selected_cart_items(
            db, current_user.user_id, recommend_request.selected_cart_ids
        )
        
        if not ingredients:
            logger.warning(f"장바구니 상품에서 재료를 추출할 수 없음: user_id={current_user.user_id}, cart_ids={recommend_request.selected_cart_ids}")
            raise HTTPException(status_code=400, detail="재료를 추출할 수 있는 상품이 없습니다.")
        
        logger.info(f"재료 추출 성공: {ingredients}")
        
        # 레시피 추천 서비스 호출
        from services.recipe.crud.recipe_crud import recommend_recipes_by_ingredients
        
        recipes, total = await recommend_recipes_by_ingredients(
            db, 
            ingredients, 
            amounts=None,  # 장바구니 기반 추천에서는 분량 정보 없음
            units=None,    # 장바구니 기반 추천에서는 단위 정보 없음
            page=recommend_request.page, 
            size=recommend_request.size
        )
        
        logger.info(f"레시피 추천 완료: {len(recipes)}개 레시피 발견, 총 {total}개")
        
        # 레시피 추천 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="cart_recipe_recommend", 
                event_data={
                    "selected_cart_ids": recommend_request.selected_cart_ids,
                    "ingredients_used": ingredients,
                    "page": recommend_request.page,
                    "size": recommend_request.size,
                    "total_results": total
                }
            )
        
        return KokCartRecipeRecommendResponse(
            recipes=recipes,
            page=recommend_request.page,
            total=total,
            ingredients_used=ingredients
        )
    except ValueError as e:
        logger.warning(f"레시피 추천 검증 오류: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"레시피 추천 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="레시피 추천 중 오류가 발생했습니다.")