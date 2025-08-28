# -*- coding: utf-8 -*-
"""
추천 오케스트레이터
- 후보 게이트(LIKE): (tail 핵심 + core/roots + 동적 n-gram)
- 후보 내 pgvector 정렬 → 상세/가격 조인
- 최종 OR 필터: tail ≥1 OR n-gram ≥1
- 결과는 최대 k개(기본 5). 모자라면 있는 만큼, 없으면 빈 리스트.
"""

import os, re, yaml
from typing import Dict, List, Tuple, Union, Set
from collections import Counter
from dotenv import load_dotenv
load_dotenv()

# ---- 환경 기본값 ----
RERANK_MODE_DEFAULT = os.getenv("RERANK_MODE", "off").lower().strip()

# -------------------- 동적 파라미터 --------------------
def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except Exception:
        return default

# LIKE 검색/키워드 확장 파라미터
DYN_MAX_TERMS   = _env_int("DYN_MAX_TERMS", 32)
DYN_MAX_EXTRAS  = _env_int("DYN_MAX_EXTRAS", 20)
DYN_SAMPLE_ROWS = _env_int("DYN_SAMPLE_ROWS", 4000)

# Tail / n-gram 필터 동작 파라미터
TAIL_MAX_DF_RATIO = float(os.getenv("TAIL_MAX_DF_RATIO", "0.35"))
TAIL_MAX_TERMS    = _env_int("TAIL_MAX_TERMS", 3)
NGRAM_N           = _env_int("NGRAM_N", 2)

# n-gram 생성 범위
DYN_NGRAM_MIN  = _env_int("DYN_NGRAM_MIN", 2)
DYN_NGRAM_MAX  = max(DYN_NGRAM_MIN, _env_int("DYN_NGRAM_MAX", 4))

# (참고용) 선택 규칙/카운트 범위가 필요하면 여기에 추가해 사용
DYN_COUNT_MIN  = _env_int("DYN_COUNT_MIN", 3)
DYN_COUNT_MAX  = _env_int("DYN_COUNT_MAX", 30000)

# -------------------- 사전/패턴 --------------------
DEFAULT_STOPWORDS: Set[str] = set("""
세트 선물세트 모음 모음전 구성 증정 행사 정품 정기 무료 특가 사은품 선물 혼합 혼합세트 묶음 총 택
옵션 국내산 수입산 무료배송 당일 당일발송 예약 신상 히트 인기 추천 기획 기획세트 명품 프리미엄 리미티드
한정 본품 리뉴얼 정가 정상가 행사상품 대용량 소용량 박스 리필 업소용 가정용 편의점 오리지널 리얼 신제품 공식 단독
정기구독 구독 사은 혜택 특전 한정판 고당도 산지 당일 당일직송 직송 손질 세척 냉동 냉장 생물 해동 숙성
팩 봉 포 개 입 병 캔 스틱 정 포기 세트구성 골라담기 택1 택일 실속 못난이 파우치 슬라이스 인분 종
""".split())

DEFAULT_ROOT_HINTS = [
    "육수","다시","사골","곰탕","장국","티백","멸치","황태","디포리","가쓰오","가다랭이",
    "주꾸미","쭈꾸미","오징어","한치","문어","낙지","새우","꽃게","홍게","대게","게",
    "김치","포기김치","열무김치","갓김치","동치미","만두","교자","왕교자","라면","우동","국수","칼국수","냉면",
    "사리","메밀","막국수","어묵","오뎅","두부","순두부","유부","우유","치즈","요거트","버터",
    "닭","닭가슴살","닭다리","닭안심","돼지","돼지고기","삼겹살","목살","소고기","한우","양지","사태","갈비","차돌",
    "식용유","참기름","들기름","설탕","소금","고추장","된장","간장","쌈장","고춧가루","카레","짜장","분말",
    "명란","명란젓","젓갈","어란","창란","창란젓","오징어젓","낙지젓",
]
DEFAULT_STRONG_NGRAMS = ["사골곰탕","포기김치","왕교자","어묵탕","갈비탕","육개장","사골국물","황태채","국물티백"]
DEFAULT_VARIANTS = {
    "주꾸미": ["쭈꾸미"],
    "가쓰오": ["가츠오","가쓰오부시","가츠오부시"],
    "명태":   ["북어"],
    "어묵":   ["오뎅"],
    "백명란": ["명란","명란젓"],
}

_MEAS1   = re.compile(r"\d+(?:\.\d+)?\s*(?:g|kg|ml|l|L)?\s*(?:[xX×＊*]\s*\d+)?", re.I)
_MEAS2   = re.compile(r"\b\d+[a-zA-Z]+\b")
_ONLYNUM = re.compile(r"\b\d+\b")
_HANGUL_ONLY = re.compile(r"^[가-힣]{2,}$")

def _load_yaml(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def load_domain_dicts() -> Dict:
    """CATEGORY_DICT_PATH/KEYWORDS_DICT_PATH가 있으면 결합하여 로딩."""
    cat_path = os.getenv("CATEGORY_DICT_PATH", "").strip()
    key_path = os.getenv("KEYWORDS_DICT_PATH", "").strip()

    roots = set(DEFAULT_ROOT_HINTS)
    strong = set(DEFAULT_STRONG_NGRAMS)
    variants = {k:list(v) for k,v in DEFAULT_VARIANTS.items()}
    stopwords = set(DEFAULT_STOPWORDS)

    if cat_path and os.path.exists(cat_path):
        cat = _load_yaml(cat_path)
        for _, rule in (cat.get("categories") or {}).items():
            detect = rule.get("detect") or rule.get("match") or []
            like   = rule.get("candidate_like") or rule.get("like_extra") or []
            excl   = rule.get("exclude") or []
            roots.update(detect); roots.update(like); stopwords.update(excl)

    if key_path and os.path.exists(key_path):
        kd = _load_yaml(key_path)
        roots.update(kd.get("roots", []) or [])
        strong.update(kd.get("strong_ngrams", []) or [])
        stopwords.update(kd.get("stopwords", []) or [])
        for k, arr in (kd.get("variants") or {}).items():
            vs = variants.get(k, [])
            for v in arr or []:
                if v not in vs: vs.append(v)
            variants[k] = vs

    return {
        "roots": sorted(roots, key=len, reverse=True),
        "strong_ngrams": sorted(strong, key=len, reverse=True),
        "variants": variants,
        "stopwords": stopwords,
    }

# -------------------- 전처리/토큰화 --------------------
def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = re.sub(r"\[[^\]]*\]", " ", name)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = _MEAS1.sub(" ", s); s = _MEAS2.sub(" ", s); s = _ONLYNUM.sub(" ", s)
    s = re.sub(r"[^\w가-힣]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokenize_normalized(text: str, stopwords: Set[str]) -> List[str]:
    s = normalize_name(text)
    return [t for t in s.split() if len(t) >= 2 and not t.isnumeric() and t not in stopwords]

def _split_by_roots(token: str, roots: List[str]) -> List[str]:
    return [r for r in roots if r and r in token and token != r]

def _expand_variants(core: List[str], variants: Dict[str, List[str]]) -> List[str]:
    out: List[str] = []
    seen = set()
    for k in core:
        if k not in seen:
            out.append(k); seen.add(k)
        for v in variants.get(k, []):
            if v not in seen:
                out.append(v); seen.add(v)
    return out

# -------------------- 핵심/루트/테일 키워드 --------------------
def extract_core_keywords(prod_name: str, max_n: int = 3) -> List[str]:
    d = load_domain_dicts()
    roots, strong, variants, stop = d["roots"], d["strong_ngrams"], d["variants"], d["stopwords"]

    s = normalize_name(prod_name)
    found_ng = [ng for ng in strong if ng and ng in s]
    raw_toks = tokenize_normalized(s, stop)

    expanded: List[str] = []
    for t in raw_toks:
        expanded.extend(_split_by_roots(t, roots))
        expanded.append(t)

    ordered: List[str] = []
    for ng in found_ng:
        if ng not in ordered: ordered.append(ng)
        for r in _split_by_roots(ng, roots):
            if r not in ordered: ordered.append(r)
    for t in expanded:
        if t not in ordered: ordered.append(t)

    core = ordered[:max_n]
    return _expand_variants(core, variants)[:max_n]

def roots_in_name(prod_name: str) -> List[str]:
    d = load_domain_dicts()
    s = normalize_name(prod_name)
    hits = [r for r in d["roots"] if len(r) >= 2 and (r in s) and (r not in d["stopwords"])]
    # 중복 제거 순서 보존
    out = []
    seen = set()
    for h in hits:
        if h not in seen:
            out.append(h); seen.add(h)
    return out[:5]

def extract_tail_keywords(prod_name: str, max_n: int = 2) -> List[str]:
    """뒤쪽 핵심 키워드 중심으로(희소성/변형 고려는 가볍게) 추출."""
    d = load_domain_dicts()
    stop, variants, roots = d["stopwords"], d["variants"], d["roots"]
    s = normalize_name(prod_name)
    toks = [t for t in s.split() if len(t) >= 2 and not t.isnumeric() and t not in stop and not re.search(r"\d", t)]

    tail_base: List[str] = []
    for t in reversed(toks):
        if t not in tail_base:
            tail_base.append(t)
        if len(tail_base) >= max_n:
            break
    tail_base.reverse()

    expanded = list(tail_base)
    for t in tail_base:
        for v in variants.get(t, []):
            if v not in expanded:
                expanded.append(v)
    for t in tail_base:
        for r in _split_by_roots(t, roots):
            if r not in expanded:
                expanded.append(r)
    return expanded

# -------------------- 동적 n-gram --------------------
def _char_ngrams_windowed(token: str, nmin: int, nmax: int) -> List[str]:
    out = []
    L = len(token)
    for n in range(nmin, min(nmax, L) + 1):
        for i in range(0, L - n + 1):
            out.append(token[i:i+n])
    return out

def infer_terms_from_name_via_ngrams(prod_name: str, max_terms: int = DYN_MAX_TERMS) -> List[str]:
    d = load_domain_dicts()
    stop = d["stopwords"]

    toks = tokenize_normalized(prod_name, stop)
    toks = [t for t in toks if _HANGUL_ONLY.fullmatch(t)]

    cand = []
    for t in toks:
        cand.extend(_char_ngrams_windowed(t, DYN_NGRAM_MIN, DYN_NGRAM_MAX))
    cand.extend([t for t in toks if len(t) >= DYN_NGRAM_MIN])

    cand = [c for c in cand if _HANGUL_ONLY.fullmatch(c) and c not in stop]
    cand = list(dict.fromkeys(cand))[:max_terms]
    return cand

# -------------------- tail + n-gram OR 필터 (AND에서 변경) --------------------
def _char_ngrams_raw(s: str, n: int = 2) -> Set[str]:
    s2 = normalize_name(s).replace(" ", "")
    if len(s2) < n:
        return set()
    return {s2[i:i+n] for i in range(len(s2)-n+1)}

def _ngram_overlap_count(a: str, b: str, n: int = 2) -> int:
    a_ngrams = _char_ngrams_raw(a, n)
    b_ngrams = _char_ngrams_raw(b, n)
    overlap = a_ngrams & b_ngrams
    
    # 디버깅: 처음 몇 개만 로그로 출력
    from common.logger import get_logger
    logger = get_logger("homeshopping_kok")
    
    if len(a) < 100 and len(b) < 100:  # 짧은 문자열만 로그로 출력
        logger.debug(f"n-gram 계산: a='{a}' -> {list(a_ngrams)[:5]}, b='{b}' -> {list(b_ngrams)[:5]}, overlap={list(overlap)[:5]}")
    
    return len(overlap)

def _dynamic_tail_terms(query_name: str, candidate_names: List[str], stopwords: Set[str]) -> List[str]:
    """후보 집합에서 희소한 쿼리 토큰만 tail로 선정."""
    q_toks = set(tokenize_normalized(query_name, stopwords))
    if not q_toks or not candidate_names:
        return list(q_toks)[:1]  # 폴백

    df = Counter()
    for name in candidate_names:
        df.update(set(tokenize_normalized(name, stopwords)))

    total_docs = max(1, len(candidate_names))
    tail = [t for t in q_toks if (df.get(t, 0) / total_docs) <= TAIL_MAX_DF_RATIO]
    tail.sort(key=lambda t: df.get(t, 0))  # 희소한 순
    if not tail:
        tail = list(q_toks)[:1]
    return tail[:max(1, TAIL_MAX_TERMS)]

def filter_tail_and_ngram_or(details: List[dict], prod_name: str) -> List[dict]:
    """
    OR 조건으로 변경:
      - tail 토큰 일치 ≥ 1 OR n-gram 겹침 ≥ 1
    들어온 순서를 보존(이미 정렬되어 있다고 가정).
    """
    if not details:
        return []
    
    from common.logger import get_logger
    logger = get_logger("homeshopping_kok")
    
    d = load_domain_dicts()
    stop = d["stopwords"]

    # 실제 DB에서 반환되는 키 이름에 맞춰 수정
    cand_names = []
    for r in details:
        product_name = r.get('kok_product_name') or r.get('KOK_PRODUCT_NAME') or ''
        store_name = r.get('kok_store_name') or r.get('KOK_STORE_NAME') or ''
        cand_names.append(f"{product_name} {store_name}")
    
    tails = set(_dynamic_tail_terms(prod_name, cand_names, stop))
    
    logger.info(f"필터링 시작: prod_name='{prod_name}', tails={list(tails)[:10]}, 총 후보={len(details)}개")

    out = []
    filtered_count = 0
    for r in details:
        product_name = r.get('kok_product_name') or r.get('KOK_PRODUCT_NAME') or ''
        store_name = r.get('kok_store_name') or r.get('KOK_STORE_NAME') or ''
        name = f"{product_name} {store_name}"
        toks = set(tokenize_normalized(name, stop))
        tail_hits = len(tails & toks)
        ngram_hits = _ngram_overlap_count(prod_name, name, n=NGRAM_N)
        
        # 디버깅: 처음 3개 상품의 상세 정보 출력
        if filtered_count < 3:
            logger.info(f"상품 '{name}' 분석: tail_hits={tail_hits}, ngram_hits={ngram_hits}")
            logger.info(f"  - tails: {list(tails)[:5]}")
            logger.info(f"  - toks: {list(toks)[:5]}")
            logger.info(f"  - 교집합: {list(tails & toks)}")
        
        # 조건 완화: tail_hits >= 1 OR ngram_hits >= 1 (AND에서 OR로 변경)
        if tail_hits >= 1 or ngram_hits >= 1:
            out.append(r)
        else:
            filtered_count += 1
            if filtered_count <= 5:  # 처음 5개만 로그로 출력
                logger.debug(f"필터링됨: '{name}' (tail_hits={tail_hits}, ngram_hits={ngram_hits})")
    
    logger.info(f"필터링 완료: 통과={len(out)}개, 필터링됨={filtered_count}개")
    return out

# ----- 옵션: 게이트에서 스토어명도 LIKE 비교할지 (기본 False) -----
GATE_COMPARE_STORE = os.getenv("GATE_COMPARE_STORE", "false").lower() in ("1","true","yes","on")

# ---------- 후보 LIKE 게이트 ----------
def _sql_like_or(cols: List[str], num: int) -> str:
    return " OR ".join([f"{c} LIKE %s" for c in cols for _ in range(num)])

def _sql_like_and(cols: List[str], num: int) -> str:
    return " OR ".join(["(" + " AND ".join([f"{c} LIKE %s" for _ in range(num)]) + ")" for c in cols])

def kok_candidates_by_keywords_gated(
    must_kws: List[str],
    optional_kws: List[str],
    limit: int = 600,
    min_if_all_fail: int = 30,
) -> List[int]:
    """
    - must: OR(하나라도) → 부족하면 AND(최대 2개) → 다시 OR로 폴백
    - optional: 여전히 부족하면 OR로 보충
    - 기본은 상품명만 비교. GATE_COMPARE_STORE=true면 스토어명도 포함.
    """
    must_kws = [k for k in must_kws if k and len(k) >= 2]
    optional_kws = [k for k in optional_kws if k and len(k) >= 2]
    if not must_kws and not optional_kws:
        return []

    cols = ["i.KOK_PRODUCT_NAME"]
    if GATE_COMPARE_STORE:
        cols.append("i.KOK_STORE_NAME")

    def _run(sql: str, params: List[str]) -> List[int]:
        # 실제 DB 연결 구현 필요
        # 현재는 더미 데이터 반환
        return list(range(1001, 1001 + min(limit, 100)))

    ids: List[int] = []
    if must_kws:
        cond_or = _sql_like_or(cols, len(must_kws))
        sql_or = f"SELECT DISTINCT i.KOK_PRODUCT_ID FROM KOK_PRODUCT_INFO i WHERE ({cond_or}) LIMIT %s"
        params_or = [f"%{k}%" for k in must_kws for _ in cols]
        ids = _run(sql_or, params_or)

    if len(ids) < min_if_all_fail and must_kws:
        use = must_kws[:2]
        cond_and = _sql_like_and(cols, len(use))
        sql_and = f"SELECT DISTINCT i.KOK_PRODUCT_ID FROM KOK_PRODUCT_INFO i WHERE ({cond_and}) LIMIT %s"
        params_and = [f"%{k}%" for k in use for _ in cols]
        ids = _run(sql_and, params_and)
        if len(ids) < min_if_all_fail:
            ids = _run(sql_or, params_or)

    if len(ids) < min_if_all_fail and optional_kws:
        cond_opt = _sql_like_or(cols, len(optional_kws))
        sql_opt = f"SELECT DISTINCT i.KOK_PRODUCT_ID FROM KOK_PRODUCT_INFO i WHERE ({cond_opt}) LIMIT %s"
        params_opt = [f"%{k}%" for k in optional_kws for _ in cols]
        more = _run(sql_opt, params_opt)
        ids = list(dict.fromkeys(ids + more))[:limit]

    return ids

# ---------- 추천 본체 ----------
def recommend_homeshopping_to_kok(
    product_id: Union[int, str],
    k: int = 5,                       # 최대 5개
    use_rerank: bool = False,         # 여기선 기본 거리 정렬만 사용 (원하면 True로)
    candidate_n: int = 150,
    rerank_mode: str = None,
) -> List[Dict]:
    """
    파이프라인:
      1) 홈쇼핑 상품명에서 must/optional 키워드 구성
      2) LIKE 게이트로 후보 수집
      3) 후보 내 pgvector 정렬
      4) (옵션) 리랭크
      5) 최종 OR 필터(tail ≥1 OR n-gram ≥1)
      6) 최대 k개 슬라이스
    """
    # 실제 DB에서 상품명 조회 필요
    prod_name = f"홈쇼핑상품_{product_id}"  # 더미 데이터
    if not prod_name:
        return []

    # 1) 키워드 구성
    tail_k = extract_tail_keywords(prod_name, max_n=2)          # 뒤쪽 핵심(희소 가능성이 높은 토큰)
    core_k = extract_core_keywords(prod_name, max_n=3)          # 앞/강한 핵심
    root_k = roots_in_name(prod_name)                           # 루트 힌트(사전 기반)
    ngram_k = infer_terms_from_name_via_ngrams(prod_name, max_terms=DYN_MAX_TERMS)

    must_kws = list(dict.fromkeys([*tail_k, *core_k, *root_k]))[:12]
    optional_kws = list(dict.fromkeys([*ngram_k]))[:DYN_MAX_TERMS]

    # 2) LIKE 게이트로 후보
    cand_ids = kok_candidates_by_keywords_gated(
        must_kws=must_kws,
        optional_kws=optional_kws,
        limit=max(candidate_n * 3, 300),
        min_if_all_fail=max(30, k),
    )
    if not cand_ids:
        return []  # 게이트 통과 상품이 전혀 없으면 빈 리스트

    # 3) 후보 내 pgvector 정렬 (더미 데이터)
    sims: List[Tuple[Union[int, str], float]] = [(pid, 1.0 / (i + 1)) for i, pid in enumerate(cand_ids[:candidate_n])]
    if not sims:
        return []

    pid_order = [pid for pid, _ in sims]
    dist_map = {pid: dist for pid, dist in sims}

    # 4) 상세 조인 (더미 데이터)
    details = [{"KOK_PRODUCT_ID": pid, "KOK_PRODUCT_NAME": f"콕상품_{pid}", "KOK_STORE_NAME": f"스토어_{pid % 10}"} for pid in pid_order]
    if not details:
        return []
    for d in details:
        d["distance"] = dist_map.get(d["KOK_PRODUCT_ID"])

    # 5) 거리 정렬
    ranked = sorted(details, key=lambda x: x.get("distance", 1e9))

    # 6) 최종 OR 필터 적용 (tail ≥1 OR n-gram ≥1)
    filtered = filter_tail_and_ngram_or(ranked, prod_name)

    # 7) 최대 k개까지 반환
    return filtered[:k]

# -------------------- 내보내기 --------------------
__all__ = [
    # 파라미터
    "DYN_MAX_TERMS","DYN_MAX_EXTRAS","DYN_SAMPLE_ROWS",
    "DYN_NGRAM_MIN","DYN_NGRAM_MAX","NGRAM_N",
    "TAIL_MAX_DF_RATIO","TAIL_MAX_TERMS",
    "DYN_COUNT_MIN","DYN_COUNT_MAX",
    # 사전/전처리
    "load_domain_dicts","normalize_name","tokenize_normalized",
    # 키워드
    "extract_core_keywords","extract_tail_keywords","roots_in_name",
    "infer_terms_from_name_via_ngrams",
    # 최종 필터
    "filter_tail_and_ngram_or",
    # 추천 시스템
    "recommend_homeshopping_to_kok","kok_candidates_by_keywords_gated",
]
