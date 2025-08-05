"""
콕 쇼핑몰 API 라우터 (MariaDB)
- 메인화면 상품정보, 상품 상세, 검색, 찜, 장바구니 기능
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from common.dependencies import get_current_user
from services.user.models.user_model import User
from services.order.schemas.order_schema import KokOrderCreate, OrderRead
from services.order.crud.order_crud import create_kok_order

from services.kok.schemas.kok_schema import (
    # 제품 관련 스키마
    KokProductDetailResponse,
    KokProductListResponse,
    KokProductBase,
    KokProductInfoResponse,
    KokProductTabsResponse,
    
    # 리뷰 관련 스키마
    KokReviewResponse,
    KokReviewStats,
    KokReviewDetail,
    KokReviewExample,
    
    # 상품 상세정보 스키마
    KokProductDetailsResponse,
    KokProductDetails,
    KokDetailInfoItem,
    
    # 검색 관련 스키마
    KokSearchRequest,
    KokSearchHistoryResponse,
    KokSearchHistoryCreate,
    KokSearchHistoryDelete,
    
    # 찜 관련 스키마
    KokLikesToggle,
    KokLikesResponse,
    KokLikesListResponse,
    
    # 장바구니 관련 스키마
    KokCartToggle,
    KokCartResponse,
    KokCartListResponse,
    
    # 메인화면 상품 리스트 스키마
    KokDiscountedProduct,
    KokDiscountedProductsResponse,
    KokTopSellingProduct,
    KokTopSellingProductsResponse,
    KokSearchProduct,
    KokSearchProductsResponse,
    KokStoreBestProduct,
    KokStoreBestProductsResponse,
    KokUnpurchasedResponse,
    
    # 구매 이력 관련 스키마
    KokPurchaseHistoryResponse,
    KokPurchaseCreate
)

from services.kok.crud.kok_crud import (
    # 제품 관련 CRUD
    get_kok_product_detail,
    get_kok_product_list,
    get_kok_product_by_id,
    get_kok_product_info,
    get_kok_product_tabs,
    get_kok_product_details,
    search_kok_products,
    
    # 리뷰 관련 CRUD
    get_kok_review_data,
    
    # 검색 이력 관련 CRUD
    get_kok_search_history,
    add_kok_search_history,
    delete_kok_search_history,
    
    # 찜 관련 CRUD
    toggle_kok_likes,
    get_kok_liked_products,
    
    # 장바구니 관련 CRUD
    toggle_kok_cart,
    get_kok_cart_items,
    
    # 메인화면 상품 리스트 CRUD
    get_kok_discounted_products,
    get_kok_top_selling_products,
    get_kok_store_best_items,
    get_kok_unpurchased,
    
    # 구매 이력 관련 CRUD
    add_kok_purchase,
    get_kok_purchase_history
)

from common.database.mariadb_service import get_maria_service_db

router = APIRouter(prefix="/api/kok", tags=["kok"])

# ================================
# 메인화면 상품정보
# ================================

@router.get("/discounted", response_model=KokDiscountedProductsResponse)
async def get_discounted_products(
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    할인 특가 상품 리스트 조회
    """
    products = await get_kok_discounted_products(db)
    return {"products": products}

@router.get("/top-selling", response_model=KokTopSellingProductsResponse)
async def get_top_selling_products(
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    판매율 높은 상품 리스트 조회
    """
    products = await get_kok_top_selling_products(db)
    return {"products": products}
    
@router.get("/store-best-items", response_model=KokStoreBestProductsResponse)
async def get_store_best_items(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    구매한 스토어의 리뷰 많은 상품 리스트 조회
    """
    products = await get_kok_store_best_items(db, current_user.user_id)
    return {"products": products}

# ================================
# 상품 상세 설명
# ================================

@router.get("/product/{product_id}/tabs", response_model=KokProductTabsResponse)
async def get_product_tabs(
        product_id: int,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 설명 탭 정보 조회
    """
    images = await get_kok_product_tabs(db, product_id)
    if images is None:
        raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
    
    return {
        "images": images
    }

@router.get("/product/{product_id}/reviews", response_model=KokReviewResponse)
async def get_product_reviews(
        product_id: int,
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
    
    return review_data

@router.get("/product/{product_id}/details", response_model=KokProductDetailsResponse)
async def get_product_details(
        product_id: int,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 상세 정보 조회
    """
    product_details = await get_kok_product_details(db, product_id)
    if not product_details:
        raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
    return product_details

# ================================
# 검색 기능
# ================================

@router.get("/search", response_model=KokSearchProductsResponse)
async def search_products(
        keyword: str = Query(..., description="검색 키워드"),
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=100),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    키워드 기반 상품 검색
    """
    products = await search_kok_products(db, keyword, page, size)
    
    # 검색 이력 저장
    await add_kok_search_history(db, current_user.user_id, keyword)
    
    return {"products": products}

@router.get("/search/history", response_model=KokSearchHistoryResponse)
async def get_search_history(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    사용자 검색 이력 조회
    """
    history = await get_kok_search_history(db, current_user.user_id)
    return {"history": history}

@router.post("/search/history")
async def save_search_history(
        req: KokSearchHistoryCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    검색 이력 저장
    """
    saved_history = await add_kok_search_history(db, current_user.user_id, req.keyword)
    
    return {
        "message": "검색 이력이 저장되었습니다.",
        "saved": saved_history
    }

@router.delete("/search/history")
async def delete_search_history(
        keyword: str = Query(..., description="삭제할 키워드"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    검색 이력 삭제
    """
    deleted = await delete_kok_search_history(db, current_user.user_id, keyword)
    
    if deleted:
        return {"message": f"'{keyword}' 키워드 검색 이력이 삭제되었습니다."}
    else:
        raise HTTPException(status_code=404, detail="검색 이력을 찾을 수 없습니다.")

# ================================
# 상품 찜 등록/해제
# ================================

@router.post("/likes/toggle", response_model=KokLikesResponse)
async def toggle_likes(
        req: KokLikesToggle,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 찜 등록/해제
    """
    result = await toggle_kok_likes(db, current_user.user_id, req.kok_product_id)
    return result

@router.get("/likes", response_model=KokLikesListResponse)
async def get_liked_products(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    찜한 상품 목록 조회
    """
    liked_products = await get_kok_liked_products(db, current_user.user_id)
    return {"liked_products": liked_products}

# ================================
# 장바구니 등록/해제
# ================================

@router.post("/carts/toggle", response_model=KokCartResponse)
async def toggle_cart(
        req: KokCartToggle,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니 등록/해제
    """
    result = await toggle_kok_cart(db, current_user.user_id, req.kok_product_id)
    return result

@router.get("/carts", response_model=KokCartListResponse)
async def get_cart_items(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니 상품 목록 조회
    """
    cart_items = await get_kok_cart_items(db, current_user.user_id)
    return {"cart_items": cart_items}

# ================================
# 제품 상세 정보
# ================================

@router.get("/product/{product_id}/info", response_model=KokProductInfoResponse)
async def get_product_info(
        product_id: int,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 기본 정보 조회
    """
    product = await get_kok_product_info(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
    return product

@router.get("/product/{product_id}", response_model=KokProductDetailResponse)
async def get_product_detail(
        product_id: int,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    제품 상세 정보 조회
    """
    product = await get_kok_product_detail(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
    return product




# ================================
# 구매 이력 관련 API
# ================================

@router.post("/purchase")
async def add_purchase(
        kok_product_id: int,
        kok_quantity: int = 1,
        kok_purchase_price: Optional[int] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    구매 이력 추가
    """
    purchase = await add_kok_purchase(db, current_user.user_id, kok_product_id, kok_quantity, kok_purchase_price)
    return {
        "message": "구매 이력이 추가되었습니다.",
        "purchase": purchase
    }

@router.get("/purchase/history", response_model=KokPurchaseHistoryResponse)
async def get_purchase_history(
        limit: int = Query(10, ge=1, le=50),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    구매 이력 조회
    """
    purchase_history = await get_kok_purchase_history(db, current_user.user_id, limit)
    return {
        "purchase_history": purchase_history,
        "total_count": len(purchase_history)
    }


# ================================
# 주문 관련 API
# ================================

@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_kok_order_api(
    order_data: KokOrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    주문 생성
    """
    order = await create_kok_order(db, current_user.user_id, order_data.price_id)
    return order
