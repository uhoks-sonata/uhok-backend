from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.keyword_extraction import (
    extract_ingredient_keywords,
    get_homeshopping_db_config,
    load_ing_vocab,
)
from services.homeshopping.models.core_model import HomeshoppingClassify
from services.kok.models.classify_model import KokClassify
from services.kok.models.interaction_model import KokCart
from services.kok.models.product_model import KokPriceInfo, KokProductInfo

from .shared import get_latest_kok_price_id, logger

async def get_kok_cart_items(
    db: AsyncSession,
    user_id: int,
    limit: int = 50
) -> List[dict]:
    """
    사용자의 장바구니 상품 목록 조회
    """
    stmt = (
        select(KokCart, KokProductInfo, KokPriceInfo)
        .join(KokProductInfo, KokCart.kok_product_id == KokProductInfo.kok_product_id)
        .join(KokPriceInfo, KokCart.kok_price_id == KokPriceInfo.kok_price_id)
        .where(KokCart.user_id == user_id)
        .order_by(KokCart.kok_created_at.desc())
        .limit(limit)
    )
    
    try:
        results = (await db.execute(stmt)).all()
    except Exception as e:
        logger.error(f"장바구니 상품 목록 조회 SQL 실행 실패: user_id={user_id}, limit={limit}, error={str(e)}")
        return []
    
    cart_items = []
    for cart, product, price in results:
        cart_items.append({
            "kok_cart_id": cart.kok_cart_id,
            "kok_product_id": product.kok_product_id,
            "kok_price_id": cart.kok_price_id,
            "recipe_id": cart.recipe_id,
            "kok_product_name": product.kok_product_name,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_product_price": product.kok_product_price,
            "kok_discount_rate": price.kok_discount_rate if price else 0,
            "kok_discounted_price": price.kok_discounted_price if price else product.kok_product_price,
            "kok_store_name": product.kok_store_name,
            "kok_quantity": cart.kok_quantity,
        })
    
    return cart_items


# 새로운 장바구니 CRUD 함수들
async def add_kok_cart(
    db: AsyncSession,
    user_id: int,
    kok_product_id: int,
    kok_quantity: int = 1,
    recipe_id: Optional[int] = None
) -> dict:
    """
    장바구니에 상품 추가 (자동으로 최신 가격 ID 사용)
    """
    # logger.info(f"장바구니 추가 시작: user_id={user_id}, kok_product_id={kok_product_id}, kok_quantity={kok_quantity}, recipe_id={recipe_id}")
    
    # recipe_id가 0이면 None으로 처리 (외래키 제약 조건 위반 방지)
    if recipe_id == 0:
        recipe_id = None
    # logger.info(f"recipe_id가 0이므로 None으로 처리")
    
    # 최신 가격 ID 자동 조회
    latest_price_id = await get_latest_kok_price_id(db, kok_product_id)
    if not latest_price_id:
        logger.warning(f"가격 정보를 찾을 수 없음: kok_product_id={kok_product_id}")
        raise ValueError("상품의 가격 정보를 찾을 수 없습니다.")
    
    # logger.info(f"최신 가격 ID 사용: kok_product_id={kok_product_id}, latest_kok_price_id={latest_price_id}")
    
    # 기존 장바구니 항목 확인 (product_id만 고려)
    stmt = select(KokCart).where(
        KokCart.user_id == user_id,
        KokCart.kok_product_id == kok_product_id
    )
    try:
        result = await db.execute(stmt)
        existing_cart = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"기존 장바구니 항목 확인 SQL 실행 실패: user_id={user_id}, kok_product_id={kok_product_id}, error={str(e)}")
        raise
    
    if existing_cart:
        # 수량 업데이트
        existing_cart.kok_quantity += kok_quantity
    # logger.info(f"장바구니 수량 업데이트 완료: kok_cart_id={existing_cart.kok_cart_id}, new_quantity={existing_cart.kok_quantity}")
        return {
            "kok_cart_id": existing_cart.kok_cart_id,
            "message": f"장바구니 수량이 {existing_cart.kok_quantity}개로 업데이트되었습니다."
        }
    else:
        # 새 항목 추가
        created_at = datetime.now()
        
        new_cart = KokCart(
            user_id=user_id,
            kok_product_id=kok_product_id,
            kok_price_id=latest_price_id,
            kok_quantity=kok_quantity,
            kok_created_at=created_at,
            recipe_id=recipe_id
        )
        
        db.add(new_cart)
        # refresh는 commit 후에 호출해야 하므로 여기서는 제거
        # await db.refresh(new_cart)
        
    # logger.info(f"장바구니 새 항목 추가 완료: user_id={user_id}, kok_product_id={kok_product_id}, kok_price_id={latest_price_id}")
        return {
            "kok_cart_id": 0,  # commit 후에 실제 ID를 얻을 수 있음
            "message": "장바구니에 상품이 추가되었습니다."
        }


async def update_kok_cart_quantity(
    db: AsyncSession,
    user_id: int,
    kok_cart_id: int,
    kok_quantity: int
) -> dict:
    """
    장바구니 상품 수량 변경
    """
    # 장바구니 항목 확인
    stmt = (
        select(KokCart)
        .where(KokCart.kok_cart_id == kok_cart_id)
        .where(KokCart.user_id == user_id)
    )
    try:
        result = await db.execute(stmt)
        cart_item = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"장바구니 항목 확인 SQL 실행 실패: user_id={user_id}, kok_cart_id={kok_cart_id}, error={str(e)}")
        raise
    
    if not cart_item:
        logger.warning(f"장바구니 항목을 찾을 수 없음: user_id={user_id}, kok_cart_id={kok_cart_id}")
        raise ValueError("장바구니 항목을 찾을 수 없습니다.")
    
    # 수량 변경
    cart_item.kok_quantity = kok_quantity
    
    return {
        "kok_cart_id": cart_item.kok_cart_id,
        "kok_price_id": cart_item.kok_price_id,
        "kok_quantity": cart_item.kok_quantity,
        "message": f"수량이 {kok_quantity}개로 변경되었습니다."
    }


async def delete_kok_cart_item(
    db: AsyncSession,
    user_id: int,
    kok_cart_id: int
) -> dict:
    """
    장바구니에서 상품 삭제
    """
    # 장바구니 항목 확인
    stmt = (
        select(KokCart)
        .where(KokCart.kok_cart_id == kok_cart_id)
        .where(KokCart.user_id == user_id)
    )
    try:
        result = await db.execute(stmt)
        cart_item = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"장바구니 항목 삭제 확인 SQL 실행 실패: user_id={user_id}, kok_cart_id={kok_cart_id}, error={str(e)}")
        return {"success": False, "message": "장바구니 항목 삭제 중 오류가 발생했습니다."}
    
    if not cart_item:
        logger.warning(f"삭제할 장바구니 항목을 찾을 수 없음: user_id={user_id}, kok_cart_id={kok_cart_id}")
        return {"success": False, "message": "장바구니 항목을 찾을 수 없습니다."}
    
    # 삭제할 항목 정보 저장
    deleted_info = {
        "kok_cart_id": cart_item.kok_cart_id,
        "kok_price_id": cart_item.kok_price_id,
        "kok_product_id": cart_item.kok_product_id,
        "kok_quantity": cart_item.kok_quantity
    }
    
    # 장바구니에서 삭제
    await db.delete(cart_item)
    
    return {
        "success": True,
        "message": "장바구니에서 상품이 삭제되었습니다.",
        "deleted_item": deleted_info
    }


# -----------------------------
# 검색 관련 CRUD 함수
# -----------------------------

async def get_ingredients_from_selected_cart_items(
    db: AsyncSession,
    user_id: int,
    selected_cart_ids: List[int]
) -> List[str]:
    """
    선택된 장바구니 상품들에서 재료명을 추출
    - 상품명에서 식재료 관련 키워드를 추출하여 반환
    - keyword_extraction.py의 로직을 사용하여 정확한 재료 추출
    """
    # logger.info(f"장바구니 상품에서 재료 추출 시작: user_id={user_id}, kok_cart_ids={selected_cart_ids}")

    if not selected_cart_ids:
        logger.warning("선택된 장바구니 항목이 없음")
        return []

    # 선택된 장바구니 상품들의 상품 정보 조회
    stmt = (
        select(KokCart, KokProductInfo)
        .join(KokProductInfo, KokCart.kok_product_id == KokProductInfo.kok_product_id)
        .where(KokCart.user_id == user_id)
        .where(KokCart.kok_cart_id.in_(selected_cart_ids))
    )

    try:
        result = await db.execute(stmt)
        cart_items = result.fetchall()
    except Exception as e:
        logger.error(f"선택된 장바구니 상품 조회 SQL 실행 실패: user_id={user_id}, kok_cart_ids={selected_cart_ids}, error={str(e)}")
        return []

    if not cart_items:
        logger.warning(f"장바구니 상품을 찾을 수 없음: user_id={user_id}, kok_cart_ids={selected_cart_ids}")
        return []

    # 표준 재료 어휘 로드 (TEST_MTRL.MATERIAL_NAME)
    ing_vocab = set()
    try:
        # 환경변수에서 자동으로 DB 설정을 가져와서 표준 재료 어휘 로드
        db_conf = get_homeshopping_db_config()
        ing_vocab = load_ing_vocab(db_conf)
    # logger.info(f"표준 재료 어휘 로드 완료: {len(ing_vocab)}개")
    except Exception as e:
        logger.error(f"표준 재료 어휘 로드 실패: {str(e)}")
    # logger.info("기본 키워드로 폴백하여 진행")
        # 실패 시 기본 키워드로 폴백
        ing_vocab = {
            "감자", "양파", "당근", "양배추", "상추", "시금치", "깻잎", "청경채", "브로콜리", "콜리플라워",
            "피망", "파프리카", "오이", "가지", "애호박", "고구마", "마늘", "생강", "대파", "쪽파",
            "돼지고기", "소고기", "닭고기", "양고기", "오리고기", "삼겹살", "목살", "등심", "안심",
            "새우", "고등어", "연어", "참치", "조기", "갈치", "꽁치", "고등어", "삼치", "전복",
            "홍합", "굴", "바지락", "조개", "새우", "게", "랍스터", "문어", "오징어", "낙지",
            "계란", "달걀", "우유", "치즈", "버터", "생크림", "요거트", "두부", "순두부", "콩나물",
            "숙주나물", "미나리", "깻잎", "상추", "치커리", "로메인", "아이스버그", "양상추", "적상추",
            "청상추", "배추", "무", "순무", "우엉", "연근", "토란", "토마토", "가지", "애호박",
            "호박", "단호박", "단감", "사과", "배", "복숭아", "자두", "포도", "딸기", "블루베리",
            "라즈베리", "블랙베리", "크랜베리", "오렌지", "레몬", "라임", "자몽", "귤", "한라봉",
            "천혜향", "레드향", "금귤", "유자", "석류", "무화과", "대추", "밤", "호두", "아몬드",
            "땅콩", "해바라기씨", "호박씨", "참깨", "들깨", "깨", "소금", "설탕", "간장", "된장",
            "고추장", "쌈장", "초고추장", "마요네즈", "케찹", "머스타드", "와사비", "겨자", "식초",
            "레몬즙", "라임즙", "올리브오일", "식용유", "참기름", "들기름", "고추기름", "마늘기름"
        }

    # 키워드 추출 로직 import
    extracted_ingredients = set()

    # 각 상품명에서 재료 키워드 추출
    for cart_item, product_info in cart_items:
        product_name = product_info.kok_product_name
        if not product_name:
            continue

    # logger.info(f"상품명 분석 중: {product_name}")

        try:
            # keyword_extraction.py의 고급 로직으로 재료 추출
            result = extract_ingredient_keywords(
                product_name=product_name,
                ing_vocab=ing_vocab,
                use_bigrams=True,      # 다단어 재료 매칭
                drop_first_token=True, # 브랜드명 제거
                strip_digits=True,     # 숫자/프로모션 제거
                keep_longest_only=True, # 가장 긴 키워드 우선
                max_fuzzy_try=1,       # 퍼지 매칭 시도 수 줄이기
                fuzzy_limit=1,         # 퍼지 결과 수 줄이기
                fuzzy_threshold=90     # 퍼지 임계값 높이기
            )

            if result and result.get("keywords"):
                keywords = result["keywords"]
                # 최대 1개만 추출하도록 제한
                if len(keywords) > 1:
                    keywords = [keywords[0]]  # 첫 번째 키워드만 사용
                extracted_ingredients.update(keywords)
                # logger.info(f"상품 '{product_name}'에서 추출된 키워드: {keywords}")
            else:
                logger.error(f"상품 '{product_name}'에서 키워드 추출 실패")

        except Exception as e:
            logger.error(f"상품 '{product_name}' 키워드 추출 중 오류: {str(e)}")
            continue

    # 중복 제거 및 정렬
    final_ingredients = sorted(list(extracted_ingredients))
    # logger.info(f"최종 추출된 재료: {final_ingredients}")
    return final_ingredients


async def get_ingredients_from_cart_product_ids(
    db: AsyncSession,
    kok_product_ids: List[int],
    homeshopping_product_ids: List[int] = None,
    unified_product_ids: List[int] = None
) -> List[str]:
    """
    장바구니에서 선택한 상품들의 kok_product_id와 homeshopping_product_ids를 받아서 키워드를 추출
    - KOK 상품: KOK_CLASSIFY 테이블에서 cls_ing이 1인 상품만 필터링
    - 홈쇼핑 상품: HOMESHOPPING_CLASSIFY 테이블에서 cls_ing이 1인 상품만 필터링
    - 통합 상품: 두 테이블 모두에서 cls_ing이 1인 상품을 찾아서 필터링
    - 해당 상품들의 product_name에서 키워드 추출
    - keyword_extraction.py의 고급 로직 사용
    
    Returns:
        List[str]: 추출된 키워드 목록
    """
    homeshopping_product_ids = homeshopping_product_ids or []
    unified_product_ids = unified_product_ids or []
    
    # 통합 파라미터가 있으면 기존 파라미터와 합치기
    if unified_product_ids:
        kok_product_ids = list(set(kok_product_ids + unified_product_ids))
        homeshopping_product_ids = list(set(homeshopping_product_ids + unified_product_ids))
    
    # logger.info(f"장바구니 상품 ID에서 재료 추출 시작: kok_product_ids={kok_product_ids}, homeshopping_product_ids={homeshopping_product_ids}")

    if not kok_product_ids and not homeshopping_product_ids:
        logger.warning("선택된 상품 ID가 없음")
        return []

    # KOK 상품 처리
    kok_products = []
    if kok_product_ids:
        stmt = (
            select(KokClassify)
            .where(KokClassify.product_id.in_(kok_product_ids))
            .where(KokClassify.cls_ing == 1)
        )
        try:
            result = await db.execute(stmt)
            kok_products = result.scalars().all()
            logger.info(f"KOK cls_ing이 1인 상품 {len(kok_products)}개 발견")
        except Exception as e:
            logger.error(f"KOK 상품 분류 조회 SQL 실행 실패: kok_product_ids={kok_product_ids}, error={str(e)}")
            kok_products = []

    # 홈쇼핑 상품 처리
    homeshopping_products = []
    if homeshopping_product_ids:
        stmt = (
            select(HomeshoppingClassify)
            .where(HomeshoppingClassify.product_id.in_(homeshopping_product_ids))
            .where(HomeshoppingClassify.cls_ing == 1)
        )
        try:
            result = await db.execute(stmt)
            homeshopping_products = result.scalars().all()
            # logger.info(f"홈쇼핑 cls_ing=1인 상품 {len(homeshopping_products)}개 발견")
        except Exception as e:
            logger.error(f"홈쇼핑 상품 분류 조회 SQL 실행 실패: homeshopping_product_ids={homeshopping_product_ids}, error={str(e)}")
            homeshopping_products = []

    # 모든 상품을 하나의 리스트로 합치기
    all_products = list(kok_products) + list(homeshopping_products)
    
    # 분류된 상품이 없으면 FCT_KOK_PRODUCT_INFO에서 직접 상품명 조회 (폴백)
    if not all_products and kok_product_ids:
        logger.warning(f"분류된 상품을 찾을 수 없음: kok_product_ids={kok_product_ids}, homeshopping_product_ids={homeshopping_product_ids}")
        # logger.info("FCT_KOK_PRODUCT_INFO에서 직접 상품명 조회 시도 (폴백)")
        
        # FCT_KOK_PRODUCT_INFO에서 상품명 조회
        product_stmt = (
            select(KokProductInfo)
            .where(KokProductInfo.kok_product_id.in_(kok_product_ids))
        )
        try:
            product_result = await db.execute(product_stmt)
            products = product_result.scalars().all()
        except Exception as e:
            logger.error(f"폴백 상품명 조회 SQL 실행 실패: kok_product_ids={kok_product_ids}, error={str(e)}")
            products = []
        
        if products:
            # KokClassify 형태로 변환
            for product in products:
                temp_classify = type('TempClassify', (), {
                    'product_id': product.kok_product_id,
                    'product_name': product.kok_product_name,
                    'cls_ing': 1  # 임시로 1로 설정
                })()
                all_products.append(temp_classify)
            
        # logger.info(f"FCT_KOK_PRODUCT_INFO에서 {len(all_products)}개 상품 발견 (폴백)")
        else:
            logger.warning(f"FCT_KOK_PRODUCT_INFO에서도 상품을 찾을 수 없음: kok_product_ids={kok_product_ids}")
    
    if not all_products:
        logger.warning(f"모든 방법으로 상품을 찾을 수 없음: kok_product_ids={kok_product_ids}, homeshopping_product_ids={homeshopping_product_ids}")
        return []

    # logger.info(f"총 {len(all_products)}개 상품에서 키워드 추출 시작")

    # 표준 재료 어휘 로드 (TEST_MTRL.MATERIAL_NAME)
    ing_vocab = set()
    try:
        # 환경변수에서 자동으로 DB 설정을 가져와서 표준 재료 어휘 로드
        db_conf = get_homeshopping_db_config()
        ing_vocab = load_ing_vocab(db_conf)
        # logger.info(f"표준 재료 어휘 로드 완료: {len(ing_vocab)}개")
    except Exception as e:
        logger.error(f"표준 재료 어휘 로드 실패: {str(e)}")
        # logger.info("기본 키워드로 폴백하여 진행")
        # 실패 시 기본 키워드로 폴백
        ing_vocab = {
            "감자", "양파", "당근", "양배추", "상추", "시금치", "깻잎", "청경채", "브로콜리", "콜리플라워",
            "피망", "파프리카", "오이", "가지", "애호박", "고구마", "마늘", "생강", "대파", "쪽파",
            "돼지고기", "소고기", "닭고기", "양고기", "오리고기", "삼겹살", "목살", "등심", "안심",
            "새우", "고등어", "연어", "참치", "조기", "갈치", "꽁치", "고등어", "삼치", "전복",
            "홍합", "굴", "바지락", "조개", "새우", "게", "랍스터", "문어", "오징어", "낙지",
            "계란", "달걀", "우유", "치즈", "버터", "생크림", "요거트", "두부", "순두부", "콩나물",
            "숙주나물", "미나리", "깻잎", "상추", "치커리", "로메인", "아이스버그", "양상추", "적상추",
            "청상추", "배추", "무", "순무", "우엉", "연근", "토란", "토마토", "가지", "애호박",
            "호박", "단호박", "단감", "사과", "배", "복숭아", "자두", "포도", "딸기", "블루베리",
            "라즈베리", "블랙베리", "크랜베리", "오렌지", "레몬", "라임", "자몽", "귤", "한라봉",
            "천혜향", "레드향", "금귤", "유자", "석류", "무화과", "대추", "밤", "호두", "아몬드",
            "땅콩", "해바라기씨", "호박씨", "참깨", "들깨", "깨", "소금", "설탕", "간장", "된장",
            "고추장", "쌈장", "초고추장", "마요네즈", "케찹", "머스타드", "와사비", "겨자", "식초",
            "레몬즙", "라임즙", "올리브오일", "식용유", "참기름", "들기름", "고추기름", "마늘기름"
        }

    # 키워드 추출 로직
    extracted_ingredients = set()

    # 각 상품명에서 재료 키워드 추출
    for classified_product in all_products:
        product_name = classified_product.product_name
        if not product_name:
            continue

    # logger.info(f"상품명 분석 중: {product_name}")

        try:
            # keyword_extraction.py의 고급 로직으로 재료 추출
            result = extract_ingredient_keywords(
                product_name=product_name,
                ing_vocab=ing_vocab,
                use_bigrams=True,      # 다단어 재료 매칭
                drop_first_token=True, # 브랜드명 제거
                strip_digits=True,     # 숫자/프로모션 제거
                keep_longest_only=True, # 가장 긴 키워드 우선
                max_fuzzy_try=1,       # 퍼지 매칭 시도 수 줄이기
                fuzzy_limit=1,         # 퍼지 결과 수 줄이기
                fuzzy_threshold=90     # 퍼지 임계값 높이기
            )

            if result and result.get("keywords"):
                keywords = result["keywords"]
                # 최대 1개만 추출하도록 제한
                if len(keywords) > 1:
                    keywords = [keywords[0]]  # 첫 번째 키워드만 사용
                extracted_ingredients.update(keywords)
                
                # 키워드만 추출하여 저장
                # logger.info(f"상품 '{product_name}'에서 추출된 키워드: {keywords}")
            else:
                logger.error(f"상품 '{product_name}'에서 키워드 추출 실패")
                
        except Exception as e:
            logger.error(f"상품 '{product_name}' 키워드 추출 중 오류: {str(e)}")
            continue

    # 중복 제거 및 정렬
    final_ingredients = sorted(list(extracted_ingredients))
    # logger.info(f"최종 추출된 재료: {final_ingredients}")
    return final_ingredients


async def get_cart_product_names_by_ids(
    db: AsyncSession,
    kok_product_ids: List[int]
) -> List[str]:
    """
    kok_product_id 목록으로 상품명 목록을 조회
    """
    if not kok_product_ids:
        return []

    stmt = (
        select(KokProductInfo.kok_product_name)
        .where(KokProductInfo.kok_product_id.in_(kok_product_ids))
        .where(KokProductInfo.kok_product_name.isnot(None))
    )
    
    try:
        result = await db.execute(stmt)
        product_names = [row[0] for row in result.fetchall() if row[0]]
    except Exception as e:
        logger.error(f"상품명 조회 SQL 실행 실패: kok_product_ids={kok_product_ids}, error={str(e)}")
        return []
    
    return product_names
