from typing import List, Optional

from pydantic import BaseModel, Field

class RecipeRecommendation(BaseModel):
    """레시피 추천 정보"""
    recipe_id: int
    recipe_name: str
    scrap_count: Optional[int] = None
    ingredients: List[str]
    description: str
    recipe_image_url: Optional[str] = None
    number_of_serving: Optional[str] = None
    
    class Config:
        from_attributes = True


class RecipeRecommendationsResponse(BaseModel):
    """레시피 추천 응답"""
    recipes: List[RecipeRecommendation] = Field(default_factory=list)
    is_ingredient: bool
    extracted_keywords: List[str] = Field(default_factory=list, description="상품명에서 추출된 키워드")

