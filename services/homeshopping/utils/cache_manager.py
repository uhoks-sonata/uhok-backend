"""
홈쇼핑 캐시 관리 유틸리티
- Redis를 활용한 스케줄 데이터 캐싱
- 성능 최적화를 위한 캐시 전략 구현
"""

from datetime import date
from typing import Dict, List, Optional

from common.cache.redis_cache import RedisCacheCore
from common.config import get_settings
from common.logger import get_logger

logger = get_logger("homeshopping_cache")
settings = get_settings()

class HomeshoppingCacheManager:
    """홈쇼핑 캐시 관리자"""
    
    def __init__(self, redis_url: Optional[str] = None):  # Redis URL 형식 (기본값)
        self.redis_url = redis_url or getattr(settings, "redis_url", "redis://redis:6379/0")
        self.redis_cache = RedisCacheCore(self.redis_url, component="homeshopping_cache")
        self.cache_ttl = {
            "schedule": 7200,  # 2시간 (극도로 긴 캐시)
            "schedule_count": 14400,  # 4시간
            "product_detail": 14400,  # 4시간
            "food_product_ids": 28800,  # 8시간 (식품 ID 목록)
            "kok_recommendation": 3600,  # 1시간 (KOK 추천 결과)
        }
    
    def _generate_cache_key(self, cache_type: str, **kwargs) -> str:
        """캐시 키 생성"""
        key_parts = [f"homeshopping:{cache_type}"]
        
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}:{v}")
        
        return ":".join(key_parts)
    
    async def get_schedule_cache(
        self, 
        live_date: Optional[date] = None
    ) -> Optional[List[Dict]]:
        """스케줄 캐시 조회"""
        try:
            cache_key = self._generate_cache_key(
                "schedule", 
                live_date=live_date.isoformat() if live_date else "all"
            )

            cached_data = await self.redis_cache.get_json(cache_key)
            if cached_data:
                logger.info(f"스케줄 캐시 히트: {cache_key}")
                return cached_data["schedules"]
            
            logger.info(f"스케줄 캐시 미스: {cache_key}")
            return None
            
        except Exception as e:
            logger.error(f"스케줄 캐시 조회 실패: {e}")
            return None
    
    async def set_schedule_cache(
        self, 
        schedules: List[Dict], 
        live_date: Optional[date] = None
    ) -> bool:
        """스케줄 캐시 저장"""
        try:
            cache_key = self._generate_cache_key(
                "schedule", 
                live_date=live_date.isoformat() if live_date else "all"
            )

            cache_data = {"schedules": schedules}
            success = await self.redis_cache.set_json(
                cache_key,
                cache_data,
                self.cache_ttl["schedule"],
            )
            if not success:
                return False
            
            logger.info(f"스케줄 캐시 저장: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"스케줄 캐시 저장 실패: {e}")
            return False
    
    async def invalidate_schedule_cache(self, live_date: Optional[date] = None) -> bool:
        """스케줄 캐시 무효화"""
        try:
            # 패턴 매칭으로 관련 캐시 모두 삭제
            pattern = self._generate_cache_key("schedule", live_date=live_date.isoformat() if live_date else "*")
            if not live_date:
                pattern = "homeshopping:schedule:*"

            deleted_count = await self.redis_cache.delete_pattern(pattern)
            if deleted_count:
                logger.info(f"스케줄 캐시 무효화: {deleted_count}개 키 삭제")
            
            return True
            
        except Exception as e:
            logger.error(f"스케줄 캐시 무효화 실패: {e}")
            return False

    async def get_kok_recommendation_cache(
        self,
        product_id: int,
        k: int = 5
    ) -> Optional[List[Dict]]:
        """KOK 추천 결과 캐시 조회"""
        try:
            cache_key = self._generate_cache_key(
                "kok_recommendation",
                product_id=product_id,
                k=k
            )

            cached_data = await self.redis_cache.get_json(cache_key)
            if cached_data:
                logger.info(f"KOK 추천 캐시 히트: {cache_key}")
                return cached_data["recommendations"]

            logger.info(f"KOK 추천 캐시 미스: {cache_key}")
            return None

        except Exception as e:
            logger.error(f"KOK 추천 캐시 조회 실패: {e}")
            return None

    async def set_kok_recommendation_cache(
        self,
        product_id: int,
        recommendations: List[Dict],
        k: int = 5
    ) -> bool:
        """KOK 추천 결과 캐시 저장"""
        try:
            cache_key = self._generate_cache_key(
                "kok_recommendation",
                product_id=product_id,
                k=k
            )

            cache_data = {"recommendations": recommendations}

            success = await self.redis_cache.set_json(
                cache_key,
                cache_data,
                self.cache_ttl["kok_recommendation"],
            )
            if not success:
                return False

            logger.info(f"KOK 추천 캐시 저장: {cache_key}")
            return True

        except Exception as e:
            logger.error(f"KOK 추천 캐시 저장 실패: {e}")
            return False

    async def invalidate_kok_recommendation_cache(self, product_id: Optional[int] = None) -> int:
        """KOK 추천 캐시 무효화"""
        try:
            if product_id is None:
                pattern = "homeshopping:kok_recommendation:*"
            else:
                pattern = f"homeshopping:kok_recommendation:*:product_id:{product_id}"

            deleted_count = await self.redis_cache.delete_pattern(pattern)
            logger.info(f"KOK 추천 캐시 무효화: pattern={pattern}, 삭제된 키 수={deleted_count}")
            return deleted_count

        except Exception as e:
            logger.error(f"KOK 추천 캐시 무효화 실패: {e}")
            return 0

    async def close(self):
        """Redis 연결 종료"""
        await self.redis_cache.close()

# 전역 캐시 매니저 인스턴스
cache_manager = HomeshoppingCacheManager()
