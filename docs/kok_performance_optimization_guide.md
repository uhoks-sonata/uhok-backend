# KOK API 성능 최적화 가이드

## 개요

`/api/kok/discounted` API의 평균 응답시간 1783ms를 대폭 개선하기 위한 성능 최적화 작업을 수행했습니다.

## 최적화 내용

### 1. 데이터베이스 쿼리 최적화

#### 문제점
- **N+1 쿼리 문제**: 메인 쿼리로 상품 목록을 가져온 후, 각 상품마다 추가 쿼리 실행
- **비효율적인 JOIN**: `func.max()` 사용으로 인한 성능 저하
- **중복된 데이터베이스 접근**: 같은 테이블을 여러 번 조회

#### 해결책
- **단일 쿼리 최적화**: 서브쿼리와 JOIN을 활용하여 한 번의 쿼리로 모든 데이터 조회
- **인덱스 최적화**: 자주 사용되는 컬럼에 복합 인덱스 추가

```sql
-- 최적화 전 (N+1 쿼리)
SELECT * FROM FCT_KOK_PRODUCT_INFO WHERE ...;
-- 각 상품마다 실행
SELECT * FROM FCT_KOK_PRICE_INFO WHERE kok_product_id = ? ORDER BY kok_price_id DESC LIMIT 1;

-- 최적화 후 (단일 쿼리)
SELECT p.*, pr.kok_discount_rate, pr.kok_discounted_price
FROM FCT_KOK_PRODUCT_INFO p
JOIN (
    SELECT kok_product_id, MAX(kok_price_id) as latest_price_id
    FROM FCT_KOK_PRICE_INFO
    WHERE kok_discount_rate > 0
    GROUP BY kok_product_id
) latest ON p.kok_product_id = latest.kok_product_id
JOIN FCT_KOK_PRICE_INFO pr ON pr.kok_price_id = latest.latest_price_id
ORDER BY pr.kok_discount_rate DESC;
```

### 2. Redis 캐싱 전략

#### 캐시 설정
- **할인 상품**: 5분 TTL
- **인기 상품**: 10분 TTL  
- **스토어 베스트**: 15분 TTL

#### 캐시 키 패턴
```
kok:discounted:page:{page}:size:{size}
kok:top_selling:page:{page}:size:{size}:sort:{sort_by}
kok:store_best:user:{user_id}:sort:{sort_by}
```

#### 캐시 무효화 API
- `POST /api/kok/cache/invalidate/discounted` - 할인 상품 캐시 무효화
- `POST /api/kok/cache/invalidate/top-selling` - 인기 상품 캐시 무효화
- `POST /api/kok/cache/invalidate/store-best` - 스토어 베스트 캐시 무효화
- `POST /api/kok/cache/invalidate/all` - 모든 캐시 무효화

### 3. 데이터베이스 인덱스 최적화

#### 추가된 인덱스

**FCT_KOK_PRICE_INFO 테이블**
```sql
-- 할인율 기준 정렬
CREATE INDEX idx_kok_price_discount_rate_product_id 
ON FCT_KOK_PRICE_INFO (KOK_DISCOUNT_RATE, KOK_PRODUCT_ID);

-- 상품별 최신 가격 조회
CREATE INDEX idx_kok_price_product_id_price_id 
ON FCT_KOK_PRICE_INFO (KOK_PRODUCT_ID, KOK_PRICE_ID);

-- 할인 상품만 필터링
CREATE INDEX idx_kok_price_discount_rate_gt_zero 
ON FCT_KOK_PRICE_INFO (KOK_DISCOUNT_RATE) 
WHERE KOK_DISCOUNT_RATE > 0;
```

**FCT_KOK_PRODUCT_INFO 테이블**
```sql
-- 리뷰 개수 기준 정렬
CREATE INDEX idx_kok_product_review_cnt_score 
ON FCT_KOK_PRODUCT_INFO (KOK_REVIEW_CNT, KOK_REVIEW_SCORE);

-- 리뷰 점수 기준 정렬
CREATE INDEX idx_kok_product_review_score_cnt 
ON FCT_KOK_PRODUCT_INFO (KOK_REVIEW_SCORE, KOK_REVIEW_CNT);

-- 스토어별 상품 조회
CREATE INDEX idx_kok_product_store_name 
ON FCT_KOK_PRODUCT_INFO (KOK_STORE_NAME);

-- 리뷰가 있는 상품만 필터링
CREATE INDEX idx_kok_product_has_reviews 
ON FCT_KOK_PRODUCT_INFO (KOK_REVIEW_CNT, KOK_REVIEW_SCORE) 
WHERE KOK_REVIEW_CNT > 0;
```

### 4. 성능 모니터링

#### 로깅 개선
- 실행시간 측정 및 로깅
- 캐시 히트/미스 로깅
- 데이터베이스 쿼리 성능 추적

#### 성능 지표
```json
{
  "execution_time_ms": 150.25,
  "use_cache": true,
  "product_count": 20,
  "cache_hit": true
}
```

## 예상 성능 개선 효과

### 1. 응답시간 개선
- **기존**: 1783ms (평균)
- **예상**: 50-200ms (캐시 히트 시), 200-500ms (캐시 미스 시)
- **개선율**: 70-90% 감소

### 2. 데이터베이스 부하 감소
- **쿼리 수**: 21개 → 1개 (N+1 문제 해결)
- **인덱스 활용**: 복합 인덱스로 조회 성능 향상
- **캐시 활용**: 반복 요청 시 DB 접근 없음

### 3. 확장성 향상
- **동시 사용자**: 캐시로 인한 처리량 증가
- **서버 리소스**: CPU 및 메모리 사용량 최적화

## 사용법

### 1. 캐시 사용/비사용
```bash
# 캐시 사용 (기본값)
GET /api/kok/discounted?page=1&size=20&use_cache=true

# 캐시 비사용 (실시간 데이터)
GET /api/kok/discounted?page=1&size=20&use_cache=false
```

### 2. 캐시 무효화
```bash
# 할인 상품 캐시 무효화
POST /api/kok/cache/invalidate/discounted

# 모든 캐시 무효화
POST /api/kok/cache/invalidate/all
```

### 3. 마이그레이션 실행
```bash
# 데이터베이스 인덱스 추가
alembic -c alembic_mariadb_auth.ini upgrade optimize_kok_performance_indexes
```

## 모니터링 및 유지보수

### 1. 성능 모니터링
- 로그에서 `execution_time_ms` 확인
- 캐시 히트율 모니터링
- 데이터베이스 쿼리 성능 추적

### 2. 캐시 관리
- 정기적인 캐시 무효화 (상품 정보 업데이트 시)
- Redis 메모리 사용량 모니터링
- TTL 설정 조정 (필요시)

### 3. 인덱스 유지보수
- 인덱스 사용률 모니터링
- 불필요한 인덱스 제거
- 새로운 쿼리 패턴에 따른 인덱스 추가

## 주의사항

1. **캐시 일관성**: 상품 정보 업데이트 시 반드시 캐시 무효화 필요
2. **메모리 사용량**: Redis 메모리 사용량 모니터링 필요
3. **인덱스 유지보수**: 인덱스 추가로 인한 INSERT/UPDATE 성능 영향 고려
4. **캐시 TTL**: 비즈니스 요구사항에 따라 TTL 조정 필요

## 결론

이번 성능 최적화를 통해 `/api/kok/discounted` API의 응답시간을 대폭 개선할 수 있을 것으로 예상됩니다. 특히 Redis 캐싱과 데이터베이스 쿼리 최적화를 통해 70-90%의 성능 향상을 기대할 수 있습니다.
