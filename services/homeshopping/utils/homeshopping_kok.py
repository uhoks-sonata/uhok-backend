# -*- coding: utf-8 -*-
"""
utils.py
- 문자열 정규화 / 사전 로딩
- 핵심 키워드 / 루트 / Tail 키워드
- 동적 n-gram
- tail + n-gram AND 필터
"""

import os, re, yaml
from typing import Dict, List, Set
from collections import Counter
from dotenv import load_dotenv
load_dotenv()

# -------------------- 동적 파라미터 --------------------
def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except Exception:
        return default

# LIKE 검색/키워드 확장 파라미터(외부에서도 import해 사용)
DYN_MAX_TERMS   = _env_int("DYN_MAX_TERMS", 32)
DYN_MAX_EXTRAS  = _env_int("DYN_MAX_EXTRAS", 20)
DYN_SAMPLE_ROWS = _env_int("DYN_SAMPLE_ROWS", 4000)

# Tail / n-gram 필터 동작 파라미터
TAIL_MAX_DF_RATIO = float(os.getenv("TAIL_MAX_DF_RATIO", "0.35"))  # 희소 토큰 판정 기준(문서비율 ≤ 0.35)
TAIL_MAX_TERMS    = _env_int("TAIL_MAX_TERMS", 3)                   # tail 후보로 쓸 최대 토큰 수
NGRAM_N           = _env_int("NGRAM_N", 2)                          # bi-gram 기본

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
팩 봉 포 개 입 병 캔 스틱 정 포기 세트구성 골라담기 택1 택일 실속 못난이 파우치 슬라이스 인분
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

# -------------------- tail + n-gram AND 필터 --------------------
def _char_ngrams_raw(s: str, n: int = 2) -> Set[str]:
    s2 = normalize_name(s).replace(" ", "")
    if len(s2) < n:
        return set()
    return {s2[i:i+n] for i in range(len(s2)-n+1)}

def _ngram_overlap_count(a: str, b: str, n: int = 2) -> int:
    return len(_char_ngrams_raw(a, n) & _char_ngrams_raw(b, n))

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

def filter_tail_and_ngram_and(details: List[dict], prod_name: str) -> List[dict]:
    """
    AND 조건:
      - tail 토큰 일치 ≥ 1
      - n-gram 겹침 ≥ 1 (기본 bi-gram)
    들어온 순서를 보존(이미 정렬되어 있다고 가정).
    """
    if not details:
        return []
    d = load_domain_dicts()
    stop = d["stopwords"]

    cand_names = [f"{r.get('KOK_PRODUCT_NAME','')} {r.get('KOK_STORE_NAME','')}" for r in details]
    tails = set(_dynamic_tail_terms(prod_name, cand_names, stop))

    out = []
    for r in details:
        name = f"{r.get('KOK_PRODUCT_NAME','')} {r.get('KOK_STORE_NAME','')}"
        toks = set(tokenize_normalized(name, stop))
        tail_hits = len(tails & toks)
        ngram_hits = _ngram_overlap_count(prod_name, name, n=NGRAM_N)
        if tail_hits >= 1 and ngram_hits >= 1:
            out.append(r)
    return out

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
    "filter_tail_and_ngram_and",
    # 내부 유틸
    "_dynamic_tail_terms","_ngram_overlap_count","_char_ngrams_raw",
]

# ================== 추천 오케스트레이터 관련 환경변수 ==================
# ---- 환경 기본값 ----
RERANK_MODE_DEFAULT = os.getenv("RERANK_MODE", "off").lower().strip()  # 여기선 기본 off (원하면 "boost"/"strict")

# 이 utils 파일에서는 키워드 추출, 필터링 등의 유틸리티 함수들만 제공
# 실제 DB 연동 및 추천 로직은 CRUD에서 처리