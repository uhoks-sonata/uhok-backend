"""Recipe recommendation and product recommendation schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


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


class ProductRecommendation(BaseModel):
    """상품 추천 정보"""

    source: str = Field(..., description="상품 출처 (homeshopping 또는 kok)")
    name: str = Field(..., description="상품명")
    live_id: Optional[int] = Field(None, description="홈쇼핑 라이브 ID (source가 homeshopping일 경우)")
    kok_product_id: Optional[int] = Field(None, description="KOK 상품 ID (source가 kok일 경우)")
    thumb_img_url: Optional[str] = Field(None, description="홈쇼핑 상품 썸네일 이미지 URL")
    image_url: Optional[str] = Field(None, description="KOK 상품 이미지 URL")
    brand_name: Optional[str] = Field(None, description="브랜드명")
    price: Optional[int] = Field(None, description="가격")
    homeshopping_id: Optional[int] = Field(None, description="홈쇼핑 ID (source가 homeshopping일 경우)")
    kok_discount_rate: Optional[int] = Field(None, description="KOK 할인율 (source가 kok일 경우)")
    kok_review_cnt: Optional[int] = Field(None, description="KOK 리뷰 개수 (source가 kok일 경우)")
    kok_review_score: Optional[float] = Field(None, description="KOK 리뷰 평점 (source가 kok일 경우)")
    dc_rate: Optional[int] = Field(None, description="홈쇼핑 할인율 (source가 homeshopping일 경우)")


class ProductRecommendResponse(BaseModel):
    """상품 추천 응답"""

    ingredient: str
    recommendations: List[ProductRecommendation] = Field(default_factory=list)
    total_count: int = Field(0, description="추천 상품 총 개수")
