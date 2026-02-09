from datetime import date, time
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

class KokHomeshoppingRecommendationRequest(BaseModel):
    """KOK 상품 기반 홈쇼핑 추천 요청"""
    k: int = Field(5, ge=1, le=20, description="추천 상품 개수")


class KokHomeshoppingRecommendationProduct(BaseModel):
    """홈쇼핑 추천 상품 정보"""
    product_id: int
    product_name: str
    store_name: Optional[str] = None
    sale_price: Optional[int] = None
    dc_price: Optional[int] = None
    dc_rate: Optional[int] = None
    thumb_img_url: str
    live_date: Optional[date] = None
    live_start_time: Optional[time] = None
    live_end_time: Optional[time] = None
    similarity_score: Optional[float] = Field(None, description="유사도 점수")
    
    class Config:
        from_attributes = True


class KokHomeshoppingRecommendationResponse(BaseModel):
    """KOK 상품 기반 홈쇼핑 추천 응답"""
    kok_product_id: Optional[int] = None
    kok_product_name: str
    recommendations: List[KokHomeshoppingRecommendationProduct] = Field(default_factory=list)
    total_count: int
    algorithm_info: Dict[str, str] = Field(default_factory=dict, description="추천 알고리즘 정보")
    product_recommendations: Optional[Dict[str, List[KokHomeshoppingRecommendationProduct]]] = Field(
        default=None, description="각 KOK 상품별 추천 결과"
    )
