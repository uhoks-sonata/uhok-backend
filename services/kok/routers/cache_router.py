from fastapi import APIRouter, HTTPException

from common.logger import get_logger
from services.kok.utils.cache_utils import cache_manager

logger = get_logger("kok_router")
router = APIRouter()

@router.post("/cache/invalidate/discounted")
async def invalidate_discounted_cache():
    """
    할인 상품 캐시 무효화
    """
    logger.debug("할인 상품 캐시 무효화 시작")
    
    try:
        deleted_count = cache_manager.invalidate_discounted_products()
        logger.debug(f"할인 상품 캐시 무효화 성공: 삭제된 키 수={deleted_count}")
        logger.info(f"할인 상품 캐시 무효화 완료: 삭제된 키 수={deleted_count}")
        return {"message": f"할인 상품 캐시가 무효화되었습니다. 삭제된 키 수: {deleted_count}"}
    except Exception as e:
        logger.error(f"할인 상품 캐시 무효화 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"캐시 무효화 중 오류가 발생했습니다: {str(e)}")

@router.post("/cache/invalidate/top-selling")
async def invalidate_top_selling_cache():
    """
    인기 상품 캐시 무효화
    """
    logger.debug("인기 상품 캐시 무효화 시작")
    
    try:
        deleted_count = cache_manager.invalidate_top_selling_products()
        logger.debug(f"인기 상품 캐시 무효화 성공: 삭제된 키 수={deleted_count}")
        logger.info(f"인기 상품 캐시 무효화 완료: 삭제된 키 수={deleted_count}")
        return {"message": f"인기 상품 캐시가 무효화되었습니다. 삭제된 키 수: {deleted_count}"}
    except Exception as e:
        logger.error(f"인기 상품 캐시 무효화 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"캐시 무효화 중 오류가 발생했습니다: {str(e)}")

@router.post("/cache/invalidate/store-best")
async def invalidate_store_best_cache():
    """
    스토어 베스트 상품 캐시 무효화
    """
    logger.debug("스토어 베스트 상품 캐시 무효화 시작")
    
    try:
        deleted_count = cache_manager.invalidate_store_best_items()
        logger.debug(f"스토어 베스트 상품 캐시 무효화 성공: 삭제된 키 수={deleted_count}")
        logger.info(f"스토어 베스트 상품 캐시 무효화 완료: 삭제된 키 수={deleted_count}")
        return {"message": f"스토어 베스트 상품 캐시가 무효화되었습니다. 삭제된 키 수: {deleted_count}"}
    except Exception as e:
        logger.error(f"스토어 베스트 상품 캐시 무효화 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"캐시 무효화 중 오류가 발생했습니다: {str(e)}")

@router.post("/cache/invalidate/all")
async def invalidate_all_cache():
    """
    모든 KOK 관련 캐시 무효화
    """
    logger.debug("모든 KOK 관련 캐시 무효화 시작")
    
    try:
        discounted_count = cache_manager.invalidate_discounted_products()
        top_selling_count = cache_manager.invalidate_top_selling_products()
        store_best_count = cache_manager.invalidate_store_best_items()
        
        total_count = discounted_count + top_selling_count + store_best_count
        logger.debug(f"모든 KOK 캐시 무효화 성공: 총 삭제된 키 수={total_count}")
        logger.info(f"모든 KOK 캐시 무효화 완료: 총 삭제된 키 수={total_count}")
        return {
            "message": f"모든 KOK 캐시가 무효화되었습니다.",
            "deleted_keys": {
                "discounted_products": discounted_count,
                "top_selling_products": top_selling_count,
                "store_best_items": store_best_count,
                "total": total_count
            }
        }
    except Exception as e:
        logger.error(f"모든 KOK 캐시 무효화 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"캐시 무효화 중 오류가 발생했습니다: {str(e)}")
        
