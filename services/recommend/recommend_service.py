import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from common.logger import get_logger

logger = get_logger("recommend_service")

_model = None

async def get_model():
    """
    SentenceTransformer 임베딩 모델을 전역 캐싱 후 반환 (최초 1회 로드)
    """
    global _model
    if _model is None:
        logger.info("SentenceTransformer 모델 로드 중: paraphrase-multilingual-MiniLM-L12-v2")
        try:
            _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
            logger.info("SentenceTransformer 모델 로드 완료")
        except Exception as e:
            logger.error(f"SentenceTransformer 모델 로드 실패: {str(e)}")
            raise
    else:
        logger.debug("캐시된 SentenceTransformer 모델 사용 중")
    return _model

async def _get_recipe_recommendations(df: pd.DataFrame, query: str, top_k: int = 25) -> pd.DataFrame:
    """
    레시피명 기반 추천 로직 (내부용)
    - 레시피명 일치 우선 + 벡터 유사도 기반 하이브리드 추천
    """
    logger.info(f"레시피 추천 시작: 검색어='{query}', 상위 {top_k}개, 데이터프레임 크기={len(df)}")
    
    try:
        model = await get_model()
        query_vec = model.encode(query, normalize_embeddings=True)
        logger.debug(f"쿼리 인코딩 완료, 벡터 형태: {query_vec.shape}")

        # [1] 레시피명 일치 우선 필터 (MariaDB 스타일)
        # COOKING_NAME 컬럼이 없으면 벡터 유사도만 사용
        if "COOKING_NAME" in df.columns:
            exact_df = df[df["COOKING_NAME"].str.contains(query, case=False, na=False)].copy()
            exact_df["RANK_TYPE"] = 0  # 0은 '일치'를 의미
            exact_k = min(len(exact_df), top_k)
            exact_df = exact_df.head(exact_k)
            seen_ids = set(exact_df["RECIPE_ID"])
            logger.info(f"정확한 일치 발견: {len(exact_df)}개 레시피")
        else:
            # COOKING_NAME이 없으면 벡터 유사도만 사용
            exact_df = pd.DataFrame()
            seen_ids = set()
            exact_k = 0
            logger.warning("COOKING_NAME 컬럼을 찾을 수 없음, 벡터 유사도만 사용")

        # [2] 임베딩 벡터 기반 유사도 추천 (PostgreSQL + pgvector 스타일)
        remaining_k = top_k - exact_k
        similar_df = pd.DataFrame()
        
        if remaining_k > 0:
            remaining_df = df[~df["RECIPE_ID"].isin(seen_ids)].copy()
            if not remaining_df.empty:
                logger.debug(f"벡터 유사도 계산을 위해 {len(remaining_df)}개 레시피 처리 중")
                # 벡터 유사도 계산
                remaining_df["VECTOR_ARRAY"] = remaining_df["VECTOR_NAME"].apply(
                    lambda x: np.array(list(map(float, x.split(',')))) if x else np.zeros(384)
                )
                remaining_df["SIMILARITY"] = remaining_df["VECTOR_ARRAY"].apply(
                    lambda vec: cosine_similarity([query_vec], [vec])[0][0]
                )
                similar_df = remaining_df.sort_values(by="SIMILARITY", ascending=False).head(remaining_k)
                similar_df["RANK_TYPE"] = 1  # 1은 '추천'을 의미
                logger.info(f"벡터 유사도 기반 추천: {len(similar_df)}개 레시피")
            else:
                logger.debug("벡터 유사도 계산을 위한 남은 레시피 없음")
        else:
            logger.debug("벡터 유사도 추천을 위한 남은 슬롯 없음")

        # [3] 두 결과를 합치고 중복 제거
        final_result_df_base = pd.concat([exact_df, similar_df], ignore_index=True)
        if not final_result_df_base.empty:
            final_result_df_base = final_result_df_base.drop_duplicates(subset=["RECIPE_ID"]).sort_values(by="RANK_TYPE").reset_index(drop=True)
            logger.info(f"최종 추천 결과: {len(final_result_df_base)}개 레시피 (정확한 일치: {exact_k}개, 유사도 기반: {len(similar_df)}개)")
        else:
            logger.warning("최종 추천 결과에서 레시피를 찾을 수 없음")
        
        return final_result_df_base
        
    except Exception as e:
        logger.error(f"레시피 추천 실패: 검색어='{query}', 오류={str(e)}")
        raise
