"""
홈쇼핑 캐시 관리 유틸리티
- Redis를 활용한 스케줄 데이터 캐싱
- 성능 최적화를 위한 캐시 전략 구현
"""

import json
from datetime import date, datetime
from typing import Dict, List, Optional

import redis.asyncio as redis

from common.logger import get_logger

logger = get_logger("homeshopping_cache")

class HomeshoppingCacheManager:
    """홈쇼핑 캐시 관리자"""
    
    def __init__(self, redis_url: str = "redis://redis:6379/0"):  # Redis URL 형식 (기본값)
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.cache_ttl = {
            "schedule": 7200,  # 2시간 (극도로 긴 캐시)
            "schedule_count": 14400,  # 4시간
            "product_detail": 14400,  # 4시간
            "food_product_ids": 28800,  # 8시간 (식품 ID 목록)
            "kok_recommendation": 3600,  # 1시간 (KOK 추천 결과)
        }
    
    async def get_redis_client(self) -> redis.Redis:
        """Redis 클라이언트 가져오기 (지연 초기화)"""
        if self.redis_client is None:
            try:
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
                # 연결 테스트
                await self.redis_client.ping()
                logger.info("Redis 연결 성공")
            except Exception as e:
                logger.error(f"Redis 연결 실패: {e}")
                # Redis 연결 실패 시 None 반환하여 캐시 비활성화
                return None
        return self.redis_client
    
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
            redis_client = await self.get_redis_client()
            if not redis_client:
                return None
            
            cache_key = self._generate_cache_key(
                "schedule", 
                live_date=live_date.isoformat() if live_date else "all"
            )
            
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                logger.info(f"스케줄 캐시 히트: {cache_key}")
                return data["schedules"]
            
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
            redis_client = await self.get_redis_client()
            if not redis_client:
                return False
            
            cache_key = self._generate_cache_key(
                "schedule", 
                live_date=live_date.isoformat() if live_date else "all"
            )
            
            cache_data = {
                "schedules": schedules,
                "cached_at": datetime.now().isoformat()
            }
            
            await redis_client.setex(
                cache_key, 
                self.cache_ttl["schedule"], 
                json.dumps(cache_data, default=str)
            )
            
            logger.info(f"스케줄 캐시 저장: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"스케줄 캐시 저장 실패: {e}")
            return False
    
    async def invalidate_schedule_cache(self, live_date: Optional[date] = None) -> bool:
        """스케줄 캐시 무효화"""
        try:
            redis_client = await self.get_redis_client()
            if not redis_client:
                return False
            
            # 패턴 매칭으로 관련 캐시 모두 삭제
            pattern = self._generate_cache_key("schedule", live_date=live_date.isoformat() if live_date else "*")
            if live_date:
                # 특정 날짜의 캐시만 삭제
                keys = await redis_client.keys(pattern)
            else:
                # 모든 스케줄 캐시 삭제
                keys = await redis_client.keys("homeshopping:schedule:*")
            
            if keys:
                await redis_client.delete(*keys)
                logger.info(f"스케줄 캐시 무효화: {len(keys)}개 키 삭제")
            
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
            redis_client = await self.get_redis_client()
            if not redis_client:
                return None

            cache_key = self._generate_cache_key(
                "kok_recommendation",
                product_id=product_id,
                k=k
            )

            cached_data = await redis_client.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                logger.info(f"KOK 추천 캐시 히트: {cache_key}")
                return data["recommendations"]

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
            redis_client = await self.get_redis_client()
            if not redis_client:
                return False

            cache_key = self._generate_cache_key(
                "kok_recommendation",
                product_id=product_id,
                k=k
            )

            cache_data = {
                "recommendations": recommendations,
                "cached_at": datetime.now().isoformat()
            }

            await redis_client.setex(
                cache_key,
                self.cache_ttl["kok_recommendation"],
                json.dumps(cache_data, default=str)
            )

            logger.info(f"KOK 추천 캐시 저장: {cache_key}")
            return True

        except Exception as e:
            logger.error(f"KOK 추천 캐시 저장 실패: {e}")
            return False

    async def invalidate_kok_recommendation_cache(self, product_id: Optional[int] = None) -> int:
        """KOK 추천 캐시 무효화"""
        try:
            redis_client = await self.get_redis_client()
            if not redis_client:
                return 0

            if product_id is None:
                pattern = "homeshopping:kok_recommendation:*"
            else:
                pattern = f"homeshopping:kok_recommendation:*:product_id:{product_id}"

            keys = await redis_client.keys(pattern)
            if not keys:
                return 0

            deleted_count = await redis_client.delete(*keys)
            logger.info(f"KOK 추천 캐시 무효화: pattern={pattern}, 삭제된 키 수={deleted_count}")
            return deleted_count

        except Exception as e:
            logger.error(f"KOK 추천 캐시 무효화 실패: {e}")
            return 0

    async def close(self):
        """Redis 연결 종료"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis 연결 종료")

# 전역 캐시 매니저 인스턴스
cache_manager = HomeshoppingCacheManager()
