# backend/services/recommend/ports.py
from typing import Protocol, List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd

class RecommenderPort(Protocol):
    async def recommend_by_recipe_name(self, df: pd.DataFrame, query: str, top_k: int = 25) -> pd.DataFrame:
        """
        레시피명 기반 추천(앱 내 코사인)용 포트.
        - df: RECIPE_ID, VECTOR_NAME[, COOKING_NAME]
        - 반환: 추천 결과 DF (RANK_TYPE 포함)
        """
        ...

class VectorSearcherPort(Protocol):
    async def find_similar_ids(
        self,
        pg_db: AsyncSession,
        query: str,
        top_k: int,
        exclude_ids: Optional[List[int]] = None,
    ) -> List[Tuple[int, float]]:
        """
        pgvector <-> 를 DB에서 실행해 (recipe_id, distance) 리스트를 유사도 순(오름차순)으로 반환한다.
        - query: 검색어(임베딩은 내부에서 수행)
        - top_k: 상위 N개
        - exclude_ids: 제외할 RECIPE_ID 목록
        - 반환: [(recipe_id, distance), ...]
        """
        ...
