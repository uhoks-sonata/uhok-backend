# -*- coding: utf-8 -*-
# utils.py — 공통 유틸 + DB 연결 + 필터/정규화

import os
import re
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from common.database.mariadb_service import get_maria_service_db

# 환경변수 로드
load_dotenv()

# 후보 컬럼 (더 이상 사용하지 않음 - JOIN으로 대체)
# NAME_CANDIDATES = ["PRODUCT_NAME", "NAME", "TITLE"]
# ID_CANDIDATES   = ["PRODUCT_ID", "LIVE_ID", "ITEM_ID", "GOOD_ID", "ID"]
# IMAGE_CANDIDATES = ["IMAGE_URL", "IMG_URL", "THUMBNAIL", "PRODUCT_IMAGE"]
# BRAND_CANDIDATES = ["BRAND_NAME", "BRAND", "MAKER", "COMPANY"]
# PRICE_CANDIDATES = ["PRICE", "COST", "AMOUNT", "SALE_PRICE"]

# 임시방편: 키워드별 "포함되면 제외" 금지어 목록
EXCLUDE_CONTAINS = {
    "안심": ["쌀"],       # '안심' 검색 시 '쌀' 포함 상품 제외
    "양파": ["아몬드"],   # '양파' 검색 시 '아몬드' 포함 상품 제외
    "쌀":   ["수프"],     # 예: 쌀 검색 시 '수프' 포함은 제외(원하면 유지/삭제)
}

# ---------- 텍스트 유틸 ----------
def normalize_text(s: str) -> str:
    if s is None: return ""
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    return s

def norm_for_dedupe(s: str) -> str:
    """중복 제거용 키: 소문자 + 공백/특수문자 제거"""
    s = normalize_text(s).lower()
    s = re.sub(r"[\s\[\]\(\)\-_/·•,.;:!?\+#'\"※~`]", "", s)
    return s

def pick_first_col(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    return None

def build_regex_params(keyword: str):
    """
    오른쪽 경계 강제:
      - 패턴: '키워드($|[^0-9A-Za-z가-힣])'
      - 공백 제거 버전도 함께 생성
    """
    kw = normalize_text(keyword)
    kw_ns = kw.replace(" ", "")
    safe_kw = re.escape(kw)
    safe_kw_ns = re.escape(kw_ns)
    pat    = rf"{safe_kw}($|[^0-9A-Za-z가-힣])"
    pat_ns = rf"{safe_kw_ns}($|[^0-9A-Za-z가-힣])"
    return (pat, pat_ns), kw

def is_false_positive(name: str, keyword: str) -> bool:
    """임시 스텁: 향후 맥락 필터 확장 전까지 항상 False"""
    return False

def apply_exclude(df: pd.DataFrame, name_col: str, ingredient: str) -> pd.DataFrame:
    """임시방편: ingredient에 매핑된 금지어가 상품명에 포함되면 제외"""
    if df is None or df.empty:
        return df
    key = normalize_text(ingredient)
    bans = EXCLUDE_CONTAINS.get(key, [])
    if not bans:
        return df
    name_s = df[name_col].astype(str)
    mask = pd.Series(True, index=df.index)
    for ban in bans:
        mask &= ~name_s.str.contains(re.escape(ban), case=False, na=False)
    return df[mask]

def safe_price(price_value):
    """가격 값을 안전하게 변환: nan, None, 빈 값은 None으로 변환"""
    if price_value is None:
        return None
    if pd.isna(price_value) or np.isnan(price_value):
        return None
    try:
        # 숫자로 변환 시도
        price_float = float(price_value)
        if np.isnan(price_float):
            return None
        return int(price_float) if price_float.is_integer() else price_float
    except (ValueError, TypeError):
        return None

# ---------- DB 유틸 ----------
async def _read_df_async(session: AsyncSession, sql: str, params: list) -> pd.DataFrame:
    """SQLAlchemy 세션을 사용하여 데이터프레임 반환"""
    result = await session.execute(text(sql), params)
    rows = result.fetchall()
    if rows:
        # 컬럼명 추출
        columns = result.keys()
        # 딕셔너리 리스트로 변환
        dict_rows = [dict(zip(columns, row)) for row in rows]
        return pd.DataFrame(dict_rows)
    return pd.DataFrame()

# def detect_name_col(conn, table: str) -> str:
#     cur = conn.cursor()
#     cur.execute(f"SELECT * FROM {table} LIMIT 1")
#     cols = [d[0] for d in cur.description]
#     cur.close()
#     return pick_first_col(cols, NAME_CANDIDATES) or cols[0]

# -*- coding: utf-8 -*-
# recommend.py — 검색 쿼리 + 추천 로직

# ---------- SQL 템플릿 (REGEXP + 오른쪽 경계) ----------
HS_SQL_TMPL = """
SELECT 
    hc.PRODUCT_ID as product_id,
    hc.PRODUCT_NAME as product_name,
    hc.CLS_FOOD as cls_food,
    hc.CLS_ING as cls_ing,
    hpi.SALE_PRICE as sale_price,
    hpi.STORE_NAME as store_name,
    hfl.THUMB_IMG_URL as thumb_img_url,
    COALESCE(hfl.LIVE_ID, hc.PRODUCT_ID) as live_id
FROM HOMESHOPPING_CLASSIFY hc
LEFT JOIN FCT_HOMESHOPPING_PRODUCT_INFO hpi ON hc.PRODUCT_ID = hpi.PRODUCT_ID
LEFT JOIN FCT_HOMESHOPPING_LIST hfl ON hc.PRODUCT_ID = hfl.PRODUCT_ID
WHERE hc.CLS_FOOD = 1
  AND hc.CLS_ING  = 1
  AND (
        hc.PRODUCT_NAME REGEXP :pat
        OR REPLACE(hc.PRODUCT_NAME, ' ', '') REGEXP :pat_ns
      )
ORDER BY
  CASE WHEN LOCATE(:kw, hc.PRODUCT_NAME) > 0 THEN LOCATE(:kw, hc.PRODUCT_NAME) ELSE 99999 END,
  CHAR_LENGTH(hc.PRODUCT_NAME) ASC
LIMIT :limit_n
"""

KOK_SQL_TMPL = """
SELECT 
    kc.PRODUCT_ID as product_id,
    kc.PRODUCT_NAME as product_name,
    kc.CLS_ING as cls_ing,
    kpi.KOK_PRODUCT_PRICE as kok_product_price,
    kpi.KOK_STORE_NAME as kok_store_name,
    kpi.KOK_THUMBNAIL as kok_thumbnail
FROM KOK_CLASSIFY kc
LEFT JOIN FCT_KOK_PRODUCT_INFO kpi ON kc.PRODUCT_ID = kpi.KOK_PRODUCT_ID
WHERE kc.CLS_ING = 1
  AND (
        kc.PRODUCT_NAME REGEXP :pat
        OR REPLACE(kc.PRODUCT_NAME, ' ', '') REGEXP :pat_ns
      )
ORDER BY
  CASE WHEN LOCATE(:kw, kc.PRODUCT_NAME) > 0 THEN LOCATE(:kw, kc.PRODUCT_NAME) ELSE 99999 END,
  CHAR_LENGTH(kc.PRODUCT_NAME) ASC
LIMIT :limit_n
"""

# ---------- 검색 함수 ----------
async def search_homeshopping(session: AsyncSession, ingredient: str, limit_n: int = 2) -> pd.DataFrame:
    (pat, pat_ns), kw = build_regex_params(ingredient)
    sql = HS_SQL_TMPL
    params = {"pat": pat, "pat_ns": pat_ns, "kw": kw, "limit_n": limit_n * 3}  # 중복/필터 대비 여유
    
    df = await _read_df_async(session, sql, params)

    if not df.empty:
        # (선택) 맥락 필터 — 현재 스텁 False
        df = df[~df['product_name'].astype(str).apply(lambda n: is_false_positive(n, ingredient))]
        # 임시 금지어 필터
        df = apply_exclude(df, 'product_name', ingredient)
        df = df.head(limit_n)
    return df

async def search_kok(session: AsyncSession, ingredient: str, limit_n: int) -> pd.DataFrame:
    (pat, pat_ns), kw = build_regex_params(ingredient)
    sql = KOK_SQL_TMPL
    params = {"pat": pat, "pat_ns": pat_ns, "kw": kw, "limit_n": limit_n * 3}
    
    df = await _read_df_async(session, sql, params)

    if not df.empty:
        df = df[~df['product_name'].astype(str).apply(lambda n: is_false_positive(n, ingredient))]
        df = apply_exclude(df, 'product_name', ingredient)
        df = df.head(limit_n)
    return df

# ---------- 추천 메인 ----------
async def recommend_for_ingredient(session: AsyncSession, ingredient: str, max_total: int = 5, max_home: int = 2):
    """
    반환: list of dict(source, table, name, id, image_url/thumb_img_url, brand_name, price)
    """
    recs = []
    seen = set()

    # 1) 홈쇼핑 먼저 (최대 2)
    hs = await search_homeshopping(session, ingredient, limit_n=max_home)
    if not hs.empty:
        for _, r in hs.iterrows():
            name = str(r.get('product_name', "")); key = norm_for_dedupe(name)
            if key in seen:
                continue
            seen.add(key)
            recs.append({
                "source": "homeshopping",
                "table":  "HOMESHOPPING_CLASSIFY",
                "name":   name,
                "id":     r.get('live_id'),
                "thumb_img_url": r.get('thumb_img_url'),
                "brand_name": r.get('store_name'),
                "price": safe_price(r.get('sale_price')),
                "homeshopping_id": r.get('live_id'),
            })
            if len(recs) >= max_home:
                break

    # 2) KOK로 채우기 (총 max_total까지)
    need = max_total - len(recs)
    if need > 0:
        kok = await search_kok(session, ingredient, limit_n=need * 3)  # 여유로 뽑아 중복 제거
        if not kok.empty:
            for _, r in kok.iterrows():
                if len(recs) >= max_total:
                    break
                name = str(r.get('product_name', "")); key = norm_for_dedupe(name)
                if key in seen:
                    continue
                seen.add(key)
                recs.append({
                    "source": "kok",
                    "table":  "KOK_CLASSIFY",
                    "name":   name,
                    "id":     r.get('product_id'),
                    "image_url": r.get('kok_thumbnail'),
                    "brand_name": r.get('kok_store_name'),
                    "price": safe_price(r.get('kok_product_price')),
                    "homeshopping_id": None,
                })

    return recs
