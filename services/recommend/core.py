import asyncio
from typing import Optional
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from common.logger import get_logger

logger = get_logger("recommend_core")

_model: Optional[SentenceTransformer] = None
_model_lock = asyncio.Lock()

async def get_model() -> SentenceTransformer:
    """
    SentenceTransformer 임베딩 모델을 전역 캐시하여 반환한다.
    - 최초 1회만 로드하며 동시 호출은 Lock으로 보호한다.
    - 모델: paraphrase-multilingual-MiniLM-L12-v2 (384차원)
    """
    global _model
    if _model is not None:
        logger.debug("캐시된 SentenceTransformer 모델 사용 중")
        return _model
    async with _model_lock:
        if _model is None:
            logger.info("SentenceTransformer 모델 로드 중: paraphrase-multilingual-MiniLM-L12-v2")
            try:
                _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
                logger.info("SentenceTransformer 모델 로드 완료")
            except Exception as e:
                logger.error(f"SentenceTransformer 모델 로드 실패: {str(e)}")
                raise
        else:
            logger.debug("다른 코루틴에서 모델 로드 완료")
    return _model

async def recommend_by_recipe_name_core(df: pd.DataFrame, query: str, top_k: int = 25) -> pd.DataFrame:
    """
    레시피명 기반 추천 (하이브리드: 제목 일치 우선 + 임베딩 유사도 보완)
    - 입력 df: 최소 ['RECIPE_ID','VECTOR_NAME'] 필요, 있으면 'COOKING_NAME' 사용
    - 반환: RANK_TYPE(0=일치, 1=유사도) 포함 DataFrame
    """
    logger.info(f"레시피 추천 시작: query='{query}', top_k={top_k}, df={len(df)}행")

    if "RECIPE_ID" not in df.columns:
        raise ValueError("입력 df에 'RECIPE_ID' 컬럼이 필요합니다.")

    try:
        model = await get_model()
        query_vec = model.encode(query, normalize_embeddings=True)
        logger.debug(f"쿼리 인코딩 완료, shape={np.array(query_vec).shape}")

        # [1] COOKING_NAME 부분/정확 일치 우선
        if "COOKING_NAME" in df.columns:
            exact_df = df[df["COOKING_NAME"].astype(str).str.contains(query, case=False, na=False)].copy()
            exact_df["RANK_TYPE"] = 0
            exact_k = min(len(exact_df), top_k)
            exact_df = exact_df.head(exact_k)
            seen_ids = set(exact_df["RECIPE_ID"])
            logger.info(f"제목 일치 {len(exact_df)}개")
        else:
            exact_df = pd.DataFrame()
            seen_ids = set()
            exact_k = 0
            logger.warning("COOKING_NAME 컬럼 없음 → 유사도만 사용")

        # [2] 임베딩 유사도 보완
        remaining_k = top_k - exact_k
        similar_df = pd.DataFrame()
        if remaining_k > 0 and "VECTOR_NAME" in df.columns:
            rest = df[~df["RECIPE_ID"].isin(seen_ids)].copy()
            if not rest.empty:
                def to_vec(s: Optional[str]) -> np.ndarray:
                    """
                    '1.0,2.0,...' 문자열을 numpy 벡터로 변환한다. 실패 시 384차원 영벡터.
                    """
                    if not s:
                        return np.zeros(384, dtype=float)
                    try:
                        return np.array(list(map(float, str(s).split(","))), dtype=float)
                    except Exception:
                        return np.zeros(384, dtype=float)

                rest["VECTOR_ARRAY"] = rest["VECTOR_NAME"].apply(to_vec)
                rest["SIMILARITY"] = rest["VECTOR_ARRAY"].apply(
                    lambda v: float(cosine_similarity([query_vec], [v])[0][0]) if v is not None else 0.0
                )
                similar_df = rest.sort_values(by="SIMILARITY", ascending=False).head(remaining_k)
                similar_df["RANK_TYPE"] = 1
                logger.info(f"유사도 보완 {len(similar_df)}개")
        else:
            logger.debug("유사도 보완 없이 종료")

        # [3] 합치기 + 정리
        out = pd.concat([exact_df, similar_df], ignore_index=True)
        if not out.empty and "VECTOR_ARRAY" in out.columns:
            out = out.drop(columns=["VECTOR_ARRAY"])
        if not out.empty:
            out = out.drop_duplicates(subset=["RECIPE_ID"]).sort_values(by="RANK_TYPE").reset_index(drop=True)
        else:
            logger.warning("최종 추천 결과 없음")

        return out

    except Exception as e:
        logger.error(f"레시피 추천 실패: query='{query}', error={str(e)}")
        raise
