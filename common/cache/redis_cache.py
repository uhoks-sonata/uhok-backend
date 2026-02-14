"""
Shared Redis cache core utilities.

This module centralizes Redis connection management and common JSON cache
operations so domain cache managers can focus on key/TTL policies.
"""

import json
from typing import Any, Optional

import redis.asyncio as redis

from common.logger import get_logger

logger = get_logger("redis_cache_core")


class RedisCacheCore:
    """Shared async Redis cache helper."""

    def __init__(self, redis_url: str, component: str = "cache"):
        self.redis_url = redis_url
        self.component = component
        self.redis_client: Optional[redis.Redis] = None

    async def get_client(self) -> Optional[redis.Redis]:
        """Get Redis client with lazy initialization."""
        if self.redis_client is None:
            try:
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
                await self.redis_client.ping()
                logger.info(f"[{self.component}] Redis 연결 성공")
            except Exception as e:
                logger.error(f"[{self.component}] Redis 연결 실패: {e}")
                return None
        return self.redis_client

    async def get_json(self, key: str) -> Optional[Any]:
        """Read JSON value from Redis key."""
        try:
            client = await self.get_client()
            if not client:
                return None
            cached_data = await client.get(key)
            if not cached_data:
                return None
            return json.loads(cached_data)
        except Exception as e:
            logger.error(f"[{self.component}] Redis get_json 실패: key={key}, error={e}")
            return None

    async def set_json(
        self,
        key: str,
        data: Any,
        ttl: int,
        *,
        ensure_ascii: bool = False,
    ) -> bool:
        """Write JSON value with TTL."""
        try:
            client = await self.get_client()
            if not client:
                return False
            await client.setex(
                key,
                ttl,
                json.dumps(data, ensure_ascii=ensure_ascii, default=str),
            )
            return True
        except Exception as e:
            logger.error(f"[{self.component}] Redis set_json 실패: key={key}, error={e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys that match pattern."""
        try:
            client = await self.get_client()
            if not client:
                return 0
            keys = await client.keys(pattern)
            if not keys:
                return 0
            return await client.delete(*keys)
        except Exception as e:
            logger.error(f"[{self.component}] Redis delete_pattern 실패: pattern={pattern}, error={e}")
            return 0

    async def delete_key(self, key: str) -> int:
        """Delete a single key."""
        try:
            client = await self.get_client()
            if not client:
                return 0
            return await client.delete(key)
        except Exception as e:
            logger.error(f"[{self.component}] Redis delete_key 실패: key={key}, error={e}")
            return 0

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info(f"[{self.component}] Redis 연결 종료")
