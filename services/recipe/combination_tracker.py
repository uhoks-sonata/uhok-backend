"""
조합별 사용된 레시피 추적 시스템
- Redis나 메모리 캐시를 활용하여 사용된 레시피 ID들을 관리
- 각 조합마다 다른 레시피 풀을 사용할 수 있도록 지원
"""

import hashlib
from typing import List, Dict, Optional
import json
from datetime import datetime, timedelta

class CombinationTracker:
    """조합별 사용된 레시피를 추적하는 클래스"""
    
    def __init__(self, use_redis: bool = False, redis_host: str = 'localhost', redis_port: int = 6379):
        self.use_redis = use_redis
        self.memory_cache = {}  # 메모리 캐시 (Redis 대신 사용)
        
        if use_redis:
            try:
                import redis
                self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)
                self.redis_client.ping()  # 연결 테스트
            except Exception as e:
                print(f"Redis 연결 실패, 메모리 캐시로 대체: {e}")
                self.use_redis = False
                self.memory_cache = {}
    
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
        
        if self.use_redis:
            # Redis에 저장
            combination_data = {
                f"combo_{combination_number}": json.dumps(recipe_ids),
                f"combo_{combination_number}_timestamp": datetime.now().isoformat()
            }
            self.redis_client.hset(cache_key, mapping=combination_data)
            self.redis_client.expire(cache_key, 3600)  # 1시간 후 만료
        else:
            # 메모리 캐시에 저장
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
        
        if self.use_redis:
            # Redis에서 조회
            for combo_num in range(1, current_combination):
                combo_key = f"combo_{combo_num}"
                used_ids = self.redis_client.hget(cache_key, combo_key)
                
                if used_ids:
                    try:
                        excluded_ids.extend(json.loads(used_ids))
                    except json.JSONDecodeError:
                        continue
        else:
            # 메모리 캐시에서 조회
            if cache_key in self.memory_cache:
                for combo_num in range(1, current_combination):
                    combo_key = f"combo_{combo_num}"
                    if combo_key in self.memory_cache[cache_key]:
                        excluded_ids.extend(self.memory_cache[cache_key][combo_key])
        
        return list(set(excluded_ids))  # 중복 제거
    
    def clear_user_combinations(self, user_id: int, ingredients_hash: str):
        """사용자의 특정 재료 조합에 대한 추적 데이터 삭제"""
        cache_key = self.get_cache_key(user_id, ingredients_hash)
        
        if self.use_redis:
            self.redis_client.delete(cache_key)
        else:
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
        
        if self.use_redis:
            # Redis에서 조회
            all_data = self.redis_client.hgetall(cache_key)
            result = {}
            for key, value in all_data.items():
                if key.endswith('_timestamp'):
                    result[key] = value.decode()
                else:
                    try:
                        result[key] = json.loads(value.decode())
                    except json.JSONDecodeError:
                        result[key] = value.decode()
            return result
        else:
            # 메모리 캐시에서 조회
            return self.memory_cache.get(cache_key, {})

# 전역 인스턴스 생성
combination_tracker = CombinationTracker(use_redis=False)  # 기본적으로 메모리 캐시 사용
