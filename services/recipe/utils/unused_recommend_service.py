# backend/services/recipe/utils/recommend_service.py
import time
from typing import List, Optional, Tuple

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from .core import recommend_by_recipe_name_core  # 로컬 코사인용
from .ports import RecommenderPort, VectorSearcherPort

# get_model은 ML 서비스로 분리됨
# (import 보강)
# pgvector와 numpy는 ML 서비스로 분리됨

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
        """로컬 모델을 사용한 pgvector 검색 (더 이상 사용하지 않음)
        - 이 클래스는 ML 서비스로 분리되어 더 이상 사용되지 않습니다.
        - 대신 RemoteMLAdapter를 사용하세요.
        """
        logger.warning("DBVectorRecommender는 더 이상 사용되지 않습니다. RemoteMLAdapter를 사용하세요.")
        raise NotImplementedError("로컬 모델은 ML 서비스로 분리되었습니다. ML_MODE=remote_embed로 설정하세요.")


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
    환경 설정에 따라 원격 ML 서비스를 사용하는 검색 어댑터를 반환한다.
    로컬 모델은 ML 서비스로 분리되어 더 이상 사용되지 않습니다.
    """
    import os
    ml_mode = os.getenv("ML_MODE", "remote_embed")  # 기본값을 remote_embed로 변경
    
    if ml_mode == "remote_embed":
        from .remote_ml_adapter import get_remote_ml_searcher
        logger.info("원격 ML 서비스 모드로 벡터 검색 어댑터 사용")
        return await get_remote_ml_searcher()
    else:
        logger.warning(f"ML_MODE='{ml_mode}'는 더 이상 지원되지 않습니다. remote_embed로 설정하세요.")
        logger.info("기본값으로 원격 ML 서비스 모드를 사용합니다.")
        from .remote_ml_adapter import get_remote_ml_searcher
        return await get_remote_ml_searcher()

async def get_recommender() -> RecommenderPort:
    """
    앱 내 코사인(로컬) 어댑터를 반환한다. (필요 시 remote로 교체)
    """
    return LocalRecommender()
