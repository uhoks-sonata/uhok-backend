"""
레시피 식재료와 상품명 간의 키워드 매칭 유틸리티

주요 기능:
1. 상품명에서 식재료 키워드 추출
2. 레시피 식재료와 상품명 간의 매칭 점수 계산
3. 보유/장바구니/미보유 상태 판별
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from common.logger import get_logger

logger = get_logger("ingredient_matcher")


@dataclass
class IngredientMatch:
    """식재료 매칭 결과"""
    material_name: str
    product_name: str
    match_score: float
    match_type: str  # 'exact', 'contains', 'partial', 'none'


class IngredientKeywordExtractor:
    """상품명에서 식재료 키워드를 추출하는 클래스"""
    
    # 일반적인 식재료 관련 단어들 (제거할 단어)
    REMOVE_WORDS = {
        '신선', '프리미엄', '고급', '특급', '1등급', '2등급', '3등급',
        '국내산', '수입산', '친환경', '유기농', '무농약', '무항생제',
        '냉동', '냉장', '신선', '즉석', '간편', '손질', '세척',
        'kg', 'g', '개', '봉', '팩', '박스', '세트', '묶음',
        '대형', '중형', '소형', '큰', '작은', '굵은', '가는',
        '알', '껍질', '씨', '줄기', '잎', '뿌리', '줄기'
    }
    
    # 식재료별 대체 표현
    INGREDIENT_ALIASES = {
        '돼지고기': ['돼지', '돈육', '삼겹살', '목살', '등심', '안심', '갈비'],
        '소고기': ['소', '쇠고기', '우육', '등심', '안심', '갈비', '양지'],
        '닭고기': ['닭', '치킨', '닭가슴살', '닭다리', '닭날개'],
        '양파': ['양파', '양파'],
        '마늘': ['마늘', '다진마늘', '편마늘', '마늘가루'],
        '생강': ['생강', '다진생강', '생강가루'],
        '고추': ['고추', '청양고추', '홍고추', '고추가루'],
        '파': ['파', '대파', '쪽파', '실파'],
        '배추': ['배추', '알배기배추', '포기배추'],
        '무': ['무', '무우', '청무', '백무'],
        '당근': ['당근', '홍당근'],
        '감자': ['감자', '포테이토'],
        '고구마': ['고구마', '스위트포테이토'],
        '버섯': ['버섯', '느타리', '팽이', '표고', '양송이'],
        '두부': ['두부', '순두부', '연두부'],
        '계란': ['계란', '달걀', '계란'],
        '쌀': ['쌀', '백미', '현미', '찰현미'],
        '된장': ['된장', '청국장'],
        '고추장': ['고추장', '양념고추장'],
        '간장': ['간장', '양조간장', '진간장'],
        '소금': ['소금', '천일염', '정제염'],
        '설탕': ['설탕', '백설탕', '황설탕'],
        '식용유': ['식용유', '들기름', '참기름', '올리브유'],
        '참기름': ['참기름', '들기름'],
        '액젓': ['액젓', '새우젓', '멸치젓'],
        '다시다': ['다시다', '다시마', '가쓰오부시'],
        '들깨가루': ['들깨가루', '들깨', '깨가루']
    }
    
    def __init__(self):
        # 별칭을 역방향으로 매핑 (상품명 -> 표준명)
        self.reverse_aliases = {}
        for standard_name, aliases in self.INGREDIENT_ALIASES.items():
            for alias in aliases:
                self.reverse_aliases[alias.lower()] = standard_name
    
    def extract_keywords(self, product_name: str) -> List[str]:
        """
        상품명에서 식재료 키워드를 추출
        
        Args:
            product_name: 상품명
            
        Returns:
            추출된 식재료 키워드 리스트
        """
        if not product_name:
            return []
        
        # 소문자 변환 및 특수문자 제거
        cleaned_name = re.sub(r'[^\w\s가-힣]', ' ', product_name.lower())
        
        # 공백으로 분리
        words = cleaned_name.split()
        
        # 식재료 키워드 추출
        keywords = []
        for word in words:
            # 제거할 단어인지 확인
            if word in self.REMOVE_WORDS:
                continue
            
            # 식재료 별칭에 해당하는지 확인
            if word in self.reverse_aliases:
                standard_name = self.reverse_aliases[word]
                if standard_name not in keywords:
                    keywords.append(standard_name)
            
            # 일반적인 식재료 패턴 확인 (길이가 2글자 이상)
            elif len(word) >= 2:
                # 숫자나 단위가 포함된 경우 제외
                if not re.search(r'\d', word):
                    keywords.append(word)
        
        logger.debug(f"상품명 '{product_name}'에서 추출된 키워드: {keywords}")
        return keywords
    
    def calculate_match_score(self, material_name: str, product_keywords: List[str]) -> float:
        """
        레시피 식재료와 상품 키워드 간의 매칭 점수 계산
        
        Args:
            material_name: 레시피 식재료명
            product_keywords: 상품에서 추출한 키워드 리스트
            
        Returns:
            매칭 점수 (0.0 ~ 1.0)
        """
        if not product_keywords:
            return 0.0
        
        material_lower = material_name.lower()
        max_score = 0.0
        
        for keyword in product_keywords:
            keyword_lower = keyword.lower()
            
            # 정확 일치
            if material_lower == keyword_lower:
                score = 1.0
            # 포함 관계 (재료가 상품에 포함)
            elif material_lower in keyword_lower:
                score = 0.8
            # 포함 관계 (상품이 재료에 포함)
            elif keyword_lower in material_lower:
                score = 0.7
            # 부분 일치 (공통 부분이 70% 이상)
            else:
                common_chars = set(material_lower) & set(keyword_lower)
                total_chars = set(material_lower) | set(keyword_lower)
                if total_chars:
                    similarity = len(common_chars) / len(total_chars)
                    score = similarity if similarity >= 0.7 else 0.0
                else:
                    score = 0.0
            
            max_score = max(max_score, score)
        
        return max_score


class IngredientStatusMatcher:
    """레시피 식재료의 보유/장바구니/미보유 상태를 판별하는 클래스"""
    
    def __init__(self):
        self.keyword_extractor = IngredientKeywordExtractor()
        self.match_threshold = 0.5  # 매칭 점수 임계값 (0.6에서 0.5로 낮춤)
    
    def match_orders_to_ingredients(
        self, 
        materials: List[str], 
        orders: List[Dict]
    ) -> Dict[str, Dict]:
        """
        주문 내역과 레시피 식재료를 매칭하여 보유 상태 판별
        
        Args:
            materials: 레시피 식재료 리스트
            orders: 주문 내역 리스트 (kok_orders, homeshopping_orders 포함)
            
        Returns:
            재료별 매칭 결과 {material_name: order_info}
        """
        matches = {}
        
        for material in materials:
            best_match = None
            best_score = 0.0
            
            for order in orders:
                # 콕 주문 확인
                for kok_order in order.get("kok_orders", []):
                    if hasattr(kok_order, 'product_name') and kok_order.product_name:
                        score = self._calculate_material_match(material, kok_order.product_name)
                        if score > best_score and score >= self.match_threshold:
                            best_score = score
                            best_match = {
                                "order_id": order["order_id"],
                                "order_date": order["order_time"],
                                "order_type": "kok",
                                "product_name": kok_order.product_name,
                                "quantity": getattr(kok_order, "quantity", 1),
                                "match_score": score
                            }
                
                # 홈쇼핑 주문 확인
                for hs_order in order.get("homeshopping_orders", []):
                    if hasattr(hs_order, 'product_name') and hs_order.product_name:
                        score = self._calculate_material_match(material, hs_order.product_name)
                        if score > best_score and score >= self.match_threshold:
                            best_score = score
                            best_match = {
                                "order_id": order["order_id"],
                                "order_date": order["order_time"],
                                "order_type": "homeshopping",
                                "product_name": hs_order.product_name,
                                "quantity": getattr(hs_order, "quantity", 1),
                                "match_score": score
                            }
            
            if best_match:
                matches[material] = best_match
                logger.info(f"주문 매칭: {material} -> {best_match['product_name']} (점수: {best_match['match_score']:.2f})")
        
        return matches
    
    def match_cart_to_ingredients(
        self, 
        materials: List[str], 
        kok_cart_items: List, 
        exclude_owned: List[str] = None
    ) -> Dict[str, Dict]:
        """
        장바구니와 레시피 식재료를 매칭하여 장바구니 상태 판별
        
        Args:
            materials: 레시피 식재료 리스트
            kok_cart_items: 콕 장바구니 아이템 리스트
            exclude_owned: 이미 보유 상태인 재료 리스트 (제외할 재료)
            
        Returns:
            재료별 장바구니 매칭 결과 {material_name: cart_info}
        """
        if exclude_owned is None:
            exclude_owned = []
        
        matches = {}
        
        for material in materials:
            if material in exclude_owned:
                continue
                
            best_match = None
            best_score = 0.0
            
            # 콕 장바구니 확인
            for cart_item, product_name in kok_cart_items:
                if product_name:
                    score = self._calculate_material_match(material, product_name)
                    if score > best_score and score >= self.match_threshold:
                        best_score = score
                        best_match = {
                            "cart_id": cart_item.kok_cart_id,
                            "cart_type": "kok",
                            "product_name": product_name,
                            "quantity": cart_item.kok_quantity,
                            "match_score": score
                        }
            
            if best_match:
                matches[material] = best_match
                logger.info(f"장바구니 매칭: {material} -> {best_match['product_name']} (점수: {best_match['match_score']:.2f})")
        
        return matches
    
    def _calculate_material_match(self, material_name: str, product_name: str) -> float:
        """
        개별 재료와 상품명 간의 매칭 점수 계산
        
        Args:
            material_name: 재료명
            product_name: 상품명
            
        Returns:
            매칭 점수 (0.0 ~ 1.0)
        """
        return self.keyword_extractor.calculate_match_score(material_name, [product_name])
    
    def determine_ingredient_status(
        self,
        materials: List[str],
        order_matches: Dict[str, Dict],
        cart_matches: Dict[str, Dict]
    ) -> Tuple[List[Dict], Dict]:
        """
        모든 재료의 최종 상태를 판별
        
        Args:
            materials: 레시피 재료 리스트
            order_matches: 주문 매칭 결과
            cart_matches: 장바구니 매칭 결과
            
        Returns:
            (재료별 상태 리스트, 요약 정보)
        """
        ingredients_status = []
        owned_count = 0
        cart_count = 0
        not_owned_count = 0
        
        for material in materials:
            status = "not_owned"
            order_info = None
            cart_info = None
            
            # 보유 상태 확인
            if material in order_matches:
                status = "owned"
                order_info = order_matches[material]
                owned_count += 1
            # 장바구니 상태 확인 (보유가 아닌 경우에만)
            elif material in cart_matches:
                status = "cart"
                cart_info = cart_matches[material]
                cart_count += 1
            else:
                not_owned_count += 1
            
            # 재료 상태 정보 추가
            ingredients_status.append({
                "material_name": material,
                "status": status,
                "order_info": order_info,
                "cart_info": cart_info
            })
        
        # 요약 정보 생성
        summary = {
            "total_ingredients": len(materials),
            "owned_count": owned_count,
            "cart_count": cart_count,
            "not_owned_count": not_owned_count
        }
        
        return ingredients_status, summary


# 편의 함수들
def extract_ingredient_keywords(product_name: str) -> List[str]:
    """상품명에서 식재료 키워드 추출 (간편 함수)"""
    extractor = IngredientKeywordExtractor()
    return extractor.extract_keywords(product_name)


def calculate_ingredient_match(material_name: str, product_name: str) -> float:
    """재료와 상품명 간의 매칭 점수 계산 (간편 함수)"""
    extractor = IngredientKeywordExtractor()
    return extractor.calculate_match_score(material_name, [product_name])
