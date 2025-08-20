"""
ORDERS + 서비스별 주문 상세를 트랜잭션으로 한 번에 생성/조회 (HomeShopping 명칭 통일)
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from services.order.models.order_model import (
    Order, KokOrder, HomeShoppingOrder, StatusMaster
)

from common.database.mariadb_auth import get_maria_auth_db
from common.logger import get_logger

logger = get_logger("order_crud")

# 상태 코드 상수 정의
STATUS_CODES = {
    "ORDER_RECEIVED": "주문 생성", 
    "PAYMENT_REQUESTED": "결제 요청",
    "PAYMENT_COMPLETED": "결제완료",
    "PREPARING": "상품준비중",
    "SHIPPING": "배송중",
    "DELIVERED": "배송완료",
    "CANCELLED": "주문취소",
    "REFUND_REQUESTED": "환불요청",
    "REFUND_COMPLETED": "환불완료"
}

# 알림 제목 매핑
NOTIFICATION_TITLES = {
    "ORDER_RECEIVED": "주문 생성",
    "PAYMENT_REQUESTED": "결제 요청",
    "PAYMENT_COMPLETED": "주문 완료",
    "PREPARING": "상품 준비",
    "SHIPPING": "배송 시작",
    "DELIVERED": "배송 완료",
    "CANCELLED": "주문 취소",
    "REFUND_REQUESTED": "환불 요청",
    "REFUND_COMPLETED": "환불 완료"
}

# 알림 메시지 매핑
NOTIFICATION_MESSAGES = {
    "ORDER_RECEIVED": "주문이 생성되었습니다.",
    "PAYMENT_REQUESTED": "결제가 요청되었습니다.",
    "PAYMENT_COMPLETED": "주문이 성공적으로 완료되었습니다.",
    "PREPARING": "상품 준비를 시작합니다.",
    "SHIPPING": "상품이 배송을 시작합니다.",
    "DELIVERED": "상품이 배송 완료되었습니다.",
    "CANCELLED": "주문이 취소되었습니다.",
    "REFUND_REQUESTED": "환불이 요청되었습니다.",
    "REFUND_COMPLETED": "환불이 완료되었습니다."
}

async def initialize_status_master(db: AsyncSession):
    """
    STATUS_MASTER 테이블에 기본 상태 코드들을 초기화
    """
    for status_code, status_name in STATUS_CODES.items():
        # 기존 상태 코드 확인
        existing = await get_status_by_code(db, status_code)
        if not existing:
            # 새 상태 코드 추가
            new_status = StatusMaster(
                status_code=status_code,
                status_name=status_name
            )
            db.add(new_status)
    
    await db.commit()

async def validate_user_exists(user_id: int, db: AsyncSession) -> bool:
    """
    사용자 ID가 유효한지 검증 (AUTH_DB.USERS 테이블 확인)
    """
    from services.user.models.user_model import User
    
    # AUTH_DB에서 사용자 조회
    auth_db = get_maria_auth_db()
    async for auth_session in auth_db:
        result = await auth_session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalars().first()
        return user is not None
    
    return False

async def get_status_by_code(db: AsyncSession, status_code: str) -> StatusMaster:
    """
    상태 코드로 상태 정보 조회
    """
    result = await db.execute(
        select(StatusMaster).where(StatusMaster.status_code == status_code)
    )
    return result.scalars().first()

async def get_order_by_id(db: AsyncSession, order_id: int) -> dict:
    """
    주문 ID로 통합 주문 조회 (공통 정보 + 서비스별 상세)
    """
    # 주문 기본 정보 조회
    result = await db.execute(
        select(Order).where(Order.order_id == order_id)
    )
    order = result.scalars().first()
    
    if not order:
        return None
    
    # 콕 주문 정보 조회
    kok_result = await db.execute(
        select(KokOrder).where(KokOrder.order_id == order.order_id)
    )
    kok_orders = kok_result.scalars().all()
    
    # 홈쇼핑 주문 정보 조회
    homeshopping_result = await db.execute(
        select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order.order_id)
    )
    homeshopping_orders = homeshopping_result.scalars().all()
    
    # 딕셔너리 형태로 반환
    return {
        "order_id": order.order_id,
        "user_id": order.user_id,
        "order_time": order.order_time,
        "cancel_time": order.cancel_time,
        "kok_orders": kok_orders,
        "homeshopping_orders": homeshopping_orders
    }


async def get_user_orders(db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0) -> list:
    """
    사용자별 주문 목록 조회 (공통 정보 + 서비스별 상세 + 상품 이미지)
    """
    # 주문 기본 정보 조회
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.order_time.desc())
        .offset(offset)
        .limit(limit)
    )
    orders = result.scalars().all()
    
    order_list = []
    for order in orders:
        # 콕 주문 정보 조회 (상품 이미지 포함)
        kok_result = await db.execute(
            select(KokOrder).where(KokOrder.order_id == order.order_id)
        )
        kok_orders = kok_result.scalars().all()
        
        # 콕 주문에 상품 이미지 정보 추가
        for kok_order in kok_orders:
            try:
                from services.kok.models.kok_model import KokProductInfo, KokImageInfo
                
                # 상품 기본 정보 조회
                product_stmt = select(KokProductInfo).where(KokProductInfo.kok_product_id == kok_order.kok_product_id)
                product_result = await db.execute(product_stmt)
                product = product_result.scalar_one_or_none()
                
                if product:
                    # 썸네일 이미지가 있으면 사용
                    if product.kok_thumbnail:
                        kok_order.product_image = product.kok_thumbnail
                    else:
                        # 썸네일이 없으면 첫 번째 이미지 사용
                        img_stmt = select(KokImageInfo).where(KokImageInfo.kok_product_id == kok_order.kok_product_id).limit(1)
                        img_result = await db.execute(img_stmt)
                        img = img_result.scalar_one_or_none()
                        kok_order.product_image = img.kok_img_url if img else None
                        
                    # 상품명도 추가
                    kok_order.product_name = product.kok_product_name
                else:
                    kok_order.product_image = None
                    kok_order.product_name = None
                
                # 레시피 정보 조회 (recipe_id가 있는 경우)
                if kok_order.recipe_id:
                    try:
                        from services.recipe.models.recipe_model import Recipe
                        
                        recipe_stmt = select(Recipe).where(Recipe.recipe_id == kok_order.recipe_id)
                        recipe_result = await db.execute(recipe_stmt)
                        recipe = recipe_result.scalar_one_or_none()
                        
                        if recipe:
                            kok_order.recipe_title = recipe.recipe_title
                            kok_order.recipe_description = recipe.recipe_description
                            kok_order.recipe_rating = recipe.rating if hasattr(recipe, 'rating') else 0.0
                            kok_order.recipe_scrap_count = recipe.scrap_count if hasattr(recipe, 'scrap_count') else 0
                            
                            # 재료 정보 조회
                            try:
                                from services.recipe.crud.recipe_crud import fetch_recipe_ingredients_status
                                ingredients_status = await fetch_recipe_ingredients_status(db, kok_order.recipe_id, user_id)
                                kok_order.ingredients_owned = ingredients_status.get('owned_count', 0)
                                kok_order.total_ingredients = ingredients_status.get('total_count', 0)
                            except Exception as e:
                                logger.warning(f"레시피 재료 정보 조회 실패: recipe_id={kok_order.recipe_id}, error={str(e)}")
                                kok_order.ingredients_owned = 0
                                kok_order.total_ingredients = 0
                        else:
                            kok_order.recipe_title = None
                            kok_order.recipe_description = None
                            kok_order.recipe_rating = 0.0
                            kok_order.recipe_scrap_count = 0
                            kok_order.ingredients_owned = 0
                            kok_order.total_ingredients = 0
                            
                    except Exception as e:
                        logger.warning(f"레시피 정보 조회 실패: recipe_id={kok_order.recipe_id}, error={str(e)}")
                        kok_order.recipe_title = None
                        kok_order.recipe_description = None
                        kok_order.recipe_rating = 0.0
                        kok_order.recipe_scrap_count = 0
                        kok_order.ingredients_owned = 0
                        kok_order.total_ingredients = 0
                else:
                    # 레시피가 없는 경우
                    kok_order.recipe_title = None
                    kok_order.recipe_description = None
                    kok_order.recipe_rating = 0.0
                    kok_order.recipe_scrap_count = 0
                    kok_order.ingredients_owned = 0
                    kok_order.total_ingredients = 0
                    
            except Exception as e:
                logger.warning(f"콕 상품 이미지 조회 실패: kok_product_id={kok_order.kok_product_id}, error={str(e)}")
                kok_order.product_image = None
                kok_order.product_name = None
                kok_order.recipe_title = None
                kok_order.recipe_description = None
                kok_order.recipe_rating = 0.0
                kok_order.recipe_scrap_count = 0
                kok_order.ingredients_owned = 0
                kok_order.total_ingredients = 0
        
        # 홈쇼핑 주문 정보 조회 (상품 이미지 포함)
        homeshopping_result = await db.execute(
            select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order.order_id)
        )
        homeshopping_orders = homeshopping_result.scalars().all()
        
        # 홈쇼핑 주문에 상품 이미지 정보 추가
        for hs_order in homeshopping_orders:
            try:
                from services.homeshopping.models.homeshopping_model import HomeshoppingList, HomeshoppingImgUrl
                
                # 상품 기본 정보 조회
                product_stmt = select(HomeshoppingList).where(HomeshoppingList.product_id == hs_order.product_id)
                product_result = await db.execute(product_stmt)
                product = product_result.scalar_one_or_none()
                
                if product:
                    # 썸네일 이미지가 있으면 사용
                    if product.thumb_img_url:
                        hs_order.product_image = product.thumb_img_url
                    else:
                        # 썸네일이 없으면 첫 번째 이미지 사용
                        img_stmt = select(HomeshoppingImgUrl).where(HomeshoppingImgUrl.product_id == hs_order.product_id).order_by(HomeshoppingImgUrl.sort_order).limit(1)
                        img_result = await db.execute(img_stmt)
                        img = img_result.scalar_one_or_none()
                        hs_order.product_image = img.img_url if img else None
                        
                    # 상품명도 추가
                    hs_order.product_name = product.product_name
                else:
                    hs_order.product_image = None
                    hs_order.product_name = None
                    
            except Exception as e:
                logger.warning(f"홈쇼핑 상품 이미지 조회 실패: product_id={hs_order.product_id}, error={str(e)}")
                hs_order.product_image = None
                hs_order.product_name = None
        
        order_list.append({
            "order_id": order.order_id,
            "user_id": order.user_id,
            "order_time": order.order_time,
            "cancel_time": order.cancel_time,
            "kok_orders": kok_orders,
            "homeshopping_orders": homeshopping_orders
        })
    
    return order_list


async def calculate_order_total_price(db: AsyncSession, order_id: int) -> int:
    """
    주문 ID로 총 주문 금액 계산 (콕 주문 + 홈쇼핑 주문)
    각 주문 타입별로 이미 계산된 order_price 사용
    """
    total_price = 0
    
    # 콕 주문 총액 계산
    kok_result = await db.execute(
        select(KokOrder).where(KokOrder.order_id == order_id)
    )
    kok_orders = kok_result.scalars().all()
    
    for kok_order in kok_orders:
        if hasattr(kok_order, 'order_price') and kok_order.order_price:
            total_price += kok_order.order_price
        else:
            # order_price가 없는 경우 계산 함수 사용
            try:
                from services.order.crud.kok_order_crud import calculate_kok_order_price
                price_info = await calculate_kok_order_price(
                    db, 
                    kok_order.kok_price_id, 
                    kok_order.kok_product_id, 
                    kok_order.quantity
                )
                total_price += price_info["order_price"]
            except Exception as e:
                logger.warning(f"콕 주문 금액 계산 실패: kok_order_id={kok_order.kok_order_id}, error={str(e)}")
                # 기본값 사용
                total_price += getattr(kok_order, 'dc_price', 0) * getattr(kok_order, 'quantity', 1)
    
    # 홈쇼핑 주문 총액 계산
    homeshopping_result = await db.execute(
        select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order_id)
    )
    homeshopping_orders = homeshopping_result.scalars().all()
    
    for hs_order in homeshopping_orders:
        if hasattr(hs_order, 'order_price') and hs_order.order_price:
            total_price += hs_order.order_price
        else:
            # order_price가 없는 경우 계산 함수 사용
            try:
                from services.order.crud.hs_order_crud import calculate_homeshopping_order_price
                price_info = await calculate_homeshopping_order_price(
                    db, 
                    hs_order.product_id, 
                    hs_order.quantity
                )
                total_price += price_info["order_price"]
            except Exception as e:
                logger.warning(f"홈쇼핑 주문 금액 계산 실패: homeshopping_order_id={hs_order.homeshopping_order_id}, error={str(e)}")
                # 기본값 사용
                total_price += getattr(hs_order, 'dc_price', 0) * getattr(hs_order, 'quantity', 1)
    
    return total_price
