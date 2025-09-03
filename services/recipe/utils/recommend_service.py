# backend/services/recipe/utils/recommend_service.py
from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from .ports import VectorSearcherPort, RecommenderPort
from .core import get_model
import pandas as pd
from .core import recommend_by_recipe_name_core  # 로컬 코사인용
from common.logger import get_logger
import time
# (import 보강)
from sqlalchemy import text, bindparam
from pgvector.sqlalchemy import Vector  # ← 추가
import numpy as np

logger = get_logger(__name__)

EMBEDDING_DIM = 384
VECTOR_COL = '"VECTOR_NAME"'  # ← 현재 테이블 정의에 맞춤

class DBVectorRecommender(VectorSearcherPort):
    async def find_similar_ids(
        self,
        pg_db: AsyncSession,
        query: str,
        top_k: int,
        exclude_ids: Optional[List[int]] = None,
    ) -> List[Tuple[int, float]]:
        """pgvector <-> 연산자로 DB에서 유사 레시피를 조회한다(비동기).
        - 입력: query(문자열), top_k, exclude_ids(제외할 RECIPE_ID 목록)
        - 처리: query를 임베딩 → :qv 를 Vector(384) 타입으로 바인딩
        - 전제: RECIPE_VECTOR_TABLE."VECTOR_NAME" 이 vector(384) 이어야 함
        - 반환: [(recipe_id, distance)]  # distance가 작을수록 유사
        """
        start_time = time.time()

        # 1) 임베딩 생성
        model_t0 = time.time()
        model = await get_model()
        model_loading_time = time.time() - model_t0

        enc_t0 = time.time()
        query_vec_np: np.ndarray = model.encode(query, normalize_embeddings=True)
        query_vec: List[float] = [float(x) for x in query_vec_np.tolist()]  # list[float]
        encoding_time = time.time() - enc_t0

        # 2) SQL 준비
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
                bindparam("qv", type_=Vector(EMBEDDING_DIM)),  # ★ vector로 바인딩
                bindparam("ex_ids", expanding=True),           # ★ 리스트 안전 확장
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
                bindparam("qv", type_=Vector(EMBEDDING_DIM)),  # ★ vector로 바인딩
                bindparam("k")
            )
            params = {"qv": query_vec, "k": int(top_k)}

        logger.debug(f"임베딩 차원={len(query_vec)}, top_k={top_k}, exclude={len(exclude_ids) if exclude_ids else 0}")

        # 3) DB 실행
        db_t0 = time.time()
        rows = (await pg_db.execute(sql, params)).all()
        db_execution_time = time.time() - db_t0

        # 4) 결과 정리
        result: List[Tuple[int, float]] = [(int(r.recipe_id), float(r.distance)) for r in rows]

        # 5) 로깅
        total = time.time() - start_time
        logger.info(
            f"find_similar_ids 완료: query='{query}', top_k={top_k}, exclude={len(exclude_ids) if exclude_ids else 0}, "
            f"총 {total:.3f}s (모델 {model_loading_time:.3f}s, 인코딩 {encoding_time:.3f}s, 쿼리 {db_execution_time:.3f}s), "
            f"결과 {len(result)}건"
        )
        return result


class LocalRecommender(RecommenderPort):
    async def recommend_by_recipe_name(self, df: pd.DataFrame, query: str, top_k: int = 25) -> pd.DataFrame:
        """
        앱 내 코사인 유사도(로컬 임베딩)로 보완 추천을 수행한다.
        """
        # 기능 시간 체크 시작
        start_time = time.time()
        
        logger.info(f"LocalRecommender 추천 시작: query='{query}', top_k={top_k}, df={len(df)}행")
        
        result = await recommend_by_recipe_name_core(df=df, query=query, top_k=top_k)
        
        # 기능 시간 체크 완료 및 로깅
        execution_time = time.time() - start_time
        logger.info(f"LocalRecommender 추천 완료: query='{query}', top_k={top_k}, 실행시간={execution_time:.3f}초, 결과수={len(result)}")
        
        return result

async def get_db_vector_searcher() -> VectorSearcherPort:
    """
    DB(pgvector) 기반 검색 어댑터를 반환한다.
    """
    return DBVectorRecommender()

async def get_recommender() -> RecommenderPort:
    """
    앱 내 코사인(로컬) 어댑터를 반환한다. (필요 시 remote로 교체)
    """
    return LocalRecommender()
