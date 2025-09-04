"""
간단한 메모리 캐싱 시스템
- 기존 로직을 변경하지 않고 성능만 향상
- LRU 캐시를 사용하여 메모리 효율성 확보
"""

from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
import hashlib
import json
from collections import OrderedDict
from common.logger import get_logger

logger = get_logger("simple_cache")

class SimpleLRUCache:
    """간단한 LRU 캐시 구현"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache = OrderedDict()
        self.timestamps = {}
    
    def _is_expired(self, key: str) -> bool:
        """캐시가 만료되었는지 확인"""
        if key not in self.timestamps:
            return True
        return datetime.now() - self.timestamps[key] > timedelta(seconds=self.ttl_seconds)
    
    def _cleanup_expired(self):
        """만료된 캐시 항목들 정리"""
        current_time = datetime.now()
        expired_keys = []
        
        for key, timestamp in self.timestamps.items():
            if current_time - timestamp > timedelta(seconds=self.ttl_seconds):
                expired_keys.append(key)
        
        for key in expired_keys:
            self.cache.pop(key, None)
            self.timestamps.pop(key, None)
    
    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        if key not in self.cache or self._is_expired(key):
            return None
        
        # LRU: 사용된 항목을 맨 뒤로 이동
        value = self.cache.pop(key)
        self.cache[key] = value
        return value
    
    def set(self, key: str, value: Any):
        """캐시에 값 저장"""
        # 만료된 항목들 정리
        self._cleanup_expired()
        
        # 캐시 크기 초과 시 가장 오래된 항목 제거
        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            self.cache.pop(oldest_key)
            self.timestamps.pop(oldest_key, None)
        
        # 새 항목 추가
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
    
    def clear(self):
        """캐시 전체 삭제"""
        self.cache.clear()
        self.timestamps.clear()
    
    def size(self) -> int:
        """현재 캐시 크기"""
        return len(self.cache)


class RecipeCache:
    """레시피 추천 결과 캐싱"""
    
    def __init__(self):
        self.cache = SimpleLRUCache(max_size=200, ttl_seconds=1800)  # 30분 TTL
        self.logger = get_logger("recipe_cache")
    
    def _generate_key(self, 
                     user_id: int, 
                     ingredients: List[str], 
                     amounts: List[float], 
                     units: List[str], 
                     combination_number: int) -> str:
        """캐시 키 생성"""
        # 재료 정보 정규화
        normalized_ingredients = sorted([ing.lower().strip() for ing in ingredients])
        normalized_amounts = [float(amt) for amt in amounts] if amounts else [1.0] * len(ingredients)
        normalized_units = [unit.strip() for unit in units] if units else [""] * len(ingredients)
        
        # 해시 생성
        data = f"{user_id}:{','.join(normalized_ingredients)}:{','.join(map(str, normalized_amounts))}:{','.join(normalized_units)}:{combination_number}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def get_cached_result(self, 
                         user_id: int, 
                         ingredients: List[str], 
                         amounts: List[float], 
                         units: List[str], 
                         combination_number: int) -> Optional[Tuple[List[Dict], int]]:
        """캐시된 결과 조회"""
        try:
            cache_key = self._generate_key(user_id, ingredients, amounts, units, combination_number)
            cached_data = self.cache.get(cache_key)
            
            if cached_data:
                self.logger.info(f"캐시 히트: {cache_key[:8]}...")
                return cached_data.get('recipes', []), cached_data.get('total', 0)
            
            self.logger.info(f"캐시 미스: {cache_key[:8]}...")
            return None
            
        except Exception as e:
            self.logger.error(f"캐시 조회 중 오류: {e}")
            return None
    
    def set_cached_result(self, 
                         user_id: int, 
                         ingredients: List[str], 
                         amounts: List[float], 
                         units: List[str], 
                         combination_number: int, 
                         recipes: List[Dict], 
                         total: int):
        """결과를 캐시에 저장"""
        try:
            cache_key = self._generate_key(user_id, ingredients, amounts, units, combination_number)
            cache_data = {
                'recipes': recipes,
                'total': total,
                'cached_at': datetime.now().isoformat()
            }
            
            self.cache.set(cache_key, cache_data)
            self.logger.info(f"캐시 저장: {cache_key[:8]}... (크기: {len(recipes)})")
            
        except Exception as e:
            self.logger.error(f"캐시 저장 중 오류: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        return {
            "cache_size": self.cache.size(),
            "max_size": self.cache.max_size,
            "ttl_seconds": self.cache.ttl_seconds
        }


# 전역 캐시 인스턴스
recipe_cache = RecipeCache()
