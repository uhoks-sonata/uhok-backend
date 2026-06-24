import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from cachetools import TTLCache

from common.logger import get_logger

logger = get_logger("simple_cache")


class RecipeCache:
    def __init__(self):
        self.cache = TTLCache(maxsize=500, ttl=1800)
        self.search_cache = TTLCache(maxsize=300, ttl=900)
        self.logger = get_logger("recipe_cache")

    def _generate_key(self, user_id, ingredients, amounts, units, combination_number) -> str:
        normalized = sorted(ing.lower().strip() for ing in ingredients)
        amounts = [float(a) for a in amounts] if amounts else [1.0] * len(ingredients)
        units = [u.strip() for u in units] if units else [""] * len(ingredients)
        data = f"{user_id}:{','.join(normalized)}:{','.join(map(str, amounts))}:{','.join(units)}:{combination_number}"
        return hashlib.md5(data.encode()).hexdigest()

    def get_cached_result(self, user_id, ingredients, amounts, units, combination_number) -> Optional[Tuple[List[Dict], int]]:
        key = self._generate_key(user_id, ingredients, amounts, units, combination_number)
        cached = self.cache.get(key)
        if cached:
            self.logger.info(f"캐시 히트: {key[:8]}...")
            return cached["recipes"], cached["total"]
        self.logger.info(f"캐시 미스: {key[:8]}...")
        return None

    def set_cached_result(self, user_id, ingredients, amounts, units, combination_number, recipes, total):
        key = self._generate_key(user_id, ingredients, amounts, units, combination_number)
        self.cache[key] = {"recipes": recipes, "total": total}
        self.logger.info(f"캐시 저장: {key[:8]}... (크기: {len(recipes)})")

    def _generate_search_key(self, query, method, page, size) -> str:
        data = f"search:{query.lower().strip()}:{method}:{page}:{size}"
        return hashlib.md5(data.encode()).hexdigest()

    def get_cached_search(self, query, method, page, size) -> Optional[Dict]:
        key = self._generate_search_key(query, method, page, size)
        return self.search_cache.get(key)

    def set_cached_search(self, query, method, page, size, result: Dict):
        key = self._generate_search_key(query, method, page, size)
        self.search_cache[key] = result

    def get_stats(self) -> Dict[str, Any]:
        return {
            "cache_size": len(self.cache),
            "search_cache_size": len(self.search_cache),
            "max_size": self.cache.maxsize,
            "search_max_size": self.search_cache.maxsize,
            "ttl_seconds": self.cache.ttl,
            "search_ttl_seconds": self.search_cache.ttl,
        }


recipe_cache = RecipeCache()
