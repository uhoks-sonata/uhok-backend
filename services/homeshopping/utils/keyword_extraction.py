# -*- coding: utf-8 -*-
"""
홈쇼핑 전용 키워드 추출 모듈
- 홈쇼핑 상품명에서 레시피 표준 재료명 키워드 추출
- KOK의 키워드 추출 로직을 기반으로 홈쇼핑 특화 기능 추가
"""

from services.kok.utils.keyword_extraction import (
    extract_ingredient_keywords,
    normalize_name,
    split_tokens,
    make_ngrams,
    is_noise_token,
    is_derivative_form,
    fuzzy_pick,
    _filter_longest_only
)
from common.utils import load_ing_vocab
from common.config import get_settings
from urllib.parse import urlparse
from typing import Dict, Set, Any


def get_homeshopping_db_config() -> Dict[str, Any]:
    """
    홈쇼핑용 MariaDB 설정을 반환
    """
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
    """
    홈쇼핑용 표준 재료 어휘를 로드
    """
    db_conf = get_homeshopping_db_config()
    return load_ing_vocab(db_conf)


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
    
    # KOK의 키워드 추출 함수 호출
    return extract_ingredient_keywords(
        product_name=product_name,
        ing_vocab=ing_vocab,
        **default_params
    )


def extract_homeshopping_keywords_simple(
    product_name: str,
    **kwargs
) -> Dict[str, Any]:
    """
    홈쇼핑 상품명에서 식재료 키워드 추출 (간단 버전)
    - 어휘 사전 자동 로드
    - 기본 파라미터 사용
    
    Args:
        product_name: 홈쇼핑 상품명
        **kwargs: 추가 파라미터
    
    Returns:
        키워드와 디버그 정보가 포함된 딕셔너리
    """
    return extract_homeshopping_keywords(product_name, **kwargs)


# 홈쇼핑 특화 유틸리티 함수들
def is_homeshopping_product(product_name: str) -> bool:
    """
    홈쇼핑 상품명인지 확인하는 간단한 검증
    """
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


def get_homeshopping_keyword_stats(product_names: list[str]) -> Dict[str, Any]:
    """
    홈쇼핑 상품명 리스트에서 키워드 추출 통계 반환
    
    Args:
        product_names: 홈쇼핑 상품명 리스트
    
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
    
    # 어휘 사전 로드
    ing_vocab = load_homeshopping_ing_vocab()
    
    # 키워드 추출 실행
    results = []
    all_keywords = []
    
    for product_name in product_names:
        try:
            result = extract_homeshopping_keywords(product_name, ing_vocab)
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
        "most_common_keywords": [{"keyword": kw, "count": count} for kw, count in most_common]
    }
