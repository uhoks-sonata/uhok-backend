# -*- coding: utf-8 -*-
"""
KOK 서비스 유틸리티 모듈
"""

from .kok_homeshopping import (
    get_recommendation_strategy,
    recommend_by_last_word,
    recommend_by_core_keywords,
    recommend_by_tail_keywords,
    extract_core_keywords,
    extract_tail_keywords,
    last_meaningful_token,
    normalize_name,
    tokenize_normalized
)

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
