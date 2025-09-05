-- /api/recipes/search 성능 최적화를 위한 데이터베이스 인덱스 생성 스크립트
-- 실행 전 백업을 권장합니다.

-- ============================================================================
-- MariaDB 인덱스 최적화 (FCT_RECIPE, FCT_MTRL 테이블)
-- ============================================================================

-- 1. 레시피 제목 검색용 인덱스
CREATE INDEX IF NOT EXISTS idx_recipe_cooking_name ON FCT_RECIPE(COOKING_NAME);
CREATE INDEX IF NOT EXISTS idx_recipe_title ON FCT_RECIPE(RECIPE_TITLE);

-- 2. 인기순 정렬용 인덱스
CREATE INDEX IF NOT EXISTS idx_recipe_scrap_count ON FCT_RECIPE(SCRAP_COUNT DESC);

-- 3. 재료명 검색용 인덱스
CREATE INDEX IF NOT EXISTS idx_material_name ON FCT_MTRL(MATERIAL_NAME);

-- 4. 조합 검색용 복합 인덱스 (재료-레시피 조인 최적화)
CREATE INDEX IF NOT EXISTS idx_material_recipe_id ON FCT_MTRL(RECIPE_ID, MATERIAL_NAME);

-- 5. 재료별 레시피 그룹핑 최적화
CREATE INDEX IF NOT EXISTS idx_material_name_recipe_id ON FCT_MTRL(MATERIAL_NAME, RECIPE_ID);

-- 6. 텍스트 검색 최적화 (LIKE 쿼리용)
-- MySQL 5.7+ 에서는 FULLTEXT 인덱스 사용 권장
CREATE FULLTEXT INDEX IF NOT EXISTS idx_recipe_cooking_name_fulltext ON FCT_RECIPE(COOKING_NAME);
CREATE FULLTEXT INDEX IF NOT EXISTS idx_recipe_title_fulltext ON FCT_RECIPE(RECIPE_TITLE);

-- ============================================================================
-- PostgreSQL 인덱스 최적화 (RECIPE_VECTOR_TABLE)
-- ============================================================================

-- 1. pgvector HNSW 인덱스 (벡터 검색 최적화)
-- pgvector 확장이 설치되어 있어야 합니다.
CREATE INDEX IF NOT EXISTS idx_recipe_vector_hnsw ON RECIPE_VECTOR_TABLE 
USING hnsw (VECTOR_NAME vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

-- 2. recipe_id 인덱스 (JOIN 최적화)
CREATE INDEX IF NOT EXISTS idx_recipe_vector_recipe_id ON RECIPE_VECTOR_TABLE(RECIPE_ID);

-- 3. 벡터 거리 검색 최적화
CREATE INDEX IF NOT EXISTS idx_recipe_vector_distance ON RECIPE_VECTOR_TABLE 
USING ivfflat (VECTOR_NAME vector_cosine_ops) 
WITH (lists = 100);

-- ============================================================================
-- 쿼리 성능 분석용 뷰
-- ============================================================================

-- 레시피 검색 성능 모니터링용 뷰
CREATE OR REPLACE VIEW recipe_search_stats AS
SELECT 
    'FCT_RECIPE' as table_name,
    COUNT(*) as total_recipes,
    COUNT(CASE WHEN COOKING_NAME IS NOT NULL THEN 1 END) as recipes_with_cooking_name,
    COUNT(CASE WHEN RECIPE_TITLE IS NOT NULL THEN 1 END) as recipes_with_title,
    AVG(SCRAP_COUNT) as avg_scrap_count,
    MAX(SCRAP_COUNT) as max_scrap_count
FROM FCT_RECIPE
UNION ALL
SELECT 
    'FCT_MTRL' as table_name,
    COUNT(*) as total_materials,
    COUNT(DISTINCT MATERIAL_NAME) as unique_materials,
    COUNT(DISTINCT RECIPE_ID) as recipes_with_materials,
    AVG(LENGTH(MATERIAL_NAME)) as avg_material_name_length,
    NULL as max_scrap_count
FROM FCT_MTRL;

-- ============================================================================
-- 성능 최적화 확인 쿼리
-- ============================================================================

-- 인덱스 사용 여부 확인
EXPLAIN SELECT r.RECIPE_ID, r.COOKING_NAME, r.SCRAP_COUNT 
FROM FCT_RECIPE r 
WHERE r.COOKING_NAME LIKE '%김치%' 
ORDER BY r.SCRAP_COUNT DESC 
LIMIT 10;

-- 재료 검색 성능 확인
EXPLAIN SELECT m.RECIPE_ID 
FROM FCT_MTRL m 
WHERE m.MATERIAL_NAME IN ('김치', '돼지고기', '된장') 
GROUP BY m.RECIPE_ID 
HAVING COUNT(DISTINCT m.MATERIAL_NAME) = 3;

-- ============================================================================
-- 추가 최적화 권장사항
-- ============================================================================

/*
1. 데이터베이스 설정 최적화:
   - innodb_buffer_pool_size를 메모리의 70-80%로 설정
   - query_cache_size 활성화 (MySQL 5.7 이하)
   - max_connections 적절히 조정

2. 애플리케이션 레벨 최적화:
   - 연결 풀링 설정 최적화
   - 쿼리 타임아웃 설정
   - 캐싱 전략 적용

3. 모니터링:
   - slow_query_log 활성화
   - 인덱스 사용률 모니터링
   - 쿼리 실행 계획 정기 점검

4. 정기 유지보수:
   - ANALYZE TABLE 실행 (통계 정보 업데이트)
   - OPTIMIZE TABLE 실행 (테이블 최적화)
   - 인덱스 사용률에 따른 인덱스 정리
*/
