from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.homeshopping.models.core_model import HomeshoppingClassify, HomeshoppingList
from .shared import logger

async def get_homeshopping_classify_cls_ing(
    db: AsyncSession,
    homeshopping_product_id: int
) -> Optional[int]:
    """
    HOMESHOPPING_CLASSIFY 테이블에서 CLS_ING 값 조회
    """
    # logger.info(f"홈쇼핑 상품 분류 CLS_ING 조회 시작: homeshopping_product_id={homeshopping_product_id}")
    
    try:
        # HOMESHOPPING_CLASSIFY 테이블에서 CLS_ING 값 조회
        stmt = select(HomeshoppingClassify.cls_ing).where(HomeshoppingClassify.product_id == homeshopping_product_id)
        result = await db.execute(stmt)
        cls_ing = result.scalar_one_or_none()
        
        if cls_ing is None:
            logger.warning(f"HOMESHOPPING_CLASSIFY 테이블에서 상품 ID {homeshopping_product_id}를 완제품으로 분류")
            # 해당 상품이 분류 테이블에 없는 경우 기본값 0(완제품) 반환
            return 0
        
        # logger.info(f"홈쇼핑 상품 분류 CLS_ING 조회 완료: homeshopping_product_id={homeshopping_product_id}, cls_ing={cls_ing}")
        return cls_ing
        
    except Exception as e:
        logger.error(f"홈쇼핑 상품 분류 CLS_ING 조회 실패: homeshopping_product_id={homeshopping_product_id}, error={str(e)}")
        # 에러 발생 시 기본값 0(완제품) 반환
        return 0


async def get_recipe_recommendations_for_ingredient(
    db: AsyncSession,
    homeshopping_product_id: int
) -> List[dict]:
    """
    식재료에 대한 레시피 추천 조회
    """
    # logger.info(f"식재료 레시피 추천 조회 시작: homeshopping_product_id={homeshopping_product_id}")
    
    try:
        # TODO: 레시피 서비스와 연동하여 실제 레시피 추천 로직 구현
        # 현재는 더미 데이터 반환
        
        # 상품명 조회 (가장 최근 방송 정보에서 선택)
        stmt = select(HomeshoppingList.product_name).where(HomeshoppingList.product_id == homeshopping_product_id).order_by(HomeshoppingList.live_date.asc(), HomeshoppingList.live_start_time.asc(), HomeshoppingList.live_id.asc())
        result = await db.execute(stmt)
        product_name = result.scalar_one_or_none()
        
        if not product_name:
            logger.warning(f"상품명을 찾을 수 없음: homeshopping_product_id={homeshopping_product_id}")
            return []
        
        # TODO: 레시피 서비스와 연동하여 실제 레시피 추천 로직 구현
        logger.warning("레시피 추천 서비스가 아직 구현되지 않음")
        return []
        
    except Exception as e:
        logger.error(f"식재료 레시피 추천 조회 실패: homeshopping_product_id={homeshopping_product_id}, error={str(e)}")
        return []
