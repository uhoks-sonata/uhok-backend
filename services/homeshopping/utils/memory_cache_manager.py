"""
홈쇼핑 메모리 캐시 관리 유틸리티
- Redis 없이 메모리 기반 캐싱
- 개발/테스트 환경용
"""

import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import date, datetime, timedelta
from common.logger import get_logger

logger = get_logger("homeshopping_memory_cache")

class MemoryCacheManager:
    """메모리 기반 캐시 관리자"""
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.cache_ttl: Dict[str, float] = {}
        self.cache_ttl_seconds = {
            "schedule": 7200,  # 2시간
            "schedule_count": 14400,  # 4시간
            "product_detail": 14400,  # 4시간
            "food_product_ids": 28800,  # 8시간
            "kok_recommendation": 3600,  # 1시간 (KOK 추천 결과)
        }
    
    def _generate_cache_key(self, cache_type: str, **kwargs) -> str:
        """캐시 키 생성"""
        key_parts = [f"homeshopping:{cache_type}"]
        
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}:{v}")
        
        return ":".join(key_parts)
    
    def _is_expired(self, cache_key: str) -> bool:
        """캐시 만료 여부 확인"""
        if cache_key not in self.cache_ttl:
            return True
        
        return datetime.now().timestamp() > self.cache_ttl[cache_key]
    
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
            
            if cache_key in self.cache and not self._is_expired(cache_key):
                data = self.cache[cache_key]
                logger.info(f"메모리 캐시 히트: {cache_key}")
                return data["schedules"]
            
            logger.info(f"메모리 캐시 미스: {cache_key}")
            return None
            
        except Exception as e:
            logger.error(f"메모리 캐시 조회 실패: {e}")
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
            
            cache_data = {
                "schedules": schedules,
                "cached_at": datetime.now().isoformat()
            }
            
            self.cache[cache_key] = cache_data
            self.cache_ttl[cache_key] = datetime.now().timestamp() + self.cache_ttl_seconds["schedule"]
            
            logger.info(f"메모리 캐시 저장: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"메모리 캐시 저장 실패: {e}")
            return False
    
    async def invalidate_schedule_cache(self, live_date: Optional[date] = None) -> bool:
        """스케줄 캐시 무효화"""
        try:
            pattern = self._generate_cache_key("schedule", live_date=live_date.isoformat() if live_date else "*")
            
            keys_to_remove = []
            for key in self.cache.keys():
                if key.startswith("homeshopping:schedule"):
                    if live_date is None or live_date.isoformat() in key:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                if key in self.cache:
                    del self.cache[key]
                if key in self.cache_ttl:
                    del self.cache_ttl[key]
            
            if keys_to_remove:
                logger.info(f"메모리 캐시 무효화: {len(keys_to_remove)}개 키 삭제")
            
            return True
            
        except Exception as e:
            logger.error(f"메모리 캐시 무효화 실패: {e}")
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
            
            if cache_key in self.cache and not self._is_expired(cache_key):
                data = self.cache[cache_key]
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
            cache_key = self._generate_cache_key(
                "kok_recommendation", 
                product_id=product_id,
                k=k
            )
            
            cache_data = {
                "recommendations": recommendations,
                "cached_at": datetime.now().isoformat()
            }
            
            self.cache[cache_key] = cache_data
            self.cache_ttl[cache_key] = datetime.now().timestamp() + self.cache_ttl_seconds["kok_recommendation"]
            
            logger.info(f"KOK 추천 캐시 저장: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"KOK 추천 캐시 저장 실패: {e}")
            return False

    async def close(self):
        """메모리 캐시 정리"""
        self.cache.clear()
        self.cache_ttl.clear()
        logger.info("메모리 캐시 정리 완료")

# 전역 메모리 캐시 매니저 인스턴스
memory_cache_manager = MemoryCacheManager()
