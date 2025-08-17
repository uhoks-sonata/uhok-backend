# backend/services/recommend/recommend_service.py
from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from services.recommend.ports import VectorSearcherPort, RecommenderPort
from services.recommend.core import get_model
import pandas as pd
from services.recommend.core import recommend_by_recipe_name_core  # 로컬 코사인용
from common.logger import get_logger
import time

logger = get_logger("recommend_service")

class DBVectorRecommender(VectorSearcherPort):
    async def find_similar_ids(
        self,
        pg_db: AsyncSession,
        query: str,
        top_k: int,
        exclude_ids: Optional[List[int]] = None,
    ) -> List[Tuple[int, float]]:
        """
        pgvector <-> 를 사용해 DB에서 유사 레시피를 찾는다.
        - 거리(distance) 낮을수록 유사.
        """
        # 기능 시간 체크 시작
        start_time = time.time()
        
        # 모델 로딩 시간 체크
        model_start_time = time.time()
        model = await get_model()
        model_loading_time = time.time() - model_start_time
        
        # 쿼리 인코딩 시간 체크
        encoding_start_time = time.time()
        query_vec = model.encode(query, normalize_embeddings=True).tolist()
        encoding_time = time.time() - encoding_start_time

        if exclude_ids:
            placeholders = ",".join([f":ex{i}" for i in range(len(exclude_ids))])
            where_not_in = f'WHERE "RECIPE_ID" NOT IN ({placeholders})'
        else:
            where_not_in = ""

        sql = text(f"""
            SELECT "RECIPE_ID", "VECTOR_NAME" <-> :qv AS distance
            FROM "RECIPE_VECTOR_TABLE"
            {where_not_in}
            ORDER BY distance ASC
            LIMIT :k
        """)

        params = {"qv": query_vec, "k": int(top_k)}
        if exclude_ids:
            for i, rid in enumerate(exclude_ids):
                params[f"ex{i}"] = int(rid)

        # DB 쿼리 실행 시간 체크
        db_start_time = time.time()
        rows = (await pg_db.execute(sql, params)).all()
        db_execution_time = time.time() - db_start_time
        
        result = [(rid, float(dist)) for rid, dist in rows]
        
        # 기능 시간 체크 완료 및 로깅
        execution_time = time.time() - start_time
        logger.info(f"find_similar_ids 완료: query='{query}', top_k={top_k}, exclude_ids_count={len(exclude_ids) if exclude_ids else 0}, 전체실행시간={execution_time:.3f}초, 모델로딩={model_loading_time:.3f}초, 인코딩={encoding_time:.3f}초, DB쿼리={db_execution_time:.3f}초, 결과수={len(result)}")
        
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
