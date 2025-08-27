# -*- coding: utf-8 -*-
"""
KOK 상품 기반 홈쇼핑 추천 유틸리티
- 마지막 의미 토큰, 핵심 키워드, Tail 키워드 등 다양한 알고리즘 사용
"""

import re
from typing import Dict, List, Set, Any

# -------------------- 기본 설정값 --------------------
DEFAULT_STOPWORDS: Set[str] = set("""
세트 선물세트 모음 모음전 구성 증정 행사 정품 정기 무료 특가 사은품 선물 혼합 혼합세트 묶음 총 택 옵션 국내산 수입산 무료배송 당일 당일발송 예약 신상 히트 인기 추천 기획 기획세트 명품 프리미엄 리미티드 한정 본품 리뉴얼 정가 정상가 행사상품 대용량 소용량 박스 리필 업소용 가정용 편의점 오리지널 리얼 신제품 공식 단독 정기구독 구독 사은 혜택 특전 한정판 고당도 산지 당일 당일직송 직송 손질 세척 냉동 냉장 생물 해동 숙성 팩 봉 포 개 입 병 캔 스틱 정 포기 세트구성 골라담기 택1 택일 실속 못난이 파우치 슬라이스 인분 종
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
    "명태": ["북어"],
    "어묵": ["오뎅"],
    "백명란": ["명란","명란젓"],
}

# 정규표현식 패턴
_MEAS1 = re.compile(r"\d+(?:\.\d+)?\s*(?:g|kg|ml|l|L)?\s*(?:[xX×＊*]\s*\d+)?", re.I)
_MEAS2 = re.compile(r"\b\d+[a-zA-Z]+\b")
_ONLYNUM = re.compile(r"\b\d+\b")
_HANGUL_ONLY = re.compile(r"^[가-힣]{2,}$")

# -------------------- 전처리/토큰화 --------------------
def normalize_name(name: str) -> str:
    """상품명 정규화"""
    if not isinstance(name, str):
        return ""
    s = re.sub(r"\[[^\]]*\]", " ", name)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = _MEAS1.sub(" ", s)
    s = _MEAS2.sub(" ", s)
    s = _ONLYNUM.sub(" ", s)
    s = re.sub(r"[^\w가-힣]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokenize_normalized(text: str, stopwords: Set[str]) -> List[str]:
    """정규화된 텍스트를 토큰화"""
    s = normalize_name(text)
    return [t for t in s.split() if len(t) >= 2 and not t.isnumeric() and t not in stopwords]

def _split_by_roots(token: str, roots: List[str]) -> List[str]:
    """토큰을 루트 힌트로 분할"""
    return [r for r in roots if r and r in token and token != r]

def _expand_variants(core: List[str], variants: Dict[str, List[str]]) -> List[str]:
    """핵심 키워드의 변형어 확장"""
    out: List[str] = []
    seen = set()
    for k in core:
        if k not in seen:
            out.append(k)
            seen.add(k)
        for v in variants.get(k, []):
            if v not in seen:
                out.append(v)
                seen.add(v)
    return out

# -------------------- 핵심/루트/테일 키워드 --------------------
def extract_core_keywords(prod_name: str, max_n: int = 3) -> List[str]:
    """핵심 키워드 추출"""
    roots, strong, variants, stop = DEFAULT_ROOT_HINTS, DEFAULT_STRONG_NGRAMS, DEFAULT_VARIANTS, DEFAULT_STOPWORDS
    s = normalize_name(prod_name)
    
    # 강한 n-gram 찾기
    found_ng = [ng for ng in strong if ng and ng in s]
    
    # 토큰화 및 루트 분할
    raw_toks = tokenize_normalized(s, stop)
    expanded: List[str] = []
    for t in raw_toks:
        expanded.extend(_split_by_roots(t, roots))
        expanded.append(t)
    
    # 순서대로 정렬
    ordered: List[str] = []
    for ng in found_ng:
        if ng not in ordered:
            ordered.append(ng)
        for r in _split_by_roots(ng, roots):
            if r not in ordered:
                ordered.append(r)
    
    for t in expanded:
        if t not in ordered:
            ordered.append(t)
    
    core = ordered[:max_n]
    return _expand_variants(core, variants)[:max_n]

def extract_tail_keywords(prod_name: str, max_n: int = 2) -> List[str]:
    """뒤쪽 핵심 키워드 중심으로 추출"""
    stop, variants, roots = DEFAULT_STOPWORDS, DEFAULT_VARIANTS, DEFAULT_ROOT_HINTS
    s = normalize_name(prod_name)
    
    toks = [t for t in s.split() if len(t) >= 2 and not t.isnumeric() and t not in stop and not re.search(r"\d", t)]
    
    # 뒤에서부터 토큰 선택
    tail_base: List[str] = []
    for t in reversed(toks):
        if t not in tail_base:
            tail_base.append(t)
        if len(tail_base) >= max_n:
            break
    
    tail_base.reverse()
    expanded = list(tail_base)
    
    # 변형어 및 루트 확장
    for t in tail_base:
        for v in variants.get(t, []):
            if v not in expanded:
                expanded.append(v)
        for r in _split_by_roots(t, roots):
            if r not in expanded:
                expanded.append(r)
    
    return expanded

def last_meaningful_token(text: str) -> str:
    """정규화 + stopwords 기반 토크나이즈 후, 포장/수량성 토큰은 건너뛰고 마지막 의미 토큰을 반환"""
    stop = DEFAULT_STOPWORDS
    toks = tokenize_normalized(text, stop)
    
    # 마지막 위치에서부터 의미 토큰만 선택
    SKIP_LAST = {
        "종", "세트", "세트구성", "박스", "구성", "혼합", "모음", "모음전", "구독", "택", "택일", "포기", "인분", "팩", "봉", "포", "입", "병", "캔", "스틱", "정", "대용량", "소용량"
    }
    
    for t in reversed(toks):
        if t not in SKIP_LAST:
            return t
    
    return ""  # 전부 스킵되면 빈 문자열 반환

# -------------------- 추천 전략 --------------------
def recommend_by_last_word(kok_product_name: str, k: int = 5) -> List[str]:
    """마지막 의미 토큰 기반 추천"""
    last = last_meaningful_token(kok_product_name)
    if not last:
        return []
    
    # 마지막 토큰이 포함된 검색어 반환
    return [last]

def recommend_by_core_keywords(kok_product_name: str, k: int = 5) -> List[str]:
    """핵심 키워드 기반 추천"""
    core_keywords = extract_core_keywords(kok_product_name, max_n=k)
    return core_keywords

def recommend_by_tail_keywords(kok_product_name: str, k: int = 5) -> List[str]:
    """Tail 키워드 기반 추천"""
    tail_keywords = extract_tail_keywords(kok_product_name, max_n=k)
    return tail_keywords

def get_recommendation_strategy(kok_product_name: str, k: int = 5) -> Dict[str, Any]:
    """추천 전략 선택 및 실행"""
    if not kok_product_name:
        return {
            "algorithm": "none",
            "status": "failed",
            "search_terms": [],
            "message": "상품명이 없습니다."
        }
    
    # 1. 마지막 의미 토큰 전략
    last_word_results = recommend_by_last_word(kok_product_name, k)
    if last_word_results:
        return {
            "algorithm": "last_meaningful_token",
            "status": "success",
            "search_terms": last_word_results,
            "message": "마지막 의미 토큰 기반 추천"
        }
    
    # 2. 핵심 키워드 전략
    core_results = recommend_by_core_keywords(kok_product_name, k)
    if core_results:
        return {
            "algorithm": "core_keywords",
            "status": "success",
            "search_terms": core_results,
            "message": "핵심 키워드 기반 추천"
        }
    
    # 3. Tail 키워드 전략
    tail_results = recommend_by_tail_keywords(kok_product_name, k)
    if tail_results:
        return {
            "algorithm": "tail_keywords",
            "status": "success",
            "search_terms": tail_results,
            "message": "Tail 키워드 기반 추천"
        }
    
    # 4. 폴백: 상품명의 일부 사용
    normalized = normalize_name(kok_product_name)
    tokens = tokenize_normalized(normalized, DEFAULT_STOPWORDS)
    if tokens:
        return {
            "algorithm": "fallback_tokens",
            "status": "success",
            "search_terms": tokens[:k],
            "message": "폴백 토큰 기반 추천"
        }
    
    return {
        "algorithm": "none",
        "status": "failed",
        "search_terms": [],
        "message": "적절한 추천 전략을 찾을 수 없습니다."
    }

__all__ = [
    "get_recommendation_strategy",
    "recommend_by_last_word",
    "recommend_by_core_keywords",
    "recommend_by_tail_keywords",
    "extract_core_keywords",
    "extract_tail_keywords",
    "last_meaningful_token",
    "normalize_name",
    "tokenize_normalized"
]
