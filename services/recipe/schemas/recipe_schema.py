"""
레시피 및 재료 응답/요청용 Pydantic 스키마 모듈
- DB ORM과 분리, API 직렬화/유효성 검증용
"""

from pydantic import BaseModel, Field
from typing import Optional, List

class MaterialBase(BaseModel):
    """재료(MATERIAL) 기본 정보"""
    MATERIAL_ID: int
    MATERIAL_NAME: Optional[str] = None
    MEASURE_AMOUNT: Optional[str] = None
    MEASURE_UNIT: Optional[str] = None
    DETAILS: Optional[str] = None

    class Config:
        orm_mode = True

class RecipeBase(BaseModel):
    """레시피(Recipe) 기본 정보"""
    RECIPE_ID: int
    RECIPE_TITLE: Optional[str] = None
    COOKING_NAME: Optional[str] = None
    SCRAP_COUNT: Optional[int] = None
    COOKING_CASE_NAME: Optional[str] = None
    COOKING_CATEGORY_NAME: Optional[str] = None
    COOKING_INTRODUCTION: Optional[str] = None
    NUMBER_OF_SERVING: Optional[str] = None
    THUMBNAIL_URL: Optional[str] = None

    class Config:
        orm_mode = True

class RecipeDetail(RecipeBase):
    """레시피 상세 응답 스키마 (재료 리스트 포함)"""
    materials: List[MaterialBase] = Field(default_factory=list)
