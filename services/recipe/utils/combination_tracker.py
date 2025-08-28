"""
조합별 사용된 레시피 추적 시스템
- 메모리 캐시를 활용하여 사용된 레시피 ID들을 관리
- 각 조합마다 다른 레시피 풀을 사용할 수 있도록 지원
- 파일 기반 캐시로 서버 재시작 시에도 데이터 유지
"""

import hashlib
import json
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from common.logger import get_logger

class CombinationTracker:
    """조합별 사용된 레시피를 추적하는 클래스"""
    
    def __init__(self):
        self.logger = get_logger("combination_tracker")
        self.memory_cache = {}  # 메모리 캐시
        self.last_cleanup = datetime.now()  # 마지막 정리 시간 추적
        
        # 캐시 파일 경로 설정
        self.cache_dir = "cache"
        self.cache_file = os.path.join(self.cache_dir, "combination_cache.json")
        
        # 캐시 디렉토리 생성
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 파일에서 캐시 로드
        self._load_cache_from_file()
    
    def _load_cache_from_file(self):
        """파일에서 캐시 데이터를 로드합니다."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.memory_cache = json.load(f)
                self.logger.info(f"파일에서 캐시 데이터 로드: {self.cache_file}")
            except json.JSONDecodeError:
                self.logger.warning(f"파일 디코딩 오류: {self.cache_file}. 빈 딕셔너리로 초기화.")
                self.memory_cache = {}
            except Exception as e:
                self.logger.error(f"파일 로드 중 오류 발생: {e}")
                self.memory_cache = {}
        else:
            self.logger.info(f"파일에서 캐시 데이터를 찾을 수 없습니다: {self.cache_file}. 빈 딕셔너리로 초기화.")
            self.memory_cache = {}

    def _save_cache_to_file(self):
        """메모리 캐시 데이터를 파일에 저장합니다."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory_cache, f, indent=4, ensure_ascii=False)
            self.logger.info(f"캐시 데이터 파일에 저장: {self.cache_file}")
        except Exception as e:
            self.logger.error(f"캐시 데이터 파일 저장 중 오류 발생: {e}")
    
    def generate_ingredients_hash(self, ingredients: List[str], amounts: List[float], units: List[str]) -> str:
        """재료 정보를 해시로 변환하여 캐시 키 생성"""
        data = f"{','.join(ingredients)}_{','.join(map(str, amounts))}_{','.join(units)}"
        hash_result = hashlib.md5(data.encode()).hexdigest()
        self.logger.info(f"재료 해시 생성: {ingredients} -> {hash_result}")
        return hash_result
    
    def get_cache_key(self, user_id: int, ingredients_hash: str) -> str:
        """사용자별 재료별 조합 추적 키 생성"""
        cache_key = f"user:{user_id}:ingredients:{ingredients_hash}:combinations"
        self.logger.info(f"캐시 키 생성: user_id={user_id}, hash={ingredients_hash} -> {cache_key}")
        return cache_key
    
    def track_used_recipes(self, user_id: int, ingredients_hash: str, combination_number: int, recipe_ids: List[int]):
        """특정 조합에서 사용된 레시피 ID들을 저장"""
        cache_key = self.get_cache_key(user_id, ingredients_hash)
        
        if cache_key not in self.memory_cache:
            self.memory_cache[cache_key] = {}
        
        self.memory_cache[cache_key][f"combo_{combination_number}"] = recipe_ids
        self.memory_cache[cache_key][f"combo_{combination_number}_timestamp"] = datetime.now().isoformat()
        
        self.logger.info(f"사용된 레시피 추적: user_id={user_id}, combo={combination_number}, recipe_ids={recipe_ids}")
        self.logger.info(f"현재 캐시 상태: {self.memory_cache[cache_key]}")
        
        # 파일에 저장
        self._save_cache_to_file()
        
        # 주기적으로만 메모리 정리 실행 (10분마다)
        current_time = datetime.now()
        if (current_time - self.last_cleanup) > timedelta(minutes=10):
            self._cleanup_memory_cache()
            self.last_cleanup = current_time
    
    def get_excluded_recipe_ids(self, user_id: int, ingredients_hash: str, current_combination: int) -> List[int]:
        """현재 조합에서 제외해야 할 레시피 ID들 조회 (이전 조합들의 레시피를 제외)"""
        cache_key = self.get_cache_key(user_id, ingredients_hash)
        
        excluded_ids = []
        
        if cache_key in self.memory_cache:
            # 현재 조합보다 낮은 번호의 조합들에서 사용된 레시피들을 제외
            for combo_num in range(1, current_combination):
                combo_key = f"combo_{combo_num}"
                if combo_key in self.memory_cache[cache_key]:
                    excluded_ids.extend(self.memory_cache[cache_key][combo_key])
        
        self.logger.info(f"제외할 레시피 ID 조회: user_id={user_id}, combo={current_combination}, excluded_ids={excluded_ids}")
        return list(set(excluded_ids))  # 중복 제거
    
    def clear_user_combinations(self, user_id: int, ingredients_hash: str):
        """사용자의 특정 재료 조합에 대한 추적 데이터 삭제"""
        cache_key = self.get_cache_key(user_id, ingredients_hash)
        
        if cache_key in self.memory_cache:
            del self.memory_cache[cache_key]
            self.logger.info(f"사용자 조합 데이터 삭제: user_id={user_id}, hash={ingredients_hash}")
            # 파일에 저장
            self._save_cache_to_file()
    
    def _cleanup_memory_cache(self):
        """메모리 캐시에서 만료된 데이터 정리 (6시간 이상 된 데이터만)"""
        current_time = datetime.now()
        expired_keys = []
        
        for cache_key, data in self.memory_cache.items():
            for key, value in data.items():
                if key.endswith('_timestamp'):
                    try:
                        timestamp = datetime.fromisoformat(value)
                        if current_time - timestamp > timedelta(hours=6):
                            expired_keys.append(cache_key)
                            break
                    except ValueError:
                        continue
        
        for key in expired_keys:
            del self.memory_cache[key]
            self.logger.info(f"만료된 캐시 데이터 정리: {key}")
        
        # 파일에 저장
        self._save_cache_to_file()
    
    def get_combination_info(self, user_id: int, ingredients_hash: str) -> Dict:
        """사용자의 조합 정보 조회"""
        cache_key = self.get_cache_key(user_id, ingredients_hash)
        result = self.memory_cache.get(cache_key, {})
        self.logger.info(f"조합 정보 조회: user_id={user_id}, hash={ingredients_hash}, result={result}")
        return result
    
    def get_cache_status(self) -> Dict:
        """전체 캐시 상태 조회 (디버깅용)"""
        return {
            "total_cache_keys": len(self.memory_cache),
            "cache_keys": list(self.memory_cache.keys()),
            "cache_details": self.memory_cache,
            "last_cleanup": self.last_cleanup.isoformat(),
            "cache_file": self.cache_file
        }
    
    def manual_cleanup(self):
        """수동으로 메모리 정리 실행 (디버깅/관리용)"""
        self.logger.info("수동 메모리 정리 시작")
        self._cleanup_memory_cache()
        self.last_cleanup = datetime.now()
        self.logger.info("수동 메모리 정리 완료")


# 전역 인스턴스 생성
combination_tracker = CombinationTracker()
