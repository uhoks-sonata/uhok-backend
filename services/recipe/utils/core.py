import pandas as pd
import numpy as np
import time
from common.logger import get_logger

logger = get_logger("recommend_core")

# 모델 관련 코드는 ML 서비스로 분리됨
# sklearn도 ML 서비스로 분리되어 더 이상 사용하지 않음

async def recommend_by_recipe_name_core(df: pd.DataFrame, query: str, top_k: int = 25) -> pd.DataFrame:
    """
    레시피명 기반 추천 (제목 일치 우선 + 기존 임베딩 유사도 보완)
    - 입력 df: 최소 ['RECIPE_ID','VECTOR_NAME'] 필요, 있으면 'COOKING_NAME' 사용
    - 반환: RANK_TYPE(0=일치, 1=유사도) 포함 DataFrame
    - 주의: 이 함수는 기존 임베딩만 사용하며, 새로운 쿼리 임베딩은 생성하지 않음
    """
    # 기능 시간 체크 시작
    start_time = time.time()
    
    logger.info(f"레시피 추천 시작: query='{query}', top_k={top_k}, df={len(df)}행")

    if "RECIPE_ID" not in df.columns:
        raise ValueError("입력 df에 'RECIPE_ID' 컬럼이 필요합니다.")

    try:
        # 쿼리 임베딩은 ML 서비스에서 생성되어야 함
        # 이 함수는 기존 임베딩만 사용하여 유사도 계산
        logger.warning("로컬 코사인 유사도 계산: 쿼리 임베딩이 제공되지 않음. 제목 일치만 수행합니다.")

        # [1] COOKING_NAME 부분/정확 일치만 수행 (임베딩 유사도는 ML 서비스에서 처리)
        exact_start_time = time.time()
        if "COOKING_NAME" in df.columns:
            exact_df = df[df["COOKING_NAME"].astype(str).str.contains(query, case=False, na=False)].copy()
            exact_df["RANK_TYPE"] = 0
            exact_k = min(len(exact_df), top_k)
            exact_df = exact_df.head(exact_k)
            exact_time = time.time() - exact_start_time
            logger.info(f"제목 일치 {len(exact_df)}개, 처리시간={exact_time:.3f}초")
        else:
            exact_df = pd.DataFrame()
            exact_k = 0
            exact_time = time.time() - exact_start_time
            logger.warning("COOKING_NAME 컬럼 없음 → 결과 없음, 처리시간={exact_time:.3f}초")

        # [2] 임베딩 유사도는 ML 서비스에서 처리되므로 여기서는 제외
        logger.info("임베딩 유사도 계산은 ML 서비스에서 처리됩니다.")
        
        # [3] 결과 정리
        merge_start_time = time.time()
        out = exact_df.copy()
        if not out.empty:
            out = out.drop_duplicates(subset=["RECIPE_ID"]).sort_values(by="RANK_TYPE").reset_index(drop=True)
        else:
            logger.warning("최종 추천 결과 없음 (제목 일치만 수행)")
        
        merge_time = time.time() - merge_start_time
        
        # 전체 실행 시간 체크 완료 및 로깅
        total_execution_time = time.time() - start_time
        logger.info(f"로컬 레시피 추천 완료: query='{query}', top_k={top_k}, 전체실행시간={total_execution_time:.3f}초, 정확일치={exact_time:.3f}초, 병합={merge_time:.3f}초, 결과수={len(out)}")

        return out

    except Exception as e:
        total_execution_time = time.time() - start_time
        logger.error(f"로컬 레시피 추천 실패: query='{query}', 전체실행시간={total_execution_time:.3f}초, error={str(e)}")
        raise
