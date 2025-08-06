"""
콕 쇼핑몰 API 라우터 (MariaDB)
- 메인화면 상품정보, 상품 상세, 검색, 찜, 장바구니 기능
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
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
    
    # 메인화면 상품 리스트 스키마
    KokDiscountedProduct,
    KokDiscountedProductsResponse,
    KokTopSellingProduct,
    KokTopSellingProductsResponse,

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
    
    # 리뷰 관련 CRUD
    get_kok_review_data,
    
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
from common.log_utils import send_user_log

router = APIRouter(prefix="/api/kok", tags=["kok"])

# ================================
# 메인화면 상품정보
# ================================

@router.get("/discounted", response_model=KokDiscountedProductsResponse)
async def get_discounted_products(
        current_user: User = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    할인 특가 상품 리스트 조회
    """
    products = await get_kok_discounted_products(db)
    
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
        current_user: User = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    판매율 높은 상품 리스트 조회
    """
    products = await get_kok_top_selling_products(db)
    
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
        current_user: User = Depends(get_current_user),
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

@router.get("/product/{product_id}/tabs", response_model=KokProductTabsResponse)
async def get_product_tabs(
        product_id: int,
        current_user: User = Depends(get_current_user),
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
        current_user: User = Depends(get_current_user),
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

@router.get("/product/{product_id}/details", response_model=KokProductDetailsResponse)
async def get_product_details(
        product_id: int,
        current_user: User = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 상세 정보 조회
    """
    product_details = await get_kok_product_details(db, product_id)
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


# ================================
# 제품 상세 정보
# ================================

@router.get("/product/{product_id}/info", response_model=KokProductInfoResponse)
async def get_product_info(
        product_id: int,
        current_user: User = Depends(get_current_user),
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

@router.get("/product/{product_id}", response_model=KokProductDetailResponse)
async def get_product_detail(
        product_id: int,
        current_user: User = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    제품 상세 정보 조회
    """
    product = await get_kok_product_detail(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
    
    # 상품 상세 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="product_view", 
            event_data={"product_id": product_id, "product_name": product.product_name}
        )
    
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
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    구매 이력 추가
    """
    purchase = await add_kok_purchase(db, current_user.user_id, kok_product_id, kok_quantity, kok_purchase_price)
    
    # 구매 이력 추가 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="purchase_history_add", 
            event_data={
                "product_id": kok_product_id, 
                "quantity": kok_quantity, 
                "purchase_price": kok_purchase_price
            }
        )
    
    return {
        "message": "구매 이력이 추가되었습니다.",
        "purchase": purchase
    }

@router.get("/purchase/history", response_model=KokPurchaseHistoryResponse)
async def get_purchase_history(
        limit: int = Query(10, ge=1, le=50),
        current_user: User = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    구매 이력 조회
    """
    purchase_history = await get_kok_purchase_history(db, current_user.user_id, limit)
    
    # 구매 이력 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="purchase_history_view", 
            event_data={
                "limit": limit,
                "purchase_count": len(purchase_history)
            }
        )
    
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
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    주문 생성
    """
    order = await create_kok_order(db, current_user.user_id, order_data.price_id)
    
    # 주문 생성 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="order_create", 
            event_data={
                "order_id": order.order_id,
                "price_id": order_data.price_id,
                "service_type": "kok"
            }
        )
    
    return order
