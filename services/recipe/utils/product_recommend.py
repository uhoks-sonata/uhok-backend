# -*- coding: utf-8 -*-
# utils.py — 공통 유틸 + DB 연결 + 필터/정규화

import os
import re
import pandas as pd
from dotenv import load_dotenv

# ---- DB 드라이버: mariadb 우선, 실패시 pymysql 폴백 ----
try:
    import mariadb as dbapi
    DBAPI_NAME = "mariadb"
except ImportError:
    import pymysql as dbapi
    DBAPI_NAME = "pymysql"

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

# ---------- DB 유틸 ----------
def _parse_db_url(db_url: str):
    m = re.match(
        r"^[a-zA-Z0-9_+]+://(?P<user>[^:]+):(?P<pw>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<db>[\w\d_]+)$",
        db_url or ""
    )
    return m.groupdict() if m else None

def connect_mariadb():
    cfg = _parse_db_url(os.getenv("MARIADB_SERVICE_URL", ""))
    if cfg:
        host = cfg["host"]; port = int(cfg["port"]); user = cfg["user"]
        password = cfg["pw"]; database = cfg["db"]
    else:
        host = os.getenv("MARIADB_HOST")
        port = int(os.getenv("MARIADB_PORT", "3306"))
        user = os.getenv("MARIADB_USER")
        password = os.getenv("MARIADB_PASSWORD")
        database = os.getenv("MARIADB_DB")

    if DBAPI_NAME == "mariadb":
        return dbapi.connect(host=host, port=port, user=user, password=password, database=database)
    else:
        # pymysql 폴백
        return dbapi.connect(host=host, port=port, user=user, password=password, database=database, charset="utf8mb4")

def dict_cursor(conn):
    if DBAPI_NAME == "mariadb":
        return conn.cursor(dictionary=True)
    else:
        from pymysql.cursors import DictCursor
        return conn.cursor(DictCursor)

def adapt_sql(sql: str) -> str:
    """PyMySQL은 %s 플레이스홀더 사용"""
    return sql if DBAPI_NAME == "mariadb" else sql.replace("?", "%s")

def _read_df(conn, sql, params):
    sql = adapt_sql(sql)
    cur = dict_cursor(conn)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return pd.DataFrame(rows) if rows else pd.DataFrame()

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
    hc.PRODUCT_ID,
    hc.PRODUCT_NAME,
    hc.CLS_FOOD,
    hc.CLS_ING,
    hpi.SALE_PRICE,
    hpi.STORE_NAME,
    hiu.IMG_URL
FROM HOMESHOPPING_CLASSIFY hc
LEFT JOIN FCT_HOMESHOPPING_PRODUCT_INFO hpi ON hc.PRODUCT_ID = hpi.PRODUCT_ID
LEFT JOIN FCT_HOMESHOPPING_IMG_URL hiu ON hc.PRODUCT_ID = hiu.PRODUCT_ID AND hiu.SORT_ORDER = 1
WHERE hc.CLS_FOOD = 1
  AND hc.CLS_ING  = 1
  AND (
        hc.PRODUCT_NAME REGEXP ?
        OR REPLACE(hc.PRODUCT_NAME, ' ', '') REGEXP ?
      )
ORDER BY
  CASE WHEN LOCATE(?, hc.PRODUCT_NAME) > 0 THEN LOCATE(?, hc.PRODUCT_NAME) ELSE 99999 END,
  CHAR_LENGTH(hc.PRODUCT_NAME) ASC
LIMIT ?
"""

KOK_SQL_TMPL = """
SELECT 
    kc.PRODUCT_ID,
    kc.PRODUCT_NAME,
    kc.CLS_ING,
    kpi.KOK_PRODUCT_PRICE,
    kpi.KOK_STORE_NAME,
    kpi.KOK_THUMBNAIL
FROM KOK_CLASSIFY kc
LEFT JOIN FCT_KOK_PRODUCT_INFO kpi ON kc.PRODUCT_ID = kpi.KOK_PRODUCT_ID
WHERE kc.CLS_ING = 1
  AND (
        kc.PRODUCT_NAME REGEXP ?
        OR REPLACE(kc.PRODUCT_NAME, ' ', '') REGEXP ?
      )
ORDER BY
  CASE WHEN LOCATE(?, kc.PRODUCT_NAME) > 0 THEN LOCATE(?, kc.PRODUCT_NAME) ELSE 99999 END,
  CHAR_LENGTH(kc.PRODUCT_NAME) ASC
LIMIT ?
"""

# ---------- 검색 함수 ----------
def search_homeshopping(conn, ingredient: str, limit_n: int = 2) -> pd.DataFrame:
    (pat, pat_ns), kw = build_regex_params(ingredient)
    sql = HS_SQL_TMPL
    df = _read_df(conn, sql, [pat, pat_ns, kw, kw, limit_n*3])  # 중복/필터 대비 여유

    if not df.empty:
        # (선택) 맥락 필터 — 현재 스텁 False
        df = df[~df['PRODUCT_NAME'].astype(str).apply(lambda n: is_false_positive(n, ingredient))]
        # 임시 금지어 필터
        df = apply_exclude(df, 'PRODUCT_NAME', ingredient)
        df = df.head(limit_n)
    return df

def search_kok(conn, ingredient: str, limit_n: int) -> pd.DataFrame:
    (pat, pat_ns), kw = build_regex_params(ingredient)
    sql = KOK_SQL_TMPL
    df = _read_df(conn, sql, [pat, pat_ns, kw, kw, limit_n*3])

    if not df.empty:
        df = df[~df['PRODUCT_NAME'].astype(str).apply(lambda n: is_false_positive(n, ingredient))]
        df = apply_exclude(df, 'PRODUCT_NAME', ingredient)
        df = df.head(limit_n)
    return df

# ---------- 추천 메인 ----------
def recommend_for_ingredient(conn, ingredient: str, max_total: int = 5, max_home: int = 2):
    """
    반환: list of dict(source, table, name, id, image_url, brand_name, price)
    """
    recs = []
    seen = set()

    # 1) 홈쇼핑 먼저 (최대 2)
    hs = search_homeshopping(conn, ingredient, limit_n=max_home)
    if not hs.empty:
        for _, r in hs.iterrows():
            name = str(r.get('PRODUCT_NAME', "")); key = norm_for_dedupe(name)
            if key in seen:
                continue
            seen.add(key)
            recs.append({
                "source": "homeshopping",
                "table":  "HOMESHOPPING_CLASSIFY",
                "name":   name,
                "id":     r.get('PRODUCT_ID'),
                "image_url": r.get('IMG_URL'),
                "brand_name": r.get('STORE_NAME'),
                "price": r.get('SALE_PRICE'),
            })
            if len(recs) >= max_home:
                break

    # 2) KOK로 채우기 (총 max_total까지)
    need = max_total - len(recs)
    if need > 0:
        kok = search_kok(conn, ingredient, limit_n=need * 3)  # 여유로 뽑아 중복 제거
        if not kok.empty:
            for _, r in kok.iterrows():
                if len(recs) >= max_total:
                    break
                name = str(r.get('PRODUCT_NAME', "")); key = norm_for_dedupe(name)
                if key in seen:
                    continue
                seen.add(key)
                recs.append({
                    "source": "kok",
                    "table":  "KOK_CLASSIFY",
                    "name":   name,
                    "id":     r.get('PRODUCT_ID'),
                    "image_url": r.get('KOK_THUMBNAIL'),
                    "brand_name": r.get('KOK_STORE_NAME'),
                    "price": r.get('KOK_PRODUCT_PRICE'),
                })

    return recs
