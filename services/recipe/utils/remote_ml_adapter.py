"""
원격 ML 서비스 호출 어댑터
백엔드에서 ML Inference 서비스와 통신하는 모듈입니다.
"""

import os
import httpx
import asyncio
from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam
from .ports import VectorSearcherPort
from common.logger import get_logger
import time

logger = get_logger("remote_ml_adapter")

# 환경 변수에서 ML 서비스 설정 가져오기
ML_INFERENCE_URL = os.getenv("ML_INFERENCE_URL")
ML_TIMEOUT = float(os.getenv("ML_TIMEOUT", "10.0"))
ML_RETRIES = int(os.getenv("ML_RETRIES", "2"))
EMBEDDING_DIM = 384
VECTOR_COL = '"VECTOR_NAME"'


class RemoteMLAdapter(VectorSearcherPort):
    """
    원격 ML 서비스에서 임베딩을 받아 PostgreSQL(pgvector)로 유사도 검색을 수행하는 어댑터
    """
    
    async def find_similar_ids(
        self,
        pg_db: AsyncSession,
        query: str,
        top_k: int,
        exclude_ids: Optional[List[int]] = None,
    ) -> List[Tuple[int, float]]:
        """
        원격 ML 서버에서 쿼리 임베딩을 받고, 로컬 PostgreSQL(pgvector)의 <->로 유사 Top-K를 조회한다.
        
        Args:
            pg_db: PostgreSQL 세션
            query: 검색 쿼리 텍스트
            top_k: 반환할 상위 결과 수
            exclude_ids: 제외할 RECIPE_ID 목록
            
        Returns:
            (recipe_id, distance) 리스트
        """
        start_time = time.time()
        
        try:
            # 1) 원격 ML 서비스에서 임베딩 생성
            embedding_start_time = time.time()
            query_vec = await self._get_embedding_from_ml_service(query)
            embedding_time = time.time() - embedding_start_time
            
            # 2) PostgreSQL에서 유사도 검색
            db_start_time = time.time()
            result = await self._search_similar_in_db(
                pg_db, query_vec, top_k, exclude_ids
            )
            db_time = time.time() - db_start_time
            
            total_time = time.time() - start_time
            logger.info(
                f"RemoteMLAdapter 검색 완료: query='{query}', top_k={top_k}, "
                f"exclude={len(exclude_ids) if exclude_ids else 0}, "
                f"총 {total_time:.3f}s (임베딩 {embedding_time:.3f}s, DB {db_time:.3f}s), "
                f"결과 {len(result)}건"
            )
            
            return result
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(
                f"RemoteMLAdapter 검색 실패: query='{query}', "
                f"실행시간={total_time:.3f}초, error={str(e)}"
            )
            raise
    
    async def _get_embedding_from_ml_service(self, text: str) -> List[float]:
        """
        원격 ML 서비스에서 텍스트 임베딩을 가져옵니다.
        
        Args:
            text: 임베딩할 텍스트
            
        Returns:
            임베딩 벡터 (list of float)
        """
        url = f"{ML_INFERENCE_URL}/api/v1/embed"
        payload = {"text": text, "normalize": True}
        logger.info(f"ML 서비스 호출: URL={url}")
        
        async with httpx.AsyncClient(timeout=ML_TIMEOUT) as client:
            for attempt in range(ML_RETRIES + 1):
                try:
                    logger.info(f"ML 서비스 호출 시도 {attempt + 1}: {url}")
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    
                    data = response.json()
                    embedding = data.get("embedding")
                    
                    if not embedding or len(embedding) != EMBEDDING_DIM:
                        raise ValueError(f"Invalid embedding dimension: {len(embedding) if embedding else 0}")
                    
                    return embedding
                    
                except httpx.TimeoutException:
                    if attempt < ML_RETRIES:
                        logger.warning(f"ML 서비스 타임아웃, 재시도 {attempt + 1}/{ML_RETRIES}")
                        await asyncio.sleep(0.5 * (attempt + 1))  # 지수 백오프
                        continue
                    else:
                        logger.error(f"ML 서비스 타임아웃, 최대 재시도 횟수 초과")
                        raise
                        
                except httpx.HTTPStatusError as e:
                    logger.error(f"ML 서비스 HTTP 에러: {e.response.status_code} - {e.response.text}")
                    raise
                    
                except Exception as e:
                    logger.error(f"ML 서비스 호출 실패: {str(e)}")
                    raise
    
    async def _search_similar_in_db(
        self,
        pg_db: AsyncSession,
        query_vec: List[float],
        top_k: int,
        exclude_ids: Optional[List[int]] = None,
    ) -> List[Tuple[int, float]]:
        """
        PostgreSQL에서 pgvector를 사용하여 유사도 검색을 수행합니다.
        
        Args:
            pg_db: PostgreSQL 세션
            query_vec: 쿼리 임베딩 벡터
            top_k: 반환할 상위 결과 수
            exclude_ids: 제외할 RECIPE_ID 목록
            
        Returns:
            (recipe_id, distance) 리스트
        """
        if exclude_ids:
            sql = text(f"""
                SELECT "RECIPE_ID" AS recipe_id,
                       {VECTOR_COL} <-> :qv AS distance
                FROM "RECIPE_VECTOR_TABLE"
                WHERE "RECIPE_ID" NOT IN :ex_ids
                ORDER BY distance ASC
                LIMIT :k
            """
            ).bindparams(
                bindparam("qv", type_=Vector(EMBEDDING_DIM)),
                bindparam("ex_ids", expanding=True),
                bindparam("k")
            )
            params = {
                "qv": query_vec,
                "ex_ids": [int(i) for i in exclude_ids],
                "k": int(top_k),
            }
        else:
            sql = text(f"""
                SELECT "RECIPE_ID" AS recipe_id,
                       {VECTOR_COL} <-> :qv AS distance
                FROM "RECIPE_VECTOR_TABLE"
                ORDER BY distance ASC
                LIMIT :k
            """
            ).bindparams(
                bindparam("qv", type_=Vector(EMBEDDING_DIM)),
                bindparam("k")
            )
            params = {"qv": query_vec, "k": int(top_k)}
        
        rows = (await pg_db.execute(sql, params)).all()
        return [(int(r.recipe_id), float(r.distance)) for r in rows]


class MLServiceHealthChecker:
    """ML 서비스 상태 확인 클래스"""
    
    @staticmethod
    async def check_health() -> dict:
        """
        ML 서비스의 상태를 확인합니다.
        
        Returns:
            상태 정보 딕셔너리
        """
        try:
            url = f"{ML_INFERENCE_URL}/health"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"ML 서비스 헬스체크 실패: {str(e)}")
            return {"status": "error", "error": str(e)}


# 팩토리 함수
async def get_remote_ml_searcher() -> VectorSearcherPort:
    """
    원격 ML 서비스를 사용하는 벡터 검색 어댑터를 반환합니다.
    """
    return RemoteMLAdapter()
