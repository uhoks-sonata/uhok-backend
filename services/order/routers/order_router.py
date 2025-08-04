"""
레시피 상세/재료/만개의레시피 url, 후기, 별점 API 라우터 (MariaDB)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db

router = APIRouter()

