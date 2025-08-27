"""
조합별 사용된 레시피 추적 시스템
- 메모리 캐시를 활용하여 사용된 레시피 ID들을 관리
- 각 조합마다 다른 레시피 풀을 사용할 수 있도록 지원
"""

import hashlib
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class CombinationTracker:
    """조합별 사용된 레시피를 추적하는 클래스"""
    
    def __init__(self):
        self.memory_cache = {}  # 메모리 캐시
    
    def generate_ingredients_hash(self, ingredients: List[str], amounts: List[float], units: List[str]) -> str:
        """재료 정보를 해시로 변환하여 캐시 키 생성"""
        data = f"{','.join(ingredients)}_{','.join(map(str, amounts))}_{','.join(units)}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def get_cache_key(self, user_id: int, ingredients_hash: str) -> str:
        """사용자별 재료별 조합 추적 키 생성"""
        return f"user:{user_id}:ingredients:{ingredients_hash}:combinations"
    
    def track_used_recipes(self, user_id: int, ingredients_hash: str, combination_number: int, recipe_ids: List[int]):
        """특정 조합에서 사용된 레시피 ID들을 저장"""
        cache_key = self.get_cache_key(user_id, ingredients_hash)
        
        if cache_key not in self.memory_cache:
            self.memory_cache[cache_key] = {}
        
        self.memory_cache[cache_key][f"combo_{combination_number}"] = recipe_ids
        self.memory_cache[cache_key][f"combo_{combination_number}_timestamp"] = datetime.now().isoformat()
        
        # 메모리 정리 (1시간 이상 된 데이터 삭제)
        self._cleanup_memory_cache()
    
    def get_excluded_recipe_ids(self, user_id: int, ingredients_hash: str, current_combination: int) -> List[int]:
        """현재 조합에서 제외해야 할 레시피 ID들 조회"""
        cache_key = self.get_cache_key(user_id, ingredients_hash)
        
        excluded_ids = []
        
        if cache_key in self.memory_cache:
            for combo_num in range(1, current_combination):
                combo_key = f"combo_{combo_num}"
                if combo_key in self.memory_cache[cache_key]:
                    excluded_ids.extend(self.memory_cache[cache_key][combo_key])
        
        return list(set(excluded_ids))  # 중복 제거
    
    def clear_user_combinations(self, user_id: int, ingredients_hash: str):
        """사용자의 특정 재료 조합에 대한 추적 데이터 삭제"""
        cache_key = self.get_cache_key(user_id, ingredients_hash)
        
        if cache_key in self.memory_cache:
            del self.memory_cache[cache_key]
    
    def _cleanup_memory_cache(self):
        """메모리 캐시에서 만료된 데이터 정리"""
        current_time = datetime.now()
        expired_keys = []
        
        for cache_key, data in self.memory_cache.items():
            for key, value in data.items():
                if key.endswith('_timestamp'):
                    try:
                        timestamp = datetime.fromisoformat(value)
                        if current_time - timestamp > timedelta(hours=1):
                            expired_keys.append(cache_key)
                            break
                    except ValueError:
                        continue
        
        for key in expired_keys:
            del self.memory_cache[key]
    
    def get_combination_info(self, user_id: int, ingredients_hash: str) -> Dict:
        """사용자의 조합 정보 조회"""
        cache_key = self.get_cache_key(user_id, ingredients_hash)
        return self.memory_cache.get(cache_key, {})


# 전역 인스턴스 생성
combination_tracker = CombinationTracker()
