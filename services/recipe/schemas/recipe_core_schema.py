"""Core recipe response schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class Material(BaseModel):
    """재료 정보"""

    material_id: int
    recipe_id: Optional[int] = None
    material_name: Optional[str] = None
    measure_amount: Optional[str] = None
    measure_unit: Optional[str] = None
    details: Optional[str] = None

    class Config:
        from_attributes = True


class RecipeBase(BaseModel):
    """레시피 기본 정보"""

    recipe_id: int
    recipe_title: Optional[str] = None
    cooking_name: Optional[str] = None
    scrap_count: Optional[int] = None
    cooking_case_name: Optional[str] = None
    cooking_category_name: Optional[str] = None
    cooking_introduction: Optional[str] = None
    number_of_serving: Optional[str] = None
    thumbnail_url: Optional[str] = None
    recipe_url: Optional[str] = None

    class Config:
        from_attributes = True


class RecipeDetailResponse(RecipeBase):
    """레시피 상세 응답(재료 포함)"""

    materials: List[Material] = Field(default_factory=list)
    recipe_url: Optional[str]


class RecipeUrlResponse(BaseModel):
    url: str
