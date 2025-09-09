"""
KOK 서비스 캐시 유틸리티 모듈

Redis를 활용한 캐싱 전략을 구현합니다.
- 할인 상품 목록 캐싱 (5분 TTL)
- 인기 상품 목록 캐싱 (10분 TTL)
- 스토어 베스트 상품 캐싱 (15분 TTL)
"""

import json
import redis
from typing import Optional, Any, Dict, List
from common.logger import get_logger
from common.config import get_settings

logger = get_logger("kok_cache_utils")
settings = get_settings()

# Redis 연결 설정
redis_client = redis.from_url(
    getattr(settings, 'redis_url', 'redis://redis:6379/0'),  # 설정에서 Redis URL 가져오기
    decode_responses=True
)

class KokCacheManager:
    """KOK 서비스 전용 캐시 매니저"""
    
    # 캐시 키 패턴
    CACHE_KEYS = {
        'discounted_products': 'kok:discounted:page:{page}:size:{size}',
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
    
    @classmethod
    def get(cls, cache_type: str, **kwargs) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        try:
            cache_key = cls._get_cache_key(cache_type, **kwargs)
            cached_data = redis_client.get(cache_key)
            
            if cached_data:
                logger.debug(f"캐시 히트: {cache_key}")
                return json.loads(cached_data)
            else:
                logger.debug(f"캐시 미스: {cache_key}")
                return None
                
        except Exception as e:
            logger.error(f"캐시 조회 실패: {cache_type}, {kwargs}, error: {str(e)}")
            return None
    
    @classmethod
    def set(cls, cache_type: str, data: Any, **kwargs) -> bool:
        """캐시에 데이터 저장"""
        try:
            cache_key = cls._get_cache_key(cache_type, **kwargs)
            ttl = cls.TTL.get(cache_type, 300)  # 기본 5분
            
            redis_client.setex(
                cache_key,
                ttl,
                json.dumps(data, ensure_ascii=False, default=str)
            )
            
            logger.debug(f"캐시 저장 완료: {cache_key}, TTL: {ttl}초")
            return True
            
        except Exception as e:
            logger.error(f"캐시 저장 실패: {cache_type}, {kwargs}, error: {str(e)}")
            return False
    
    @classmethod
    def delete_pattern(cls, pattern: str) -> int:
        """패턴에 맞는 캐시 키들 삭제"""
        try:
            keys = redis_client.keys(pattern)
            if keys:
                deleted_count = redis_client.delete(*keys)
                logger.info(f"캐시 패턴 삭제 완료: {pattern}, 삭제된 키 수: {deleted_count}")
                return deleted_count
            return 0
            
        except Exception as e:
            logger.error(f"캐시 패턴 삭제 실패: {pattern}, error: {str(e)}")
            return 0
    
    @classmethod
    def invalidate_discounted_products(cls) -> int:
        """할인 상품 캐시 무효화"""
        return cls.delete_pattern("kok:discounted:*")
    
    @classmethod
    def invalidate_top_selling_products(cls) -> int:
        """인기 상품 캐시 무효화"""
        return cls.delete_pattern("kok:top_selling:*")
    
    @classmethod
    def invalidate_store_best_items(cls) -> int:
        """스토어 베스트 상품 캐시 무효화"""
        return cls.delete_pattern("kok:store_best:*")
    
    @classmethod
    def invalidate_product_info(cls, product_id: int) -> bool:
        """특정 상품 정보 캐시 무효화"""
        try:
            cache_key = cls._get_cache_key('product_info', product_id=product_id)
            result = redis_client.delete(cache_key)
            logger.info(f"상품 정보 캐시 무효화: {cache_key}, 결과: {result}")
            return bool(result)
        except Exception as e:
            logger.error(f"상품 정보 캐시 무효화 실패: {product_id}, error: {str(e)}")
            return False

# 캐시 매니저 인스턴스
cache_manager = KokCacheManager()
