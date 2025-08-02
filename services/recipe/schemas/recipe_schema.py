"""
레시피 및 재료 응답/요청용 Pydantic 스키마 모듈
- 모든 필드/변수는 소문자
- DB ORM과 분리, API 직렬화/유효성 검증용
"""

from pydantic import BaseModel, Field
from typing import Optional, List

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

    class Config:
        orm_mode = True


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

    class Config:
        orm_mode = True

class RecipeListItem(RecipeBase):
    """레시피 추천/검색/목록 응답용"""
    matched_ingredient_count: Optional[int] = None

class RecipeListResponse(BaseModel):
    """레시피 목록(추천/검색/페이지네이션) 응답"""
    recipes: List[RecipeListItem]

class RecipeDetailResponse(RecipeBase):
    """레시피 상세 응답(재료 포함)"""
    materials: List[Material] = Field(default_factory=list)


# -----------------------------
# 만개의 레시피 URL 응답
# -----------------------------

class RecipeUrlResponse(BaseModel):
    url: str


# -----------------------------
# 별점 스키마
# -----------------------------

class RecipeRatingResponse(BaseModel):
    recipe_id: int
    rating: Optional[float] = None

class RecipeRatingCreate(BaseModel):
    rating: float


# -----------------------------
# 후기 스키마
# -----------------------------

class CommentCreate(BaseModel):
    comment: str

class Comment(BaseModel):
    comment_id: int
    recipe_id: int
    user_id: int
    comment: str

class CommentListResponse(BaseModel):
    comments: List[Comment]
    total: int


# -----------------------------
# 상품 추천 스키마
# -----------------------------

class ProductInfo(BaseModel):
    product_id: int
    product_name: str
    product_image: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[int] = None
