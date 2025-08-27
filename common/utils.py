# -*- coding: utf-8 -*-
"""utils.py
- DB 접속/조회에 필요한 공통 유틸 모음
- streamlit 쪽에서는 이 함수들을 그대로 가져다 쓰고,
- 캐싱(st.cache_data)은 app.py에서 래핑해서 적용"""

from __future__ import annotations
from typing import Any
from urllib.parse import urlparse, unquote

import pandas as pd
import pymysql

# ---- DSN 파서 ----
def parse_mariadb_url(dsn: str | None) -> dict[str, Any] | None:
    if not dsn:
        return None
    u = urlparse(dsn)
    host = u.hostname or "localhost"
    port = int(u.port or 3306)
    user = unquote(u.username or "")
    password = unquote(u.password or "")
    database = (u.path or "").lstrip("/") or ""
    return {"host": host, "port": port, "user": user, "password": password, "database": database}

# ---- DB 연결/헬퍼 ----

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

def list_columns(conn, table: str) -> list[str]:
    """
    해당 테이블의 컬럼명을 순서대로 반환
    INFORMATION_SCHEMA를 조회하므로, 현재 접속 DB(default schema) 기준으로 동작
    """    
    cols: list[str] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (table,),
        )
        for (name,) in cur.fetchall():
            cols.append(str(name))
    return cols

# 다양한 테이블에서 '상품 식별자'로 쓰일 가능성이 있는 컬럼 후보들 
ID_PATTERNS = ["PRODUCT_ID"]

def pick_id_column(columns: list[str], override: str | None = None) -> str | None:
    """
    식별자 컬럼명을 추정해서 반환.
    - override가 주어지면 우선 사용
    - 아니면 ID & PATTERN를 대문자로 비교하여 첫 일치 항목을 선택
    - 없으면 None을 반환( 이 경우 SELECT에서 NULL AS PRODUCT_ID로 대체)"""
    if override and override in columns:
        return override
    upper = {c.upper(): c for c in columns}
    for pat in ID_PATTERNS:
        if pat in upper:
            return upper[pat]
    return None

# ---- 데이터 로딩 API (캐시는 app.py에서 래핑) ----
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

def fetch_products(db_conf: dict, source: str, limit: int, id_override: str | None = None) -> pd.DataFrame:
    conn = connect_mysql(**db_conf)
    try:
        if source in ("KOK", "KOK_CLASSIFY"):
            table = "KOK_CLASSIFY"
            where = "CLS_ING = 1 AND PRODUCT_NAME IS NOT NULL AND PRODUCT_NAME <> ''"
        elif source in ("HOME", "HOMESHOPPING", "HOMESHOPPING_CLASSIFY"):
            table = "HOMESHOPPING_CLASSIFY"
            where = "CLS_FOOD = 1 AND CLS_ING = 1 AND PRODUCT_NAME IS NOT NULL AND PRODUCT_NAME <> ''"
        else:
            raise ValueError("source must be 'KOK' OR 'HOMESHOPPING'")

        cols = list_columns(conn, table)
        if "PRODUCT_NAME" not in cols:
            raise RuntimeError(f"{table} 테이블에 PRODUCT_NAME 컬럼 없음. 실제: {cols}")

        id_col = pick_id_column(cols, id_override)
        select_id = f"`{id_col}` AS PRODUCT_ID" if id_col else "NULL AS PRODUCT_ID"

        sql = f"SELECT {select_id}, `PRODUCT_NAME` FROM `{table}` WHERE {where} LIMIT %s"
        df = pd.read_sql(sql, conn, params=[limit])
        df["SOURCE"] = "KOK" if table == "KOK_CLASSIFY" else "HOMESHOPPING"
        return df
    finally:
        conn.close()
