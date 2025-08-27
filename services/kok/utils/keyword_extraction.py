# -*- coding: utf-8 -*-
"""
--------------------------------------
장바구니 상품명에서 **레시피 표준 재료명**(ing_vocab)에 해당하는 키워드를 추출하는 모듈

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
from typing import Dict, List, Optional, Set

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

def normalize_name(s: str, *, strip_digits: bool = True) -> str:
    """
    상품명을 추출 친화적으로 정규화
    - 괄호 → 공백
    - (옵션) 모든 숫자 제거 + 1+1, x, × 같은 프로모션/곱기호 제거
    - 잔여 특수문자 제거
    - 다중 공백 압축
    """
    s = (s or "").strip()
    s = s.replace("＋","+").replace("—","-").replace("·"," ")
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
