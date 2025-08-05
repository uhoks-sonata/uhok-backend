import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

_model = None

async def get_model():
    """
    SentenceTransformer 임베딩 모델을 전역 캐싱 후 반환 (최초 1회 로드)
    """
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
    return _model

async def _get_recipe_recommendations(df: pd.DataFrame, query: str, top_k: int = 25) -> pd.DataFrame:
    """
    레시피명 기반 추천 로직 (내부용)
    """
    model = await get_model()
    query_vec = model.encode(query, normalize_embeddings=True)

    # [1] 레시피명 일치 우선 필터
    exact_df = df[df["COOKING_NAME"].str.contains(query, case=False, na=False)].copy()
    exact_df["RANK_TYPE"] = 0
    exact_k = min(len(exact_df), top_k)
    exact_df = exact_df.head(exact_k)
    seen_ids = set(exact_df["RECIPE_ID"])

    # [2] 임베딩 유사도 기반 잔여 추천
    remaining_k = top_k - exact_k
    similar_df = pd.DataFrame(columns=df.columns)
    if remaining_k > 0:
        remaining_df = df[~df["RECIPE_ID"].isin(seen_ids)].copy()
        if not remaining_df.empty:
            remaining_df["VECTOR_ARRAY"] = remaining_df["VECTOR_NAME"].apply(
                lambda x: np.array(list(map(float, x.split(','))))
            )
            remaining_df["SIMILARITY"] = remaining_df["VECTOR_ARRAY"].apply(
                lambda vec: cosine_similarity([query_vec], [vec])[0][0]
            )
            similar_df = remaining_df.sort_values(by="SIMILARITY", ascending=False).head(remaining_k)
    similar_df["RANK_TYPE"] = 1

    # [3] 결과 합치기
    final_result_df_base = pd.concat([exact_df, similar_df], ignore_index=True)
    final_result_df_base = final_result_df_base.sort_values(by="RANK_TYPE").reset_index(drop=True)
    return final_result_df_base
