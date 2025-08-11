"""
레시피 및 재료 응답/요청용 Pydantic 스키마 모듈
- 모든 필드/변수는 소문자
- DB ORM과 분리, API 직렬화/유효성 검증용
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

# -----------------------------
# 별점 스키마 (별점 0~5 int, 후기 없음)
# -----------------------------

class RatingValue(int, Enum):
    zero = 0
    one = 1
    two = 2
    three = 3
    four = 4
    five = 5

# -----------------------------
# 재료(MATERIAL) 스키마
# -----------------------------

class Material(BaseModel):
    """재료 정보"""
    material_id: int
    recipe_id: Optional[int] = None
    material_name: Optional[str] = None
    measure_amount: Optional[str] = None
    measure_unit: Optional[str] = None
    details: Optional[str] = None
    class Config: from_attributes = True

# -----------------------------
# 레시피 기본/목록/상세 스키마
# -----------------------------

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
    class Config: from_attributes = True

class RecipeDetailResponse(RecipeBase):
    """레시피 상세 응답(재료 포함)"""
    materials: List[Material] = Field(default_factory=list)
    recipe_url: Optional[str]

# -----------------------------
# 만개의 레시피 URL 응답
# -----------------------------

class RecipeUrlResponse(BaseModel):
    url: str

# -----------------------------
# 재료 기반 레시피 추천 응답 스키마
# -----------------------------

class UsedIngredient(BaseModel):
    """사용된 재료 정보"""
    material_name: str
    measure_amount: Optional[float] = None
    measure_unit: Optional[str] = None

class RecipeByIngredientsResponse(BaseModel):
    """재료 기반 레시피 추천 응답"""
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
    matched_ingredient_count: int
    total_ingredients_count: int = Field(..., description="레시피 전체 재료 개수")
    used_ingredients: List[UsedIngredient] = Field(default_factory=list)
    
    class Config:
        from_attributes = True
        populate_by_name = True

class RecipeByIngredientsListResponse(BaseModel):
    """재료 기반 레시피 추천 목록 응답"""
    recipes: List[RecipeByIngredientsResponse]
    page: int
    total: int

# -----------------------------
# 별점 스키마
# -----------------------------

class RecipeRatingCreate(BaseModel):
    """별점 등록 요청 바디"""
    rating: RatingValue = Field(..., description="0~5 정수만 허용")

class RecipeRatingResponse(BaseModel):
    recipe_id: int
    rating: Optional[float]  # 평균 별점은 float


###########################################################
# # -----------------------------
# # 후기 스키마
# # -----------------------------
#
# class RecipeCommentCreate(BaseModel):
#     """후기 등록 요청 바디"""
#     comment: str
#
# class RecipeComment(BaseModel):
#     comment_id: int
#     recipe_id: int
#     user_id: int
#     comment: str
#
# class RecipeCommentListResponse(BaseModel):
#     comments: List[RecipeComment]
#     total: int