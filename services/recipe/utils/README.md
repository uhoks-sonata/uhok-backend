# Recipe Service: 아키텍처 및 유틸리티

> **문서 요약**: `recipe` 서비스의 핵심 아키텍처, 데이터 흐름, 주요 유틸리티 모듈에 대해 설명합니다.

## 1. 아키텍처 (Microservice)

레시피 추천 기능은 **`uhok-backend`**와 **`uhok-ml-inference`** 두 개의 마이크로서비스로 분리되어 있습니다.

- **`uhok-backend`**:
    - 주 역할: 사용자 요청 처리, 비즈니스 로직 수행, 데이터베이스(MariaDB) 접근
    - 레시피 검색 요청 시, `uhok-ml-inference` 서비스에 API를 호출하여 결과를 받아옵니다.
- **`uhok-ml-inference`**:
    - 주 역할: ML 모델(Sentence Transformer)을 이용한 자연어 처리 및 벡터 검색
    - 텍스트를 벡터로 변환(Embedding)하고, PostgreSQL(pgvector)에서 유사한 레시피를 검색하여 ID 목록을 반환합니다.

### 데이터베이스 구조
- **MariaDB**: `uhok-backend`가 사용. 레시피, 재료, 사용자 등 핵심 정보 저장.
- **PostgreSQL**:
    - `uhok-ml-inference`: 벡터 임베딩 데이터 저장 및 검색 (`pgvector` 확장 기능 사용).
    - `uhok-backend`: 사용자 이벤트 및 행동 로그 적재.

## 2. 데이터 흐름 (레시피명 기반 검색)

1.  **API 요청**: 사용자가 `uhok-backend`의 `/api/recipes/search` 엔드포인트로 검색어를 보냅니다.
2.  **ML 서비스 호출**: `uhok-backend`는 `remote_ml_adapter`를 통해 `uhok-ml-inference`의 `/api/v1/search` API를 HTTP로 호출합니다.
3.  **벡터 검색**: `uhok-ml-inference`는 검색어를 임베딩 벡터로 변환하고, PostgreSQL에서 유사도가 높은 레시피 ID 목록을 찾습니다.
4.  **ID 목록 반환**: `uhok-ml-inference`가 검색된 레시피 ID 목록을 `uhok-backend`에 반환합니다.
5.  **상세 정보 조회**: `uhok-backend`는 전달받은 ID 목록을 사용하여 MariaDB에서 각 레시피의 상세 정보를 조회합니다.
6.  **최종 응답**: `uhok-backend`가 모든 정보를 취합하여 사용자에게 최종 응답을 보냅니다.

## 3. 핵심 컴포넌트 (`utils` 폴더)

- **`remote_ml_adapter.py`**: `uhok-ml-inference` 서비스와의 HTTP 통신을 담당하는 어댑터.
- **`ports.py`**: 서비스 간의 의존성을 낮추기 위한 추상 인터페이스(Protocol) 정의.
- **`inventory_recipe.py`**: 재료 소진 알고리즘 등 식재료 기반 추천 관련 유틸리티.
- **`product_recommend.py`**: 식재료에 대한 콕/홈쇼핑 상품 추천 로직.
- **`combination_tracker.py`**: 재료 기반 추천 시, 조합별로 사용된 레시피를 추적하는 모듈.
- **`simple_cache.py`**: 추천 결과를 메모리에 캐싱하여 성능을 향상시키는 모듈.
- **`unused_*.py`**: 현재 사용되지 않는 레거시 코드 백업 파일.

## 4. 사용 예시 (ML 서비스 연동)

`recipe_router.py`에서는 아래와 같이 `_call_ml_search_service` 헬퍼 함수를 통해 간단하게 ML 서비스를 호출합니다.

```python
# /services/recipe/routers/recipe_router.py

from ..utils.remote_ml_adapter import _call_ml_search_service

# ... router 로직 내에서 ...
# 'recipe' 메소드일 경우 ML 서비스 호출
search_results = await _call_ml_search_service(
    query=recipe,
    top_k=page * size + 1
)
# 결과로 받은 ID 목록 추출
result_ids = [item['recipe_id'] for item in search_results]
```

## 5. 향후 개선 계획

1.  **로그 파이프라인 개선**:
    - 현재 `uhok-backend`가 직접 PostgreSQL에 쓰는 로그를 **Kafka**로 발행하고, **Spark Streaming**으로 처리하여 최종적으로 OLAP 저장소(e.g., BigQuery)에 적재하는 방식으로 변경하는 것을 고려 중입니다.
    - **기대 효과**: 이 변경을 통해 `uhok-backend`의 PostgreSQL 직접 접근이 완전히 제거되어, 서비스 간 결합도를 더욱 낮추고 확장성을 높일 수 있습니다.
2.  **벡터 인덱싱 고도화**: `uhok-ml-inference` 서비스에서 pgvector 대신 FAISS, HNSW 등 고성능 벡터 인덱스를 도입하여 검색 속도 향상.
3.  **캐싱 레이어 도입**: 추천 결과를 Redis 같은 외부 캐시 저장소에 저장하여 응답 속도 개선.
4.  **개인화 추천**: 사용자 행동 데이터를 기반으로 한 협업 필터링 모델 도입.
