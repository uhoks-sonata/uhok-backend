"""
원격 ML 서비스 호출 어댑터
백엔드에서 ML Inference 서비스와 통신하는 모듈입니다.
"""

import os
import httpx
import asyncio
from typing import List, Tuple, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from .ports import VectorSearcherPort
from common.logger import get_logger
import time

logger = get_logger("remote_ml_adapter")

# 환경 변수에서 ML 서비스 설정 가져오기
ML_INFERENCE_URL = os.getenv("ML_INFERENCE_URL")
ML_TIMEOUT = float(os.getenv("ML_TIMEOUT", "10.0"))
ML_RETRIES = int(os.getenv("ML_RETRIES", "2"))

class RemoteMLAdapter(VectorSearcherPort):
    """
    원격 ML 서비스에 유사도 검색을 요청하는 어댑터
    """

    async def find_similar_ids(
        self,
        pg_db: AsyncSession, # DB 세션은 더 이상 사용되지 않지만, 포트 호환성을 위해 유지
        query: str,
        top_k: int,
        exclude_ids: Optional[List[int]] = None,
    ) -> List[Tuple[int, float]]:
        """
        원격 ML 서비스의 /api/v1/search 엔드포인트를 호출하여 유사도 검색을 수행합니다.

        Args:
            pg_db: (사용 안 함) PostgreSQL 세션
            query: 검색 쿼리 텍스트
            top_k: 반환할 상위 결과 수
            exclude_ids: 제외할 RECIPE_ID 목록

        Returns:
            (recipe_id, distance) 튜플 리스트
        """
        start_time = time.time()
        url = f"{ML_INFERENCE_URL}/api/v1/search"
        payload = {
            "query": query,
            "top_k": top_k,
            "exclude_ids": exclude_ids or []
        }
        logger.info(f"ML 서비스 검색 요청: URL={url}, query='{query}', top_k={top_k}")

        async with httpx.AsyncClient(timeout=ML_TIMEOUT) as client:
            for attempt in range(ML_RETRIES + 1):
                try:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    
                    data = response.json()
                    results = data.get("results", [])
                    
                    # 결과 형식 변환: List[Dict] -> List[Tuple[int, float]]
                    formatted_results = [(item["recipe_id"], item["distance"]) for item in results]
                    
                    total_time = time.time() - start_time
                    logger.info(
                        f"ML 서비스 검색 성공: query='{query}', top_k={top_k}, "
                        f"총 {total_time:.3f}s 소요, 결과 {len(formatted_results)}건 수신"
                    )
                    return formatted_results

                except httpx.TimeoutException:
                    if attempt < ML_RETRIES:
                        logger.warning(f"ML 서비스 타임아웃, 재시도 {attempt + 1}/{ML_RETRIES}")
                        await asyncio.sleep(0.5 * (attempt + 1))
                    else:
                        logger.error("ML 서비스 타임아웃, 최대 재시도 횟수 초과")
                        raise
                
                except httpx.HTTPStatusError as e:
                    total_time = time.time() - start_time
                    logger.error(
                        f"ML 서비스 HTTP 에러: status={e.response.status_code}, "
                        f"response='{e.response.text}', 총 {total_time:.3f}s 소요"
                    )
                    raise

                except Exception as e:
                    total_time = time.time() - start_time
                    logger.error(f"ML 서비스 호출 실패: 총 {total_time:.3f}s, error='{str(e)}'")
                    raise
        
        # 모든 재시도 실패 시
        raise Exception("ML 서비스 호출에 최종적으로 실패했습니다.")


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

async def _call_ml_search_service(query: str, top_k: int, exclude_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """
    원격 ML 서비스를 호출하여 유사도 검색을 수행하고, 결과를 딕셔너리 리스트로 반환합니다.
    라우터에서 사용하기 위한 헬퍼 함수입니다.
    """
    logger.info(f"Helper `_call_ml_search_service` 호출: query='{query}', top_k={top_k}")
    searcher = await get_remote_ml_searcher()
    # find_similar_ids는 pg_db를 받지만 원격 호출 시 사용하지 않으므로 None을 전달합니다.
    results_tuples = await searcher.find_similar_ids(
        pg_db=None, 
        query=query, 
        top_k=top_k, 
        exclude_ids=exclude_ids
    )
    
    # 라우터에서 기대하는 형식(List[Dict])으로 변환합니다.
    results_list = [{"recipe_id": r_id, "distance": dist} for r_id, dist in results_tuples]
    logger.info(f"Helper `_call_ml_search_service` 결과: {len(results_list)}건")
    return results_list
