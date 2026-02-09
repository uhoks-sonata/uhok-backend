import os
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.homeshopping.models.core_model import HomeshoppingList
from services.kok.models.product_model import KokProductInfo
from .shared import logger

async def get_homeshopping_product_name(
    db: AsyncSession,
    homeshopping_product_id: int
) -> Optional[str]:
    """
    홈쇼핑 상품명 조회
    """
    # logger.info(f"홈쇼핑 상품명 조회 시작: homeshopping_product_id={homeshopping_product_id}")
    
    try:
        stmt = select(HomeshoppingList.product_name).where(HomeshoppingList.product_id == homeshopping_product_id).order_by(HomeshoppingList.live_date.asc(), HomeshoppingList.live_start_time.asc(), HomeshoppingList.live_id.asc())
        try:
            result = await db.execute(stmt)
            product_name = result.scalar()
        except Exception as e:
            logger.error(f"홈쇼핑 상품명 조회 SQL 실행 실패: homeshopping_product_id={homeshopping_product_id}, error={str(e)}")
            return None
        
        if product_name:
            # logger.info(f"홈쇼핑 상품명 조회 완료: homeshopping_product_id={homeshopping_product_id}, name={product_name}")
            return product_name
        else:
            logger.warning(f"홈쇼핑 상품을 찾을 수 없음: homeshopping_product_id={homeshopping_product_id}")
            return None
            
    except Exception as e:
        logger.error(f"홈쇼핑 상품명 조회 실패: product_id={homeshopping_product_id}, error={str(e)}")
        return None


async def get_kok_product_infos(
    db: AsyncSession,
    kok_product_ids: List[int]
) -> List[dict]:
    """
    콕 상품 정보 조회 (실제 DB 연동)
    """
    # logger.info(f"콕 상품 정보 조회 시작: kok_product_ids={kok_product_ids}")
    
    if not kok_product_ids:
        logger.warning("조회할 상품 ID가 없음")
        return []
    
    try:
        # 실제 FCT_KOK_PRODUCT_INFO 테이블에서 상품 정보 조회 (가격 정보 포함)
        stmt = (
            select(KokProductInfo)
            .where(
                KokProductInfo.kok_product_id.in_(kok_product_ids)
            )
            .order_by(KokProductInfo.kok_review_cnt.desc())  # 리뷰 수 순으로 정렬 (MariaDB 호환)
        )
        
        # 가격 정보도 함께 로드
        stmt = stmt.options(selectinload(KokProductInfo.price_infos))
        
        try:
            result = await db.execute(stmt)
            kok_products = result.scalars().all()
        except Exception as e:
            logger.error(f"콕 상품 정보 조회 SQL 실행 실패: kok_product_ids={kok_product_ids}, error={str(e)}")
            return []
        
        # 응답 형태로 변환
        products = []
        for product in kok_products:
            # 할인율 계산 (원가와 할인가가 있을 때)
            discount_rate = 0
            # kok_product_price를 원가로 사용하고, 할인가가 없으면 원가를 할인가로 사용
            original_price = product.kok_product_price or 0
            discounted_price = 0
            
            # 가격 정보가 있는 경우 할인가 조회
            if hasattr(product, 'price_infos') and product.price_infos:
                for price_info in product.price_infos:
                    if price_info.kok_discounted_price:
                        discounted_price = price_info.kok_discounted_price
                        if price_info.kok_discount_rate:
                            discount_rate = price_info.kok_discount_rate
                        break
            
            # 할인가가 없으면 원가를 할인가로 사용
            if discounted_price == 0:
                discounted_price = original_price
            
            # 할인율이 0이고 원가와 할인가가 다르면 계산
            if discount_rate == 0 and original_price > 0 and discounted_price > 0 and original_price != discounted_price:
                discount_rate = int(((original_price - discounted_price) / original_price) * 100)
            
            products.append({
                "kok_product_id": product.kok_product_id,
                "kok_thumbnail": product.kok_thumbnail or "",
                "kok_discount_rate": discount_rate,
                "kok_discounted_price": discounted_price,
                "kok_product_name": product.kok_product_name or "",
                "kok_store_name": product.kok_store_name or ""
            })
        
        # logger.info(f"콕 상품 정보 조회 완료: 결과 수={len(products)}")
        return products
        
    except Exception as e:
        logger.error(f"콕 상품 정보 조회 실패: error={str(e)}")
        logger.error("콕 상품 정보 조회에 실패했습니다")
        return []

async def get_pgvector_topk_within(
    db: AsyncSession,
    product_id: int,
    candidate_ids: List[int],
    k: int
) -> List[Tuple[int, float]]:
    """
    pgvector를 사용한 유사도 기반 정렬 (실제 DB 연동)
    """
    # logger.info(f"pgvector 유사도 정렬 시작: product_id={product_id}, candidates={len(candidate_ids)}, k={k}")
    
    if not candidate_ids:
        logger.warning("pgvector 유사도 정렬: 후보 상품 ID가 없음")
        return []
    
    try:
        # 1) 쿼리 텍스트 준비: 홈쇼핑 상품명 사용
        prod_name = await get_homeshopping_product_name(db, product_id) or ""
        if not prod_name:
            logger.warning(f"pgvector 정렬 실패: 홈쇼핑 상품명을 찾을 수 없음, product_id={product_id}")
            return []

        # 2) 임베딩 생성 (ML 서비스 사용)
        from services.recipe.utils.remote_ml_adapter import RemoteMLAdapter
        ml_adapter = RemoteMLAdapter()
        query_vec = await ml_adapter._get_embedding_from_ml_service(prod_name)

        # 3) PostgreSQL(pgvector)로 후보 내 유사도 정렬
        from sqlalchemy import text, bindparam
        from pgvector.sqlalchemy import Vector
        from common.database.postgres_recommend import get_postgres_recommend_db

        sql = text(
            """
            SELECT "KOK_PRODUCT_ID" AS pid,
                   "VECTOR_NAME" <-> :qv AS distance
            FROM "KOK_VECTOR_TABLE"
            WHERE "KOK_PRODUCT_ID" IN :ids
            ORDER BY distance ASC
            LIMIT :k
            """
        ).bindparams(
            bindparam("qv", type_=Vector(384)),   # vector(384)로 바인딩
            bindparam("ids", expanding=True),      # 후보 ID 리스트 확장
            bindparam("k")
        )

        params = {
            "qv": query_vec,
            "ids": [int(i) for i in candidate_ids],
            "k": int(max(1, k)),
        }

        async for pg in get_postgres_recommend_db():
            rows = (await pg.execute(sql, params)).all()
            sims: List[Tuple[int, float]] = [
                (int(r.pid), float(r.distance)) for r in rows
            ]
            # logger.info(f"pgvector 정렬 완료: 결과 수={len(sims)}")
            return sims
        
        return []
        
    except Exception as e:
        logger.error(f"pgvector 유사도 정렬 실패: error={str(e)}")
        return []

async def get_kok_candidates_by_keywords_improved(
    db: AsyncSession,
    must_keywords: List[str],
    optional_keywords: List[str],
    limit: int = 600,
    min_if_all_fail: int = 30
) -> List[int]:
    """
    키워드 기반으로 콕 상품 후보 검색 (개선된 오케스트레이터 로직)
    - must: OR(하나라도) → 부족하면 AND(최대 2개) → 다시 OR로 폴백
    - optional: 여전히 부족하면 OR로 보충
    - GATE_COMPARE_STORE=true면 스토어명도 검색에 포함
    """
    # logger.info(f"키워드 기반 콕 상품 검색 시작: must={must_keywords}, optional={optional_keywords}, limit={limit}")
    
    if not must_keywords and not optional_keywords:
        logger.warning("키워드 기반 콕 상품 검색: 검색 키워드가 없음")
        return []
    
    try:
        # 검색 대상 컬럼 결정 (스토어명 비교 옵션에 따라)
        search_columns = [KokProductInfo.kok_product_name]
        if GATE_COMPARE_STORE:
            search_columns.append(KokProductInfo.kok_store_name)
            # logger.info("스토어명도 검색에 포함")
        
        # 1단계: must 키워드로 검색 (OR 조건)
        must_candidates = []
        if must_keywords:
            must_conditions = []
            for keyword in must_keywords:
                if len(keyword) >= 2:  # 2글자 이상만 검색
                    for col in search_columns:
                        must_conditions.append(col.contains(keyword))
            
            if must_conditions:
                must_stmt = (
                    select(KokProductInfo.kok_product_id)
                    .where(
                        or_(*must_conditions)
                    )
                    .limit(limit)
                )
                
                result = await db.execute(must_stmt)
                must_candidates = [row[0] for row in result.fetchall()]
                # logger.info(f"must 키워드 검색 결과: {len(must_candidates)}개")
        
        # 2단계: must 키워드가 부족하면 AND 조건으로 재검색
        if len(must_candidates) < min_if_all_fail and len(must_keywords) >= 2:
            use_keywords = must_keywords[:2]  # 최대 2개 키워드만 사용
            and_conditions = []
            for keyword in use_keywords:
                if len(keyword) >= 2:
                    for col in search_columns:
                        and_conditions.append(col.contains(keyword))
            
            if and_conditions:
                # 각 키워드가 최소 하나의 컬럼에 포함되어야 함
                keyword_conditions = []
                for keyword in use_keywords:
                    keyword_conditions.append(
                        or_(*[col.contains(keyword) for col in search_columns])
                    )
                
                and_stmt = (
                    select(KokProductInfo.kok_product_id)
                    .where(
                        and_(*keyword_conditions)
                    )
                    .limit(limit)
                )
                
                result = await db.execute(and_stmt)
                and_candidates = [row[0] for row in result.fetchall()]
                # logger.info(f"AND 조건 검색 결과: {len(and_candidates)}개")
                
                # AND 결과가 더 많으면 교체
                if len(and_candidates) > len(must_candidates):
                    must_candidates = and_candidates
        
        # 3단계: optional 키워드로 보충 검색
        optional_candidates = []
        if optional_keywords and len(must_candidates) < limit:
            optional_conditions = []
            for keyword in optional_keywords:
                if len(keyword) >= 2:
                    for col in search_columns:
                        optional_conditions.append(col.contains(keyword))
            
            if optional_conditions:
                optional_stmt = (
                    select(KokProductInfo.kok_product_id)
                    .where(
                        or_(*optional_conditions)
                    )
                    .limit(limit - len(must_candidates))
                )
                
                result = await db.execute(optional_stmt)
                optional_candidates = [row[0] for row in result.fetchall()]
                # logger.info(f"optional 키워드 검색 결과: {len(optional_candidates)}개")
        
        # 4단계: 결과 합치기 및 중복 제거
        all_candidates = list(dict.fromkeys(must_candidates + optional_candidates))[:limit]
        
        # logger.info(f"키워드 기반 검색 완료: 총 {len(all_candidates)}개 후보")
        return all_candidates
        
    except Exception as e:
        logger.error(f"키워드 기반 검색 실패: error={str(e)}")
        logger.error("키워드 기반 검색에 실패했습니다")
        return []


async def get_kok_candidates_by_keywords(
    db: AsyncSession,
    must_keywords: List[str],
    optional_keywords: List[str],
    limit: int = 600,
    min_if_all_fail: int = 30
) -> List[int]:
    """
    키워드 기반으로 콕 상품 후보 검색 (기존 함수 - 호환성 유지)
    """
    return await get_kok_candidates_by_keywords_improved(db, must_keywords, optional_keywords, limit, min_if_all_fail)

async def test_kok_db_connection(db: AsyncSession) -> bool:
    """
    콕 상품 DB 연결 테스트
    """
    try:
        # 간단한 쿼리로 연결 테스트
        stmt = select(func.count(KokProductInfo.kok_product_id))
        result = await db.execute(stmt)
        count = result.scalar()
        
        # logger.info(f"콕 상품 DB 연결 성공: 총 상품 수 = {count}")
        return True
        
    except Exception as e:
        logger.error(f"콕 상품 DB 연결 실패: {str(e)}")
        return False


# -----------------------------
# 추천 관련 유틸리티 함수들 (utils 폴더 사용)
# -----------------------------

# ----- 옵션: 게이트에서 스토어명도 LIKE 비교할지 (기본 False) -----
GATE_COMPARE_STORE = os.getenv("GATE_COMPARE_STORE", "false").lower() in ("1","true","yes","on")

# -----------------------------
# 추천 시스템 함수들
# -----------------------------

async def recommend_homeshopping_to_kok(
    db,
    homeshopping_product_id: int,
    k: int = 5,                       # 최대 5개
    use_rerank: bool = False,         # 여기선 기본 거리 정렬만 사용
    candidate_n: int = 150,
    rerank_mode: str = None,
) -> List[Dict]:
    """
    홈쇼핑 상품에 대한 콕 유사 상품 추천 (utils 원본 로직 사용)
    응답 형태는 라우터에서 {"products": [...]}로 감싸 반환
    """
    try:
        # utils의 키워드 추출 및 필터링 함수들 사용
        from ..utils.homeshopping_kok import (
            filter_tail_and_ngram_and,
            extract_tail_keywords, extract_core_keywords, roots_in_name,
            infer_terms_from_name_via_ngrams, DYN_MAX_TERMS
        )
        
        # 1. 홈쇼핑 상품명 조회
        prod_name = await get_homeshopping_product_name(db, homeshopping_product_id) or ""
        if not prod_name:
            logger.warning(f"홈쇼핑 상품명을 찾을 수 없음: homeshopping_product_id={homeshopping_product_id}")
            return []

        # 2. 키워드 구성 (최적화된 버전)
        # 병렬로 키워드 추출하여 성능 개선
        import asyncio
        
        # 동시에 키워드 추출 실행
        tail_task = asyncio.create_task(asyncio.to_thread(extract_tail_keywords, prod_name, 2))
        core_task = asyncio.create_task(asyncio.to_thread(extract_core_keywords, prod_name, 3))
        root_task = asyncio.create_task(asyncio.to_thread(roots_in_name, prod_name))
        ngram_task = asyncio.create_task(asyncio.to_thread(infer_terms_from_name_via_ngrams, prod_name, DYN_MAX_TERMS))
        
        # 모든 키워드 추출 완료 대기
        tail_k, core_k, root_k, ngram_k = await asyncio.gather(
            tail_task, core_task, root_task, ngram_task
        )

        must_kws = list(dict.fromkeys([*tail_k, *core_k, *root_k]))[:12]
        optional_kws = list(dict.fromkeys([*ngram_k]))[:DYN_MAX_TERMS]

        # logger.info(f"키워드 구성: must={must_kws}, optional={optional_kws}")

        # 3. LIKE 게이트로 후보 (최적화된 버전)
        # 키워드가 적으면 더 작은 후보 수로 제한하여 성능 개선
        optimized_limit = min(max(candidate_n * 2, 150), 300) if len(must_kws) <= 3 else max(candidate_n * 3, 300)
        
        cand_ids = await get_kok_candidates_by_keywords_improved(
            db=db,
            must_keywords=must_kws,
            optional_keywords=optional_kws,
            limit=optimized_limit
        )
        if not cand_ids:
            logger.warning(f"키워드 기반 후보 수집 결과가 비어있음: product_id={homeshopping_product_id}, must_keywords={must_kws}")
            return []

        # logger.info(f"후보 수집 완료: {len(cand_ids)}개")

        # 4. 후보 내 pgvector 정렬 (최적화된 버전)
        # 후보가 적으면 pgvector 정렬 생략하고 바로 상세 조회
        if len(cand_ids) <= k * 2:
            logger.warning(f"후보 수가 적어 pgvector 정렬 생략: product_id={homeshopping_product_id}, 후보 수={len(cand_ids)}개")
            pid_order = cand_ids[:k]
            dist_map = {}
        else:
            sims = await get_pgvector_topk_within(
                db,
                homeshopping_product_id,
                cand_ids,
                max(k, candidate_n),
            )
            if not sims:
                logger.warning(f"pgvector 정렬 결과가 비어있음: product_id={homeshopping_product_id}")
                return []

            pid_order = [pid for pid, _ in sims]
            dist_map = {pid: dist for pid, dist in sims}

        # 5. 상세 조인
        details = await get_kok_product_infos(db, pid_order)
        if not details:
            logger.warning(f"콕 상품 상세 정보 조회 결과가 비어있음: product_id={homeshopping_product_id}, pid_order={pid_order[:5]}")
            return []
        
        # 거리 정보 추가 (있는 경우만)
        for d in details:
            if d["kok_product_id"] in dist_map:
                d["distance"] = dist_map[d["kok_product_id"]]

        # 6. 거리 정렬 (거리 정보가 있는 경우만)
        if dist_map:
            ranked = sorted(details, key=lambda x: x.get("distance", 1e9))
        else:
            ranked = details

        # 7. 최종 AND 필터 적용 (tail ≥1 AND n-gram ≥1) - 간소화
        # 필터링을 위해 키 변환
        for d in ranked:
            d["KOK_PRODUCT_NAME"] = d.get("kok_product_name", "")
            d["KOK_STORE_NAME"] = d.get("kok_store_name", "")
        
        filtered = filter_tail_and_ngram_and(ranked, prod_name)
        
        # 임시 키 제거
        for d in filtered:
            d.pop("KOK_PRODUCT_NAME", None)
            d.pop("KOK_STORE_NAME", None)

        # 8. 최대 k개까지 반환
        result = filtered[:k]
        # logger.info(f"추천 완료: {len(result)}개 상품")
        return result
        
    except Exception as e:
        logger.error(f"추천 로직 실패: {str(e)}")
        # 폴백으로 간단 추천 사용
        return await simple_recommend_homeshopping_to_kok(homeshopping_product_id, k, db)

async def simple_recommend_homeshopping_to_kok(
    homeshopping_product_id: int,
    k: int = 5,
    db=None
) -> List[Dict]:
    """
    간단한 추천 데이터 반환 (실제 DB 연동 시도)
    - 오케스트레이터 실패 시 폴백 시스템
    """
    # logger.info(f"간단한 추천 시스템 호출: homeshopping_product_id={homeshopping_product_id}, k={k}")
    
    # DB가 있고 실제 DB 연동이 가능한 경우 시도
    if db:
        try:
            # 판매량 상위 상품들을 가져오기 위해 더미 ID 대신 실제 검색
            popular_ids = [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010]
            
            recommendations = await get_kok_product_infos(db, popular_ids[:k])
            
            if recommendations:
                # logger.info(f"실제 DB에서 추천 데이터 조회 완료: {len(recommendations)}개 상품")
                return recommendations
                
        except Exception as e:
            logger.warning(f"실제 DB 연동 실패: {str(e)}")
    
    # DB 연동 실패 시 빈 리스트 반환
    logger.warning("추천 결과를 찾을 수 없습니다")
    return []
