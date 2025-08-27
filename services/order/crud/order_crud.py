"""
ORDERS + 서비스별 주문 상세를 트랜잭션으로 한 번에 생성/조회 (HomeShopping 명칭 통일)
CRUD 계층: 모든 DB 트랜잭션 처리 담당
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List
import httpx
from fastapi import HTTPException

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession 

from services.order.models.order_model import (
    Order, KokOrder, HomeShoppingOrder, 
    KokOrderStatusHistory, HomeShoppingOrderStatusHistory, 
    StatusMaster
)
from services.kok.models.kok_model import KokProductInfo, KokImageInfo
from services.homeshopping.models.homeshopping_model import HomeshoppingList, HomeshoppingImgUrl
from services.recipe.models.recipe_model import Recipe

from services.order.crud.kok_order_crud import update_kok_order_status, calculate_kok_order_price
from services.order.crud.hs_order_crud import calculate_homeshopping_order_price, update_hs_order_status
from services.recipe.crud.recipe_crud import fetch_recipe_ingredients_status

from common.logger import get_logger
logger = get_logger("order_crud")

async def get_delivery_info(db: AsyncSession, order_type: str, order_id: int) -> tuple[str, str]:
    """
    주문의 배송 상태와 배송완료 날짜를 조회하는 헬퍼 함수
    
    Args:
        db: 데이터베이스 세션
        order_type: 주문 타입 ("kok" 또는 "homeshopping")
        order_id: 주문 ID (kok_order_id 또는 homeshopping_order_id)
    
    Returns:
        tuple: (delivery_status, delivery_date)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 배송완료 상태인 경우 한국어 형식으로 날짜 포맷팅
    """
    try:
        if order_type == "kok":
            # 콕 주문의 현재 상태 조회
            result = await db.execute(
                select(KokOrderStatusHistory, StatusMaster)
                .join(StatusMaster, KokOrderStatusHistory.status_id == StatusMaster.status_id)
                .where(KokOrderStatusHistory.kok_order_id == order_id)
                .order_by(desc(KokOrderStatusHistory.changed_at))
                .limit(1)
            )
            status_history = result.first()
        else:
            # 홈쇼핑 주문의 현재 상태 조회
            result = await db.execute(
                select(HomeShoppingOrderStatusHistory, StatusMaster)
                .join(StatusMaster, HomeShoppingOrderStatusHistory.status_id == StatusMaster.status_id)
                .where(HomeShoppingOrderStatusHistory.homeshopping_order_id == order_id)
                .order_by(desc(HomeShoppingOrderStatusHistory.changed_at))
                .limit(1)
            )
            status_history = result.first()
        
        if not status_history or len(status_history) < 2:
            return "주문접수", "배송 정보 없음"
        
        # status_history[0]은 상태 이력, status_history[1]은 상태 마스터
        status_record = status_history[0]
        status_master = status_history[1]
        
        if not status_record or not status_master:
            return "주문접수", "배송 정보 없음"
        
        current_status = status_master.status_name
        changed_at = status_record.changed_at
        
        # 배송완료 상태인 경우 배송완료 날짜 설정
        if current_status == "배송완료":
            # 배송완료 날짜를 한국어 형식으로 포맷팅
            month = changed_at.month
            day = changed_at.day
            weekday = ["월", "화", "수", "목", "금", "토", "일"][changed_at.weekday()]
            delivery_date = f"{month}/{day}({weekday}) 도착"
        else:
            # 배송완료가 아닌 경우 상태에 따른 메시지
            delivery_date = "배송 정보 없음"
        
        return current_status, delivery_date
        
    except Exception as e:
        logger.warning(f"배송 정보 조회 실패: order_type={order_type}, order_id={order_id}, error={str(e)}")
        return "상태 조회 실패", "배송 정보 없음"


async def get_order_by_id(db: AsyncSession, order_id: int) -> dict:
    """
    주문 ID로 통합 주문 조회 (공통 정보 + 서비스별 상세)
    
    Args:
        db: 데이터베이스 세션
        order_id: 조회할 주문 ID
    
    Returns:
        dict: 주문 정보 (order_id, user_id, order_time, cancel_time, kok_orders, homeshopping_orders)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 콕 주문과 홈쇼핑 주문 정보를 모두 포함하여 반환
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
    
    Args:
        db: 데이터베이스 세션
        user_id: 조회할 사용자 ID
        limit: 조회할 주문 개수 (기본값: 20)
        offset: 건너뛸 주문 개수 (기본값: 0)
    
    Returns:
        list: 사용자의 주문 목록 (각 주문에 상품 이미지, 레시피 정보 포함)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 콕 주문: 상품 이미지, 레시피 정보, 재료 보유 현황 포함
        - 홈쇼핑 주문: 상품 이미지 포함
        - 최신 주문순으로 정렬
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
    
    Args:
        db: 데이터베이스 세션
        order_id: 계산할 주문 ID
    
    Returns:
        int: 총 주문 금액
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 각 주문 타입별로 이미 계산된 order_price 사용
        - order_price가 없는 경우 계산 함수를 통해 재계산
        - 계산 실패 시 기본값(dc_price * quantity) 사용
    """
    logger.info(f"주문 총액 계산 시작: order_id={order_id}")
    total_price = 0
    
    # 콕 주문 총액 계산
    logger.info(f"콕 주문 총액 계산 시작: order_id={order_id}")
    kok_result = await db.execute(
        select(KokOrder).where(KokOrder.order_id == order_id)
    )
    kok_orders = kok_result.scalars().all()
    logger.info(f"콕 주문 조회 결과: order_id={order_id}, kok_count={len(kok_orders)}")
    
    for kok_order in kok_orders:
        if hasattr(kok_order, 'order_price') and kok_order.order_price:
            logger.info(f"콕 주문 기존 가격 사용: kok_order_id={kok_order.kok_order_id}, order_price={kok_order.order_price}")
            total_price += kok_order.order_price
        else:
            # order_price가 없는 경우 계산 함수 사용
            logger.info(f"콕 주문 가격 계산 필요: kok_order_id={kok_order.kok_order_id}, kok_price_id={kok_order.kok_price_id}")
            try:
                price_info = await calculate_kok_order_price(
                    db, 
                    kok_order.kok_price_id, 
                    kok_order.kok_product_id, 
                    kok_order.quantity
                )
                total_price += price_info["order_price"]
                logger.info(f"콕 주문 가격 계산 완료: kok_order_id={kok_order.kok_order_id}, calculated_price={price_info['order_price']}")
            except Exception as e:
                logger.warning(f"콕 주문 금액 계산 실패: kok_order_id={kok_order.kok_order_id}, error={str(e)}")
                # 기본값 사용
                fallback_price = getattr(kok_order, 'dc_price', 0) * getattr(kok_order, 'quantity', 1)
                total_price += fallback_price
                logger.info(f"콕 주문 기본값 사용: kok_order_id={kok_order.kok_order_id}, fallback_price={fallback_price}")
    
    # 홈쇼핑 주문 총액 계산
    logger.info(f"홈쇼핑 주문 총액 계산 시작: order_id={order_id}")
    homeshopping_result = await db.execute(
        select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order_id)
    )
    homeshopping_orders = homeshopping_result.scalars().all()
    logger.info(f"홈쇼핑 주문 조회 결과: order_id={order_id}, hs_count={len(homeshopping_orders)}")
    
    for hs_order in homeshopping_orders:
        if hasattr(hs_order, 'order_price') and hs_order.order_price:
            logger.info(f"홈쇼핑 주문 기존 가격 사용: hs_order_id={hs_order.homeshopping_order_id}, order_price={hs_order.order_price}")
            total_price += hs_order.order_price
        else:
            # order_price가 없는 경우 계산 함수 사용
            logger.info(f"홈쇼핑 주문 가격 계산 필요: hs_order_id={hs_order.homeshopping_order_id}, product_id={hs_order.product_id}")
            try:
                price_info = await calculate_homeshopping_order_price(
                    db, 
                    hs_order.product_id, 
                    hs_order.quantity
                )
                total_price += price_info["order_price"]
                logger.info(f"홈쇼핑 주문 가격 계산 완료: hs_order_id={hs_order.homeshopping_order_id}, calculated_price={price_info['order_price']}")
            except Exception as e:
                logger.warning(f"홈쇼핑 주문 금액 계산 실패: homeshopping_order_id={hs_order.homeshopping_order_id}, error={str(e)}")
                # 기본값 사용
                fallback_price = getattr(hs_order, 'dc_price', 0) * getattr(hs_order, 'quantity', 1)
                total_price += fallback_price
                logger.info(f"홈쇼핑 주문 기본값 사용: hs_order_id={hs_order.homeshopping_order_id}, fallback_price={fallback_price}")
    
    logger.info(f"주문 총액 계산 완료: order_id={order_id}, total_price={total_price}")
    return total_price


async def _post_json(url: str, json: Dict[str, Any], timeout: float = 20.0) -> httpx.Response:
    """
    비동기 HTTP POST 유틸
    
    Args:
        url: 요청할 URL
        json: POST할 JSON 데이터
        timeout: 연결/읽기 통합 타임아웃(초, 기본값: 20.0)
    
    Returns:
        httpx.Response: HTTP 응답 객체
        
    Note:
        - httpx.AsyncClient를 context manager로 생성하여 커넥션 누수 방지
        - Content-Type: application/json 헤더 자동 설정
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, json=json, headers={"Content-Type": "application/json"})


async def _get_json(url: str, timeout: float = 15.0) -> httpx.Response:
    """
    비동기 HTTP GET 유틸
    
    Args:
        url: 요청할 URL
        timeout: 연결/읽기 통합 타임아웃(초, 기본값: 15.0)
    
    Returns:
        httpx.Response: HTTP 응답 객체
        
    Note:
        - httpx.AsyncClient 사용
        - 상세한 로깅을 통한 디버깅 지원
        - 예외 발생 시 에러 타입과 함께 로깅
    """
    logger.info(f"HTTP GET 요청 시작: url={url}, timeout={timeout}초")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f"httpx.AsyncClient 생성 완료, GET 요청 전송: {url}")
            response = await client.get(url)
            logger.info(f"HTTP GET 응답 수신: url={url}, status_code={response.status_code}")
            return response
    except Exception as e:
        logger.error(f"HTTP GET 요청 실패: url={url}, error={str(e)}, error_type={type(e).__name__}")
        raise


async def _mark_all_children_paid(
    db: AsyncSession,
    *,
    kok_orders: List[Any],
    hs_orders: List[Any],
    user_id: int,
) -> None:
    """
    하위 주문(콕/홈쇼핑)을 PAYMENT_COMPLETED로 일괄 갱신
    
    Args:
        db: 데이터베이스 세션
        kok_orders: 콕 주문 목록
        hs_orders: 홈쇼핑 주문 목록
        user_id: 상태 변경을 수행하는 사용자 ID
    
    Returns:
        None
        
    Note:
        - CRUD 계층: DB 상태 변경 담당, 트랜잭션 단위 책임
        - 기존 트랜잭션 사용 (새로운 트랜잭션 시작하지 않음)
        - 실패 시 상위에서 롤백 처리
        - 모든 하위 주문의 상태를 PAYMENT_COMPLETED로 변경
    """
    logger.info(f"하위 주문 상태 갱신 시작: kok_count={len(kok_orders)}, hs_count={len(hs_orders)}")
    
    # 콕 주문 상태 갱신
    for k in kok_orders:
        try:
            await update_kok_order_status(
                db=db,
                kok_order_id=k.kok_order_id,
                new_status_code="PAYMENT_COMPLETED",
                changed_by=user_id,
            )
            logger.info(f"콕 주문 상태 갱신 완료: kok_order_id={k.kok_order_id}")
        except Exception as e:
            logger.error(f"콕 주문 상태 갱신 실패: kok_order_id={k.kok_order_id}, error={str(e)}")
            raise
    
    # 홈쇼핑 주문 상태 갱신
    for h in hs_orders:
        try:
            await update_hs_order_status(
                db=db,
                homeshopping_order_id=h.homeshopping_order_id,
                new_status_code="PAYMENT_COMPLETED",
                changed_by=user_id,
            )
            logger.info(f"홈쇼핑 주문 상태 갱신 완료: hs_order_id={h.homeshopping_order_id}")
        except Exception as e:
            logger.error(f"홈쇼핑 주문 상태 갱신 실패: homeshopping_order_id={h.homeshopping_order_id}, error={str(e)}")
            raise
    
    logger.info(f"모든 하위 주문 상태 갱신 완료")


async def _ensure_order_access(db: AsyncSession, order_id: int, user_id: int) -> Dict[str, Any]:
    """
    주문 존재/권한 확인 유틸
    
    Args:
        db: 데이터베이스 세션
        order_id: 확인할 주문 ID
        user_id: 요청한 사용자 ID
    
    Returns:
        Dict[str, Any]: 주문 데이터 (권한이 있는 경우)
        
    Raises:
        HTTPException: 주문이 없거나 권한이 없는 경우 404
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 해당 order_id가 존재하고, 소유자가 user_id인지 확인
        - 권한이 없으면 404 에러 반환
    """
    logger.info(f"주문 접근 권한 확인: order_id={order_id}, user_id={user_id}")
    
    order_data = await get_order_by_id(db, order_id)
    logger.info(f"주문 데이터 조회 결과: order_id={order_id}, order_data={order_data is not None}")
    
    if not order_data:
        logger.error(f"주문을 찾을 수 없음: order_id={order_id}")
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
    
    if order_data["user_id"] != user_id:
        logger.error(f"주문 접근 권한 없음: order_id={order_id}, order_user_id={order_data['user_id']}, request_user_id={user_id}")
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
    
    logger.info(f"주문 접근 권한 확인 완료: order_id={order_id}, user_id={user_id}")
    return order_data

async def cancel_order(db: AsyncSession, order_id: int, reason: str = "결제 시간 초과"):
    """
    주문을 취소하는 함수
    
    Args:
        db: 데이터베이스 세션
        order_id: 취소할 주문 ID
        reason: 취소 사유 (기본값: "결제 시간 초과")
    
    Returns:
        dict: 취소 결과 정보 (order_id, cancel_time, reason, cancelled_kok_orders, cancelled_hs_orders)
        
    Note:
        - CRUD 계층: DB 상태 변경 담당
        - 주문의 cancel_time을 현재 시간으로 설정
        - 모든 하위 주문(콕/홈쇼핑)의 상태를 CANCELLED로 변경
        - 상태 변경 이력을 StatusHistory 테이블에 기록
    """
    try:
        # 주문 조회
        order_result = await db.execute(
            select(Order)
            .where(Order.order_id == order_id)
        )
        order = order_result.scalar_one_or_none()
        
        if not order:
            raise ValueError(f"주문을 찾을 수 없습니다: {order_id}")
        
        # 취소 시간 설정
        current_time = datetime.utcnow()
        
        # cancel_time 업데이트
        order.cancel_time = current_time
        
        # 하위 주문들 조회
        kok_orders_result = await db.execute(
            select(KokOrder)
            .where(KokOrder.order_id == order_id)
        )
        kok_orders = kok_orders_result.scalars().all()
        
        hs_orders_result = await db.execute(
            select(HomeShoppingOrder)
            .where(HomeShoppingOrder.order_id == order_id)
        )
        hs_orders = hs_orders_result.scalars().all()
        
        # 콕 주문 상태를 CANCELLED로 업데이트
        for kok_order in kok_orders:
            # 상태 히스토리에 CANCELLED 기록 추가
            new_status_history = KokOrderStatusHistory(
                kok_order_id=kok_order.kok_order_id,
                status_id=await _get_status_id_by_code(db, "CANCELLED"),
                changed_at=current_time,
                changed_by=1  # 시스템 자동 취소
            )
            db.add(new_status_history)
        
        # 홈쇼핑 주문 상태를 CANCELLED로 업데이트
        for hs_order in hs_orders:
            # 상태 히스토리에 CANCELLED 기록 추가
            new_status_history = HomeShoppingOrderStatusHistory(
                homeshopping_order_id=hs_order.homeshopping_order_id,
                status_id=await _get_status_id_by_code(db, "CANCELLED"),
                changed_at=current_time,
                changed_by=1  # 시스템 자동 취소
            )
            db.add(new_status_history)
        
        await db.commit()
        
        logger.info(f"주문 취소 완료: order_id={order_id}, cancel_time={current_time}, reason={reason}")
        
        return {
            "order_id": order_id,
            "cancel_time": current_time,
            "reason": reason,
            "cancelled_kok_orders": len(kok_orders),
            "cancelled_hs_orders": len(hs_orders)
        }
        
    except Exception as e:
        logger.error(f"주문 취소 실패: order_id={order_id}, error={str(e)}")
        raise

async def _get_status_id_by_code(db: AsyncSession, status_code: str) -> int:
    """
    상태 코드로 status_id를 조회하는 헬퍼 함수
    
    Args:
        db: 데이터베이스 세션
        status_code: 조회할 상태 코드 (예: "CANCELLED", "PAYMENT_COMPLETED")
    
    Returns:
        int: 해당 상태 코드의 status_id
        
    Raises:
        ValueError: 상태 코드를 찾을 수 없는 경우
        
    Note:
        - StatusMaster 테이블에서 status_code로 status_id 조회
        - 주문 취소 시 CANCELLED 상태 ID 조회에 사용
    """
    status_result = await db.execute(
        select(StatusMaster.status_id)
        .where(StatusMaster.status_code == status_code)
    )
    status_id = status_result.scalar_one_or_none()
    if not status_id:
        raise ValueError(f"상태 코드를 찾을 수 없습니다: {status_code}")
    return status_id

async def get_recent_orders_with_ingredients(
    db: AsyncSession, 
    user_id: int, 
    days: int = 7
) -> dict:
    """
    7일 내 주문 내역에서 모든 상품의 product_name을 가져와서 키워드를 추출
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        days: 조회 기간 (일), 기본값 7일
        
    Returns:
        키워드 추출 결과 딕셔너리
    """
    logger.info(f"최근 {days}일 주문 내역 키워드 추출 시작: user_id={user_id}")
    
    # 7일 전 날짜 계산
    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # 주문 기본 정보 조회 (7일 내)
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .where(Order.order_time >= cutoff_date)
        .where(Order.cancel_time.is_(None))  # 취소되지 않은 주문만
        .order_by(Order.order_time.desc())
    )
    orders = result.scalars().all()
    
    # ingredient_matcher 초기화
    from services.recipe.utils.ingredient_matcher import IngredientKeywordExtractor
    ingredient_extractor = IngredientKeywordExtractor()
    
    all_products = []
    all_keywords = set()
    keyword_products = {}  # 키워드별로 어떤 상품에서 추출되었는지 추적
    
    for order in orders:
        # 콕 주문 처리
        kok_result = await db.execute(
            select(KokOrder).where(KokOrder.order_id == order.order_id)
        )
        kok_orders = kok_result.scalars().all()
        
        for kok_order in kok_orders:
            try:
                # 상품 기본 정보 조회
                product_stmt = select(KokProductInfo).where(KokProductInfo.kok_product_id == kok_order.kok_product_id)
                product_result = await db.execute(product_stmt)
                product = product_result.scalar_one_or_none()
                
                if product and product.kok_product_name:
                    product_name = product.kok_product_name
                    
                    # 키워드 추출
                    extracted_keywords = ingredient_extractor.extract_keywords(product_name)
                    
                    # 결과 저장
                    product_info = {
                        "order_id": order.order_id,
                        "order_time": order.order_time,
                        "product_id": kok_order.kok_product_id,
                        "product_name": product_name,
                        "product_type": "kok",
                        "quantity": kok_order.quantity,
                        "price": kok_order.order_price,
                        "extracted_keywords": extracted_keywords,
                        "keyword_count": len(extracted_keywords)
                    }
                    
                    all_products.append(product_info)
                    
                    # 키워드별 상품 추적
                    for keyword in extracted_keywords:
                        all_keywords.add(keyword)
                        if keyword not in keyword_products:
                            keyword_products[keyword] = []
                        keyword_products[keyword].append({
                            "product_name": product_name,
                            "product_type": "kok",
                            "order_time": order.order_time
                        })
                        
            except Exception as e:
                logger.warning(f"콕 주문 처리 실패: kok_order_id={kok_order.kok_order_id}, error={str(e)}")
        
        # 홈쇼핑 주문 처리
        homeshopping_result = await db.execute(
            select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order.order_id)
        )
        homeshopping_orders = homeshopping_result.scalars().all()
        
        for hs_order in homeshopping_orders:
            try:
                # 상품 기본 정보 조회
                product_stmt = select(HomeshoppingList).where(HomeshoppingList.product_id == hs_order.product_id)
                product_result = await db.execute(product_stmt)
                product = product_result.scalar_one_or_none()
                
                if product and product.product_name:
                    product_name = product.product_name
                    
                    # 키워드 추출
                    extracted_keywords = ingredient_extractor.extract_keywords(product_name)
                    
                    # 결과 저장
                    product_info = {
                        "order_id": order.order_id,
                        "order_time": order.order_time,
                        "product_id": hs_order.product_id,
                        "product_name": product_name,
                        "product_type": "homeshopping",
                        "quantity": hs_order.quantity,
                        "price": hs_order.order_price,
                        "extracted_keywords": extracted_keywords,
                        "keyword_count": len(extracted_keywords)
                    }
                    
                    all_products.append(product_info)
                    
                    # 키워드별 상품 추적
                    for keyword in extracted_keywords:
                        all_keywords.add(keyword)
                        if keyword not in keyword_products:
                            keyword_products[keyword] = []
                        keyword_products[keyword].append({
                            "product_name": product_name,
                            "product_type": "homeshopping",
                            "order_time": order.order_time
                        })
                        
            except Exception as e:
                logger.warning(f"홈쇼핑 주문 처리 실패: homeshopping_order_id={hs_order.homeshopping_order_id}, error={str(e)}")
    
    # 키워드 통계 계산
    keyword_stats = {}
    for keyword in all_keywords:
        products = keyword_products[keyword]
        kok_count = len([p for p in products if p["product_type"] == "kok"])
        homeshopping_count = len([p for p in products if p["product_type"] == "homeshopping"])
        
        keyword_stats[keyword] = {
            "total_products": len(products),
            "kok_products": kok_count,
            "homeshopping_products": homeshopping_count,
            "products": products
        }
    
    # 결과 구성
    result = {
        "user_id": user_id,
        "days": days,
        "total_orders": len(orders),
        "total_products": len(all_products),
        "total_keywords": len(all_keywords),
        "products": all_products,
        "keywords": list(all_keywords),
        "keyword_stats": keyword_stats,
        "summary": {
            "kok_products": len([p for p in all_products if p["product_type"] == "kok"]),
            "homeshopping_products": len([p for p in all_products if p["product_type"] == "homeshopping"]),
            "products_with_keywords": len([p for p in all_products if p["keyword_count"] > 0]),
            "products_without_keywords": len([p for p in all_products if p["keyword_count"] == 0])
        }
    }
    
    logger.info(f"최근 {days}일 주문 내역 키워드 추출 완료: 총 {len(all_products)}개 상품, {len(all_keywords)}개 키워드")
    return result
