"""Recipe rating schemas."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RatingValue(int, Enum):
    zero = 0
    one = 1
    two = 2
    three = 3
    four = 4
    five = 5


class RecipeRatingCreate(BaseModel):
    """별점 등록 요청 바디"""

    rating: RatingValue = Field(..., description="0~5 정수만 허용")


class RecipeRatingResponse(BaseModel):
    recipe_id: int
    rating: Optional[float]
