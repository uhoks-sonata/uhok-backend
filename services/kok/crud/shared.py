from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.kok.models.product_model import KokPriceInfo

logger = get_logger("kok_crud")

async def get_latest_kok_price_id(
        db: AsyncSession,
        kok_product_id: int
) -> Optional[int]:
    """
    주어진 kok_product_id에 대한 최신 가격 ID를 반환
    
    Args:
        db: 데이터베이스 세션
        kok_product_id: 상품 ID
        
    Returns:
        최신 가격 ID 또는 None
    """
    try:
        stmt = (
            select(func.max(KokPriceInfo.kok_price_id))
            .where(KokPriceInfo.kok_product_id == kok_product_id)
        )
        result = await db.execute(stmt)
        latest_price_id = result.scalar_one_or_none()
        
        if latest_price_id:
    # logger.info(f"최신 가격 ID 조회 완료: kok_product_id={kok_product_id}, latest_kok_price_id={latest_price_id}")
            return latest_price_id
        else:
            logger.warning(f"가격 정보를 찾을 수 없음: kok_product_id={kok_product_id}")
            return None
            
    except Exception as e:
        logger.error(f"최신 가격 ID 조회 중 오류 발생: kok_product_id={kok_product_id}, error={str(e)}")
        return None
