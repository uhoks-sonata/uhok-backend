# -*- coding: utf-8 -*-
"""
통합 키워드 추출 모듈
- 장바구니 상품명에서 **레시피 표준 재료명**(ing_vocab)에 해당하는 키워드를 추출하는 모듈
- KOK, 홈쇼핑, 레시피 서비스에서 공통으로 사용

핵심 아이디어
- 상품명 정규화(괄호/특수문자/숫자/프로모션 심벌 제거)
- 토큰화 시 맨 앞 한 단어(브랜드로 가정) 제거
- 포장/프로모션/단위 등의 노이즈 토큰 삭제
- 파생형(즙/가루/엑기스/오일/소스 등)은 **원물로 매칭 금지**
- 사전(ing_vocab)과 **정확 일치** 우선, 필요할 때만 **퍼지(오타) 매칭** 보조
- 결과가 여러개면 **가장 긴 키워드만** 남기는 옵션(ex "오이", "청오이" → "청오이"만)

참고:
- syn_map은 "국물멸치 → 멸치" 같은 **화이트리스트** 치환만 넣어야 함
  (즙/가루 같은 파생형을 '원물'로 치환하면 안 됨)
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Set, Any
from urllib.parse import urlparse, unquote
import pymysql
from common.config import get_settings

# (선택) 퍼지매칭 : RapidFuzz가 설치되어 있으면 오타 교정/근사 매칭에 사용
# 기본값은 OFF. 정확 일치가 없고, 옵션을 켰을 때만 사용
try:
    from rapidfuzz import process, fuzz  # type: ignore
    _HAS_RAPIDFUZZ = True
except Exception:
    process = None  # type: ignore
    fuzz = None     # type: ignore
    _HAS_RAPIDFUZZ = False

# ----- 도메인 사전 -----
# 재료와 무관한 수식어/프로모션/등급 등: 후보에서 제거
STOPWORDS: Set[str] = {
    "국내산","수입산","유기농","무항생제","무첨가","무가당","저염","저지방",
    "특대","대","중","소","대용량","특가","행사","정품","본품","벌크",
    "혼합","혼합팩","구성","구성품","증정","사은품","산지","수제","슬라이스",
    "구이","볶음","국물용","세척","찜","튀김","프리미엄"
}

# 포장/묶음 관련 토큰: 후보에서 제거
PACK_TOKENS: Set[str] = {
    "세트","팩","봉","입","구","개","박스","box","BOX","스틱","포","파우치","캔","병","PET"
}

# 단위 토큰: 숫자를 지운 뒤 남을 수 있어 명시적으로 제거
UNIT_TOKENS: Set[str] = {"kg","g","ml","l"}

# 공백 없이 붙는 파생형(원물 뒤에 붙는 접미사) 금지 목록
# ex) "양배추즙", "양배추가루" → "양배추"로 매칭 금지
BANNED_DERIV_SUFFIX_NS: Set[str] = {
    "즙","분말","가루","엑기스","추출물","농축액","오일","유","시럽","퓨레","페이스트",
    "환","정","캡슐","알","스낵","칩","후레이크","플레이크","분","액","액상"
}

# 공백으로 분리되는 파생형 토큰 금지 목록 (base + '즙', base + '소스' 등)
BANNED_DERIV_TOKENS: Set[str] = {
    "즙","분말","가루","엑기스","추출물","농축액","오일","유","소스","드레싱","양념","장",
    "시럽","퓨레","페이스트","환","정","캡슐","알","스낵","칩","후레이크","플레이크","향","향미유","액상"
}

# ---- 정규식 패턴 모음 ----
# 괄호류는 공백으로 치환해 토큰 경계 유지
PAREN_RX  = re.compile(r"[\(\)\[\]\{\}]")
# 노이즈 문자(한글/영문/숫자/일부 구분자 제외)를 공백으로 치환
NOISE_RX  = re.compile(r"[^\w\s가-힣/·.-]")
# 모든 숫자 제거(1+1, 10봉, 500g 등은 의미 없음)
DIGIT_RX  = re.compile(r"\d+")

# ---- DB 연결/헬퍼 ----
def parse_mariadb_url(dsn: str | None) -> dict[str, Any] | None:
    """MariaDB URL을 파싱하여 연결 정보를 반환"""
    if not dsn:
        return None
    u = urlparse(dsn)
    host = u.hostname or "localhost"
    port = int(u.port or 3306)
    user = unquote(u.username or "")
    password = unquote(u.password or "")
    database = (u.path or "").lstrip("/") or ""
    return {"host": host, "port": port, "user": user, "password": password, "database": database}

def connect_mysql(host: str, port: int, user: str, password: str, database: str):
    """
    PyMySQL 커넥션 생성
    - autocommit=False : SELECT에는 영향 없고, INSERT/UPDATE 시 트랜잭션 제어 가능
    - charset='utf8mb4' : 이모지/한글 안전
    """
    return pymysql.connect(
        host=host, port=port, user=user, password=password, database=database,
        charset="utf8mb4", autocommit=False
    )

def load_ing_vocab(db_conf: dict) -> set[str]:
    """
    레시피 '표준 재료 어휘'를 메모리(set)로 로드. 
    - TEST_MTRL.MATERIAL_NAME의 DISTINCT 집합을 만들기 위한 쿼리
    - 여기서는 DISTINCT를 SQL에서 직접 쓰지 않고, 파이썬 set으로 중복 제거
    """
    conn = connect_mysql(**db_conf)
    try:
        vocab: set[str] = set()
        sql = """
            SELECT MATERIAL_NAME
            FROM TEST_MTRL
            WHERE MATERIAL_NAME IS NOT NULL AND MATERIAL_NAME <> ''
        """
        with conn.cursor() as cur:
            cur.execute(sql)
            for (name,) in cur.fetchall():
                if name:
                    vocab.add(str(name).strip())
        return vocab
    finally:
        conn.close()

def get_homeshopping_db_config() -> Dict[str, Any]:
    """홈쇼핑용 MariaDB 설정을 반환"""
    settings = get_settings()
    
    # mariadb_service_url에서 DB 설정 파싱
    service_url = urlparse(settings.mariadb_service_url)
    return {
        "host": service_url.hostname or "localhost",
        "port": service_url.port or 3306,
        "user": service_url.username or "",
        "password": service_url.password or "",
        "database": service_url.path.lstrip("/") or ""
    }

def load_homeshopping_ing_vocab() -> Set[str]:
    """홈쇼핑용 표준 재료 어휘를 로드"""
    db_conf = get_homeshopping_db_config()
    return load_ing_vocab(db_conf)

# ---- 키워드 추출 핵심 함수들 ----
def normalize_name(s: str, *, strip_digits: bool = True) -> str:
    """
    상품명을 추출 친화적으로 정규화
    - 괄호 → 공백
    - / 구분자 → 공백 (알감자/설봉감자 → 알감자 설봉감자)
    - (옵션) 모든 숫자 제거 + 1+1, x, × 같은 프로모션/곱기호 제거
    - 잔여 특수문자 제거
    - 다중 공백 압축
    """
    s = (s or "").strip()
    s = s.replace("＋","+").replace("—","-").replace("·"," ")
    s = s.replace("/", " ")  # / 구분자를 공백으로 치환
    s = PAREN_RX.sub(" ", s)
    if strip_digits:
        s = DIGIT_RX.sub(" ", s)
        s = re.sub(r"[+×xX]", " ", s)
    s = NOISE_RX.sub(" ", s)
    return " ".join(s.split())

def _safe_lower(t: str) -> str:
    """영문 소문자화(한글 영향 없음). 예외 발생 시 원문 반환"""
    try:
        return t.lower()
    except Exception:
        return t

def split_tokens(s: str, *, drop_first_token: bool = True) -> list[str]:
    """공백 기준 토큰화
    홈쇼핑/콕 패턴 : 맨 앞 한 단어는 브랜드로 가정하고 제거(drop_first_token=True가 기본)"""
    toks = [_safe_lower(t.strip()) for t in s.split() if t.strip()]
    if drop_first_token and toks:
        toks = toks[1:]
    return toks

def make_ngrams(tokens: list[str], n: int = 2) -> list[str]:
    """
    바이그램 이상 N그램 후보 생성
    - 예: ["돼지고기", "안심"] → ["돼지고기 안심"]
    - 다단어 재료(예: "돼지고기 안심", "청양고추") 매칭 향상
    """
    out: list[str] = []
    for k in range(2, n+1):
        for i in range(len(tokens)-k+1):
            out.append(" ".join(tokens[i:i+k]))
    return out

def is_noise_token(t: str) -> bool:
    """사전에 정의한 노이즈 토큰(STOP/포장/단위) 여부"""
    return (t in STOPWORDS) or (t in PACK_TOKENS) or (t in UNIT_TOKENS)

def is_derivative_form(base: str, cand: str) -> bool:
    """
    cand(후보)가 base(원물)의 **가공/추출 파생형**이면 Ture
    - base 바로 뒤에 한글/영문이 붙으면 파생형(ex: 양배추즙, 양배추가루)
    - base [공백] 금지토큰 조합도 파생형(ex: 양배추 즙, 마늘 소스)"""
    if cand == base:
        return False
    if cand.startswith(base):
        rest = cand[len(base):]
        if re.match(r'^[가-힣A-Za-z]', rest):
            return True
        rest_clean = re.sub(r"[0-9%+\-_/\. ]+", "", rest)
        if rest_clean in BANNED_DERIV_SUFFIX_NS:
            return True
    if " " in cand:
        parts = cand.split()
        for i, p in enumerate(parts):
            if p == base and i+1 < len(parts) and parts[i+1] in BANNED_DERIV_TOKENS:
                return True
    return False

def fuzzy_pick(term: str, vocab: Set[str], limit: int = 2, threshold: int = 88) -> list[str]:
    """
    퍼지(오타) 매칭 보조
    - RapidFuzz가 설치되어 있고, 정확 일치가 하나도 없을 때만 사용 권장
    - threshold(기본 88) 이상만 채택 → 보수적으로 동작
    - return: 상위 'limit'개 정답 후보(표준명)
    """
    if not _HAS_RAPIDFUZZ:
        return []
    res = process.extract(term, vocab, scorer=fuzz.WRatio, limit=limit)
    return [k for k, score, _ in res if score >= threshold]

def _is_whole_word_in(short: str, long: str) -> bool:
    """
    공백 경계 기준 포함 여부
    - short가 long 안에 단어 경계로 포함되면 True
    - 예: short = '오이', long= '청오이'는 False(붙어 있어서 단어 경계가 아님)
          short = '오이', long='오이 피클'은 True
    """
    return re.search(rf'(?<!\S){re.escape(short)}(?!\S)', long) is not None

def _filter_longest_only(keys: list[str]) -> list[str]:
    """여러 키워드가 잡힌 경우, **더 긴 것**만 남기고 짧은 단어 제거"""
    kept: list[str] = []
    for k in sorted(keys, key=len, reverse=True):
        if any(_is_whole_word_in(k, L) for L in kept):
            continue
        kept.append(k)
    return kept

def extract_ingredient_keywords(
    product_name: str,
    ing_vocab: Set[str],                     # 표준 재료명 집합(TEST_MTRL.MATERIAL_NAME DISTINCT)
    syn_map: Dict[str, str] | None = None,   # 동의어 치환(화이트리스트)
    *,
    use_bigrams: bool = True,                # 다단어 재료 매칭 향상
    drop_first_token: bool = True,           # 맨 앞(브랜드) 제거
    strip_digits: bool = True,               # 숫자/곱표기 제거
    max_fuzzy_try: int = 0,                  # 퍼지 후보로 시도할 토큰 수(0이면 퍼지 OFF)
    fuzzy_limit: int = 0,                    # 퍼지로 고를 결과 수(0이면 퍼지 OFF)
    fuzzy_threshold: int = 88,               # 퍼지 임계(높을수록 보수적)
    keep_longest_only: bool = True,          # 여러 개일 때 가장 긴 것만 유지
) -> Dict[str, object]:
    """
    상품명에서 식재료 키워드 추출 (메인 함수)
    """
    syn_map = syn_map or {}
    original = product_name
    # 1) 정규화(숫자/곱표기 제거 등)
    s = normalize_name(product_name, strip_digits=strip_digits)

    # 2) 토큰화(브랜드 제거 옵션)
    tokens = split_tokens(s, drop_first_token=drop_first_token)

    # 3) 노이즈/가공 토큰 제거
    tokens = [t for t in tokens if not is_noise_token(t)]
    tokens = [t for t in tokens if t not in BANNED_DERIV_TOKENS]

    # 4) 후보 생성: 유니그램 + (옵션) 바이그램
    candidates = list(tokens)
    if use_bigrams:
        candidates += make_ngrams(tokens, n=2)

    # 5) 동의어 치환(화이트리스트)
    mapped = [syn_map.get(c, c) for c in candidates]

    # 6) 정확 일치 우선
    exact_hits = [m for m in mapped if m in ing_vocab]
    clean_hits: list[str] = list(exact_hits)

    # 7) 필요할 때만 퍼지(오타) 보조
    if not clean_hits and max_fuzzy_try > 0 and fuzzy_limit > 0:
        for c in sorted(set(mapped), key=len, reverse=True)[:max_fuzzy_try]:
            for p in fuzzy_pick(c, ing_vocab, limit=fuzzy_limit, threshold=fuzzy_threshold):
                if not is_derivative_form(p, c):
                    clean_hits.append(p)

    # 8) 정렬(길이 우선) + 중복 제거
    final_keys = list(dict.fromkeys(sorted(clean_hits, key=len, reverse=True)))
    
    # 9) 여러 개면 가장 긴 키워드만 유지(옵션)
    if keep_longest_only and len(final_keys) > 1:
        final_keys = _filter_longest_only(final_keys)

    # 10) 결과 + 디버그
    return {
        "keywords": final_keys,
        "debug": {
            "original": original,
            "normalized": s,
            "dropped_first_token": (s.split()[0] if s.split() else ""),
            "tokens": tokens,
            "candidates": candidates,
            "mapped": mapped,
            "exact_hits": exact_hits,
        },
    }

# ---- 서비스별 특화 함수들 ----
def extract_kok_keywords(
    product_name: str,
    ing_vocab: Set[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    KOK 상품명에서 식재료 키워드 추출
    
    Args:
        product_name: KOK 상품명
        ing_vocab: 표준 재료명 집합 (None이면 자동 로드)
        **kwargs: extract_ingredient_keywords 함수에 전달할 추가 파라미터
    
    Returns:
        키워드와 디버그 정보가 포함된 딕셔너리
    """
    # 어휘 사전이 제공되지 않으면 자동 로드
    if ing_vocab is None:
        db_conf = parse_mariadb_url(get_settings().mariadb_service_url)
        if db_conf:
            ing_vocab = load_ing_vocab(db_conf)
        else:
            ing_vocab = set()
    
    # 기본 파라미터 설정 (KOK에 최적화)
    default_params = {
        "use_bigrams": True,
        "drop_first_token": True,
        "strip_digits": True,
        "keep_longest_only": True,
        "max_fuzzy_try": 1,      # KOK는 보수적으로
        "fuzzy_limit": 2,
        "fuzzy_threshold": 90    # KOK는 높은 임계값
    }
    
    # 사용자 파라미터로 기본값 덮어쓰기
    default_params.update(kwargs)
    
    return extract_ingredient_keywords(
        product_name=product_name,
        ing_vocab=ing_vocab,
        **default_params
    )

def extract_homeshopping_keywords(
    product_name: str,
    ing_vocab: Set[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    홈쇼핑 상품명에서 식재료 키워드 추출
    
    Args:
        product_name: 홈쇼핑 상품명
        ing_vocab: 표준 재료명 집합 (None이면 자동 로드)
        **kwargs: extract_ingredient_keywords 함수에 전달할 추가 파라미터
    
    Returns:
        키워드와 디버그 정보가 포함된 딕셔너리
    """
    # 어휘 사전이 제공되지 않으면 자동 로드
    if ing_vocab is None:
        ing_vocab = load_homeshopping_ing_vocab()
    
    # 기본 파라미터 설정 (홈쇼핑에 최적화)
    default_params = {
        "use_bigrams": True,
        "drop_first_token": True,
        "strip_digits": True,
        "keep_longest_only": True,
        "max_fuzzy_try": 2,      # 홈쇼핑은 좀 더 관대하게
        "fuzzy_limit": 3,
        "fuzzy_threshold": 85    # 홈쇼핑은 좀 더 관대하게
    }
    
    # 사용자 파라미터로 기본값 덮어쓰기
    default_params.update(kwargs)
    
    return extract_ingredient_keywords(
        product_name=product_name,
        ing_vocab=ing_vocab,
        **default_params
    )

def extract_recipe_keywords(
    product_name: str,
    ing_vocab: Set[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    레시피 관련 상품명에서 식재료 키워드 추출
    
    Args:
        product_name: 레시피 관련 상품명
        ing_vocab: 표준 재료명 집합 (None이면 자동 로드)
        **kwargs: extract_ingredient_keywords 함수에 전달할 추가 파라미터
    
    Returns:
        키워드와 디버그 정보가 포함된 딕셔너리
    """
    # 어휘 사전이 제공되지 않으면 자동 로드
    if ing_vocab is None:
        db_conf = parse_mariadb_url(get_settings().mariadb_service_url)
        if db_conf:
            ing_vocab = load_ing_vocab(db_conf)
        else:
            ing_vocab = set()
    
    # 기본 파라미터 설정 (레시피에 최적화)
    default_params = {
        "use_bigrams": True,
        "drop_first_token": False,  # 레시피는 브랜드 제거 안함
        "strip_digits": True,
        "keep_longest_only": True,
        "max_fuzzy_try": 1,         # 레시피는 보수적으로
        "fuzzy_limit": 2,
        "fuzzy_threshold": 92       # 레시피는 매우 높은 임계값
    }
    
    # 사용자 파라미터로 기본값 덮어쓰기
    default_params.update(kwargs)
    
    return extract_ingredient_keywords(
        product_name=product_name,
        ing_vocab=ing_vocab,
        **default_params
    )

# ---- 유틸리티 함수들 ----
def is_homeshopping_product(product_name: str) -> bool:
    """홈쇼핑 상품명인지 확인하는 간단한 검증"""
    if not product_name or not isinstance(product_name, str):
        return False
    
    # 홈쇼핑 상품명의 일반적인 패턴 확인
    normalized = normalize_name(product_name, strip_digits=False)
    
    # 홈쇼핑 특화 키워드가 포함되어 있는지 확인
    homeshopping_indicators = [
        "특가", "행사", "할인", "증정", "사은품", "구성품",
        "팩", "봉", "입", "구", "개", "박스", "세트",
        "kg", "g", "ml", "l", "톤", "근", "두", "말"
    ]
    
    return any(indicator in normalized for indicator in homeshopping_indicators)

def get_keyword_stats(product_names: list[str], service_type: str = "auto", **kwargs) -> Dict[str, Any]:
    """
    상품명 리스트에서 키워드 추출 통계 반환
    
    Args:
        product_names: 상품명 리스트
        service_type: 서비스 타입 ("kok", "homeshopping", "recipe", "auto")
        **kwargs: 키워드 추출 함수에 전달할 추가 파라미터
    
    Returns:
        통계 정보가 포함된 딕셔너리
    """
    if not product_names:
        return {
            "total_products": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "total_keywords": 0,
            "average_keywords_per_product": 0,
            "most_common_keywords": []
        }
    
    # 서비스 타입에 따른 키워드 추출 함수 선택
    if service_type == "kok":
        extract_func = extract_kok_keywords
    elif service_type == "homeshopping":
        extract_func = extract_homeshopping_keywords
    elif service_type == "recipe":
        extract_func = extract_recipe_keywords
    else:  # auto
        # 첫 번째 상품명으로 서비스 타입 자동 감지
        if product_names and is_homeshopping_product(product_names[0]):
            extract_func = extract_homeshopping_keywords
        else:
            extract_func = extract_kok_keywords
    
    # 키워드 추출 실행
    results = []
    all_keywords = []
    
    for product_name in product_names:
        try:
            result = extract_func(product_name, **kwargs)
            results.append(result)
            all_keywords.extend(result["keywords"])
        except Exception as e:
            results.append({"keywords": [], "error": str(e)})
    
    # 통계 계산
    successful_extractions = sum(1 for r in results if r["keywords"] and "error" not in r)
    failed_extractions = len(product_names) - successful_extractions
    total_keywords = len(all_keywords)
    avg_keywords = total_keywords / len(product_names) if product_names else 0
    
    # 가장 많이 나온 키워드 (상위 10개)
    from collections import Counter
    keyword_counts = Counter(all_keywords)
    most_common = keyword_counts.most_common(10)
    
    return {
        "total_products": len(product_names),
        "successful_extractions": successful_extractions,
        "failed_extractions": failed_extractions,
        "total_keywords": total_keywords,
        "average_keywords_per_product": round(avg_keywords, 2),
        "most_common_keywords": [{"keyword": kw, "count": count} for kw, count in most_common],
        "service_type": service_type
    }

# ----- 홈쇼핑 전용 함수들 -----
def extract_homeshopping_keywords_simple(
    product_name: str,
    ing_vocab: set[str] | None = None,
    **kwargs
) -> list[str]:
    """
    홈쇼핑 상품명에서 키워드를 추출하는 간단한 함수
    자동으로 홈쇼핑 DB 설정을 사용하여 재료 사전을 로드합니다.
    
    Args:
        product_name: 홈쇼핑 상품명
        ing_vocab: 재료 사전 (None이면 자동 로드)
        **kwargs: extract_ingredient_keywords에 전달할 추가 옵션
    
    Returns:
        추출된 키워드 리스트
    """
    if ing_vocab is None:
        ing_vocab = load_homeshopping_ing_vocab()
    
    return extract_ingredient_keywords(product_name, ing_vocab, **kwargs)

def load_homeshopping_ing_vocab() -> set[str]:
    """
    홈쇼핑 서비스용 재료 사전을 로드합니다.
    
    Returns:
        재료 사전 (set)
    """
    db_conf = get_homeshopping_db_config()
    if not db_conf:
        return set()
    
    return load_ing_vocab(db_conf)

def get_homeshopping_db_config() -> dict[str, Any] | None:
    """
    홈쇼핑 서비스용 MariaDB 설정을 반환합니다.
    
    Returns:
        DB 연결 설정 딕셔너리 또는 None
    """
    settings = get_settings()
    return parse_mariadb_url(settings.mariadb_service_url)

def is_homeshopping_product(product_name: str) -> bool:
    """
    주어진 상품명이 홈쇼핑 상품인지 판단합니다.
    
    Args:
        product_name: 상품명
    
    Returns:
        홈쇼핑 상품 여부
    """
    # 홈쇼핑 상품의 특징적인 패턴들을 확인
    homeshopping_patterns = [
        r'홈쇼핑',
        r'방송',
        r'TV',
        r'특가',
        r'행사',
        r'프로모션',
        r'세일'
    ]
    
    for pattern in homeshopping_patterns:
        if re.search(pattern, product_name, re.IGNORECASE):
            return True
    
    return False

# ----- 공통 키워드 추출 함수들 -----
def extract_core_keywords(
    product_name: str, 
    max_n: int = 3,
    service_type: str = "auto"
) -> List[str]:
    """
    상품명에서 핵심 키워드를 추출하는 공통 함수
    
    Args:
        product_name: 상품명
        max_n: 최대 키워드 수
        service_type: 서비스 타입 ("kok", "homeshopping", "recipe", "auto")
    
    Returns:
        핵심 키워드 리스트
    """
    # 서비스별 최적화된 키워드 추출 실행
    if service_type == "kok":
        result = extract_kok_keywords(product_name)
    elif service_type == "homeshopping":
        result = extract_homeshopping_keywords(product_name)
    elif service_type == "recipe":
        result = extract_recipe_keywords(product_name)
    else:  # auto
        if is_homeshopping_product(product_name):
            result = extract_homeshopping_keywords(product_name)
        else:
            result = extract_kok_keywords(product_name)
    
    keywords = result.get("keywords", [])
    return keywords[:max_n]

def extract_tail_keywords(
    product_name: str, 
    max_n: int = 2,
    service_type: str = "auto"
) -> List[str]:
    """
    상품명에서 뒤쪽 핵심 키워드를 추출하는 공통 함수
    
    Args:
        product_name: 상품명
        max_n: 최대 키워드 수
        service_type: 서비스 타입 ("kok", "homeshopping", "recipe", "auto")
    
    Returns:
        뒤쪽 핵심 키워드 리스트
    """
    # 서비스별 최적화된 키워드 추출 실행
    if service_type == "kok":
        result = extract_kok_keywords(product_name)
    elif service_type == "homeshopping":
        result = extract_homeshopping_keywords(product_name)
    elif service_type == "recipe":
        result = extract_recipe_keywords(product_name)
    else:  # auto
        if is_homeshopping_product(product_name):
            result = extract_homeshopping_keywords(product_name)
        else:
            result = extract_kok_keywords(product_name)
    
    keywords = result.get("keywords", [])
    # 뒤쪽에서 max_n개 선택
    return keywords[-max_n:] if len(keywords) > max_n else keywords
