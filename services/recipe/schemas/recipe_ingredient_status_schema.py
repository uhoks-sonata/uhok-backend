"""Recipe ingredient-status schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    thumb_img_url: Optional[str] = Field(None, description="상품 썸네일 이미지 URL")

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
                            "order_type": "kok",
                        }
                    ],
                    "cart": [{"material_name": "양파", "cart_id": 101}],
                    "not_owned": [{"material_name": "당근"}],
                },
                "summary": {
                    "total_ingredients": 3,
                    "owned_count": 1,
                    "cart_count": 1,
                    "not_owned_count": 1,
                },
            }
        }
