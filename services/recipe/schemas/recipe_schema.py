"""
레시피 및 재료 응답/요청용 Pydantic 스키마 모듈
- 모든 필드/변수는 소문자
- DB ORM과 분리, API 직렬화/유효성 검증용
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

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
    combination_number: int = Field(..., description="현재 조합 번호 (1, 2, 3)")
    has_more_combinations: bool = Field(..., description="더 많은 조합이 있는지 여부")

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

class OrderInfo(BaseModel):
    """주문 정보"""
    order_id: int
    order_date: datetime
    order_type: str = Field(..., description="주문 유형: 'kok' 또는 'homeshopping'")
    product_name: str
    quantity: int
    
    class Config:
        from_attributes = True


class CartInfo(BaseModel):
    """장바구니 정보"""
    cart_id: int
    cart_type: str = Field(..., description="장바구니 유형: 'kok' 또는 'homeshopping'")
    product_name: str
    quantity: int
    
    class Config:
        from_attributes = True


class IngredientStatusSummary(BaseModel):
    """식재료 상태 요약"""
    total_ingredients: int
    owned_count: int
    cart_count: int
    not_owned_count: int
    
    class Config:
        from_attributes = True


class IngredientStatusItem(BaseModel):
    """개별 식재료 상태 정보"""
    material_name: str
    status: str = Field(..., description="상태: 'owned', 'cart', 'not_owned'")
    order_info: Optional[OrderInfo] = None
    cart_info: Optional[CartInfo] = None
    
    class Config:
        from_attributes = True


class RecipeIngredientStatusResponse(BaseModel):
    """레시피 식재료 상태 조회 응답 스키마"""
    recipe_id: int
    user_id: int
    ingredients: List[IngredientStatusItem]
    summary: IngredientStatusSummary
    
    class Config:
        from_attributes = True


class IngredientOwnedStatus(BaseModel):
    """보유 중인 식재료 상태"""
    material_name: str
    order_date: datetime
    order_id: int
    order_type: str = Field(..., description="주문 유형: 'kok' 또는 'homeshopping'")
    
    class Config:
        from_attributes = True


class IngredientCartStatus(BaseModel):
    """장바구니에 있는 식재료 상태"""
    material_name: str
    cart_id: int
    
    class Config:
        from_attributes = True


class IngredientNotOwnedStatus(BaseModel):
    """미보유 식재료 상태"""
    material_name: str
    
    class Config:
        from_attributes = True


class HomeshoppingProductInfo(BaseModel):
    """홈쇼핑 상품 정보 스키마"""
    product_id: int = Field(..., description="상품 ID")
    product_name: str = Field(..., description="상품명")
    brand_name: Optional[str] = Field(None, description="브랜드명")
    price: int = Field(..., description="가격")
    image_url: Optional[str] = Field(None, description="상품 이미지 URL")
    
    class Config:
        from_attributes = True


class HomeshoppingProductsResponse(BaseModel):
    """홈쇼핑 상품 목록 응답 스키마"""
    ingredient: str = Field(..., description="검색한 식재료명")
    products: List[HomeshoppingProductInfo] = Field(default_factory=list, description="상품 목록")
    total_count: int = Field(..., description="총 상품 개수")
    
    class Config:
        from_attributes = True


class RecipeIngredientStatusDetailResponse(BaseModel):
    """레시피 식재료 상태 상세 응답 스키마"""
    recipe_id: int
    user_id: int
    ingredients_status: Dict[str, List[Dict[str, Any]]] = Field(..., description="식재료 상태별 분류")
    summary: Dict[str, int] = Field(..., description="상태별 요약 정보")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "recipe_id": 123,
                "user_id": 456,
                "ingredients_status": {
                    "owned": [
                        {
                            "material_name": "감자",
                            "order_date": "2024-01-15T10:30:00",
                            "order_id": 789,
                            "order_type": "kok"
                        }
                    ],
                    "cart": [
                        {
                            "material_name": "양파",
                            "cart_id": 101
                        }
                    ],
                    "not_owned": [
                        {"material_name": "당근"}
                    ]
                },
                "summary": {
                    "total_ingredients": 3,
                    "owned_count": 1,
                    "cart_count": 1,
                    "not_owned_count": 1
                }
            }
        }