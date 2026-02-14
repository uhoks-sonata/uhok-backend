"""
KOK 서비스 캐시 유틸리티 모듈

Redis를 활용한 캐싱 전략을 구현합니다.
- 할인 상품 목록 캐싱 (5분 TTL)
- 인기 상품 목록 캐싱 (10분 TTL)
- 스토어 베스트 상품 캐싱 (15분 TTL)
"""

from typing import Any, Optional

from common.cache.redis_cache import RedisCacheCore
from common.config import get_settings
from common.logger import get_logger

logger = get_logger("kok_cache_utils")
settings = get_settings()

class KokCacheManager:
    """KOK 서비스 전용 캐시 매니저"""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or getattr(settings, "redis_url", "redis://redis:6379/0")
        self.redis_cache = RedisCacheCore(self.redis_url, component="kok_cache")

    # 캐시 키 패턴
    CACHE_KEYS = {
        'discounted_products': 'kok:discounted:v2:page:{page}:size:{size}',
        'top_selling_products': 'kok:top_selling:page:{page}:size:{size}:sort:{sort_by}',
        'store_best_items': 'kok:store_best:user:{user_id}:sort:{sort_by}',
        'product_info': 'kok:product:{product_id}',
    }

    # TTL 설정 (초)
    TTL = {
        'discounted_products': 300,  # 5분
        'top_selling_products': 600,  # 10분
        'store_best_items': 900,     # 15분
        'product_info': 1800,        # 30분
    }

    @classmethod
    def _get_cache_key(cls, cache_type: str, **kwargs) -> str:
        """캐시 키 생성"""
        key_template = cls.CACHE_KEYS.get(cache_type)
        if not key_template:
            raise ValueError(f"Unknown cache type: {cache_type}")

        return key_template.format(**kwargs)

    async def get(self, cache_type: str, **kwargs) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        try:
            cache_key = self._get_cache_key(cache_type, **kwargs)
            cached_data = await self.redis_cache.get_json(cache_key)

            if cached_data:
                logger.debug(f"캐시 히트: {cache_key}")
                return cached_data
            logger.debug(f"캐시 미스: {cache_key}")
            return None

        except Exception as e:
            logger.error(f"캐시 조회 실패: {cache_type}, {kwargs}, error: {str(e)}")
            return None

    async def set(self, cache_type: str, data: Any, **kwargs) -> bool:
        """캐시에 데이터 저장"""
        try:
            cache_key = self._get_cache_key(cache_type, **kwargs)
            ttl = self.TTL.get(cache_type, 300)  # 기본 5분

            success = await self.redis_cache.set_json(
                cache_key, data, ttl, ensure_ascii=False
            )
            if not success:
                return False

            logger.debug(f"캐시 저장 완료: {cache_key}, TTL: {ttl}초")
            return True

        except Exception as e:
            logger.error(f"캐시 저장 실패: {cache_type}, {kwargs}, error: {str(e)}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """패턴에 맞는 캐시 키들 삭제"""
        try:
            deleted_count = await self.redis_cache.delete_pattern(pattern)
            if deleted_count:
                logger.info(f"캐시 패턴 삭제 완료: {pattern}, 삭제된 키 수: {deleted_count}")
                return deleted_count
            return 0

        except Exception as e:
            logger.error(f"캐시 패턴 삭제 실패: {pattern}, error: {str(e)}")
            return 0

    async def invalidate_discounted_products(self) -> int:
        """할인 상품 캐시 무효화"""
        return await self.delete_pattern("kok:discounted:*")

    async def invalidate_top_selling_products(self) -> int:
        """인기 상품 캐시 무효화"""
        return await self.delete_pattern("kok:top_selling:*")

    async def invalidate_store_best_items(self) -> int:
        """스토어 베스트 상품 캐시 무효화"""
        return await self.delete_pattern("kok:store_best:*")

    async def invalidate_product_info(self, product_id: int) -> bool:
        """특정 상품 정보 캐시 무효화"""
        try:
            cache_key = self._get_cache_key('product_info', product_id=product_id)
            result = await self.redis_cache.delete_key(cache_key)
            logger.info(f"상품 정보 캐시 무효화: {cache_key}, 결과: {result}")
            return bool(result)
        except Exception as e:
            logger.error(f"상품 정보 캐시 무효화 실패: {product_id}, error: {str(e)}")
            return False

    async def close(self):
        """Redis 연결 종료"""
        await self.redis_cache.close()

# 캐시 매니저 인스턴스
cache_manager = KokCacheManager()
