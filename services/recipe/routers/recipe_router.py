from fastapi import APIRouter, Depends, status, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from services.user.database import get_db
from common.errors import BadRequestException, ConflictException, NotAuthenticatedException

router = APIRouter()

