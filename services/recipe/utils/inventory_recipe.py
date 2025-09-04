# -*- coding: utf-8 -*-
"""
Recipe 추천 시스템 유틸리티
- 순차적 재고 소진 알고리즘
- 레시피 추천 관련 유틸리티 함수들
"""

import copy
import pandas as pd
from typing import List, Dict, Optional, Tuple, Set
from common.logger import get_logger

logger = get_logger("recipe_recommendation_utils")


def recommend_sequentially_for_inventory(initial_ingredients, recipe_material_map, recipe_df, mat2recipes, max_results: Optional[int] = None):
    """
    순차적 재고 소진 알고리즘으로 레시피 추천 (Streamlit 코드와 동일한 로직)
    - 재료를 가장 효율적으로 사용하는 레시피를 순서대로 추천
    - max_results에 도달하면 조기 중단하여 성능 최적화
    """
    # 내부 함수: 단위를 정규화 (소문자 + 앞뒤 공백 제거)
    def _norm(u):
        return (u or "").strip().lower()

    # 단위 호환 규칙: 둘 중 하나라도 비어있거나(lower 후) 동일하면 ok
    def units_compatible(u_have: str, u_req: str) -> bool:
        a = (u_have or "").strip().lower()
        b = (u_req or "").strip().lower()
        return (not a) or (not b) or (a == b)

    # 현재 남은 재고 키만 사용하여 빠르게 후보 레시피 집합 구성
    def candidate_recipe_ids_from_stock(remaining_stock: Dict[str, Dict], mat2recipes: Dict[str, Set[int]]) -> Set[int]:
        current_ingredients = [k for k, v in remaining_stock.items() if v["amount"] > 1e-9]
        cand: Set[int] = set()
        for m in current_ingredients:
            cand |= mat2recipes.get(m, set())
        return cand

    # 평가: 레시피 내 '필요량'과 '재고'를 비교해 최대 사용량을 계산 (temp 재고를 줄이면서)
    def score_recipe_usage(rid: int, remaining_stock: Dict[str, Dict], recipe_material_map: Dict[int, List]) -> Tuple[int, float, Dict[str, Dict]]:
        """
        반환: (사용 재료 '종류' 수, '총 사용량' 합계, 사용 상세 dict)
        - used_amt = req_amt (재고가 충분) or stock_amt (부족한 만큼)
        - temp 재고를 레시피 평가 중 줄여 재사용 문제 방지
        """
        materials = recipe_material_map.get(int(rid), [])
        temp_stock = {k: {"amount": v["amount"], "unit": v.get("unit")} for k, v in remaining_stock.items()}

        used_ingredients: Dict[str, Dict] = {}
        used_cnt = 0
        total_used = 0.0

        for m in materials:
            mat = m['mat']      # 재료 이름
            req_amt = m['amt']  # 필요한 양
            req_unit = m['unit']  # 단위
            
            s = temp_stock.get(mat)
            if not s:
                continue
            if s["amount"] <= 1e-9:
                continue
            if not units_compatible(s.get("unit"), req_unit):
                continue

            used_amt = req_amt if s["amount"] >= req_amt - 1e-9 else s["amount"]
            if used_amt > 1e-9:
                s["amount"] -= used_amt  # temp 차감
                used_ingredients[mat] = {"amount": used_amt, "unit": s.get("unit") or req_unit}
                used_cnt += 1
                total_used += float(used_amt)

        return used_cnt, total_used, used_ingredients

    # ⬇️ 순서 수정: remaining_stock을 먼저 구성한 뒤 사용
    remaining_stock = {
        ing['name']: {'amount': ing['amount'], 'unit': ing['unit']}
        for ing in initial_ingredients
    }

    # RECIPE_ID 컬럼을 int형으로 강제 변환 (정확한 비교를 위해)
    try:
        recipe_df['RECIPE_ID'] = recipe_df['RECIPE_ID'].astype(int)
        logger.info("RECIPE_ID 컬럼을 int형으로 변환 완료")
    except Exception as e:
        logger.error(f"RECIPE_ID 컬럼 변환 실패: {e}")
        return [], remaining_stock, False

    # 추천된 레시피 리스트
    recommended = []
    # 이미 사용된 레시피 ID를 저장하는 집합
    used_recipe_ids = set()

    # 가능한 재료가 남아 있는 한 반복
    while True:
        if not any(v["amount"] > 1e-9 for v in remaining_stock.values()):
            break

        candidates = candidate_recipe_ids_from_stock(remaining_stock, mat2recipes) - used_recipe_ids
        if not candidates:
            break

        best_recipe = None
        best_usage = {}
        best_cnt = 0
        best_total = -1.0

        for rid in candidates:
            cnt, total, used = score_recipe_usage(rid, remaining_stock, recipe_material_map)
            if (cnt > best_cnt) or (cnt == best_cnt and total > best_total):
                best_recipe = int(rid)
                best_usage = used
                best_cnt = cnt
                best_total = total

        if best_recipe is None or best_cnt == 0:
            break

        # 실제 차감 (선택된 레시피만)
        for m, d in best_usage.items():
            remaining_stock[m]["amount"] -= d["amount"]

        # 레시피 정보 조회
        try:
            rid_int = int(best_recipe)
            row = recipe_df[recipe_df['RECIPE_ID'] == rid_int]
        except (ValueError, TypeError) as e:
            logger.error(f"레시피 ID 변환 실패: {best_recipe}, 에러: {e}")
            used_recipe_ids.add(best_recipe)
            continue
        if row.empty:
            # 레시피 정보가 없으면 무시하고 다음으로 진행
            used_recipe_ids.add(best_recipe)
            continue

        # 레시피 정보 딕셔너리로 변환하고 사용된 재료 정보 추가
        recipe_info = row.iloc[0].to_dict()
        
        # Pydantic 스키마에 맞게 필드명 변환
        total_ingredients = len(recipe_material_map.get(best_recipe, []))
        logger.info(f"레시피 {best_recipe}의 전체 재료 개수: {total_ingredients}")
        
        formatted_recipe = {
            "recipe_id": recipe_info.get('RECIPE_ID'),
            "recipe_title": recipe_info.get('RECIPE_TITLE'),
            "cooking_name": recipe_info.get('COOKING_NAME'),
            "scrap_count": recipe_info.get('SCRAP_COUNT'),
            "cooking_case_name": recipe_info.get('COOKING_CASE_NAME'),
            "cooking_category_name": recipe_info.get('COOKING_CATEGORY_NAME'),
            "cooking_introduction": recipe_info.get('COOKING_INTRODUCTION'),
            "number_of_serving": recipe_info.get('NUMBER_OF_SERVING'),
            "thumbnail_url": recipe_info.get('THUMBNAIL_URL'),
            "recipe_url": recipe_info.get('RECIPE_URL'),
            "matched_ingredient_count": len(best_usage),  # 사용된 재료 개수
            "total_ingredients_count": total_ingredients,  # 레시피 전체 재료 개수
            "used_ingredients": []
        }
        
        logger.info(f"formatted_recipe 생성 완료: {formatted_recipe}")
        
        # 사용된 재료 정보를 API 명세서 형식으로 변환
        for mat_name, detail in best_usage.items():
            try:
                measure_amount = float(detail.get('amount', 0)) if detail.get('amount') is not None else None
            except (ValueError, TypeError):
                measure_amount = None
            
            formatted_recipe["used_ingredients"].append({
                "material_name": mat_name,
                "measure_amount": measure_amount,
                "measure_unit": detail.get('unit', '')
            })
        
        # 최종 추천 목록에 추가
        logger.info(
            f"추천 목록에 추가: recipe_id={formatted_recipe['recipe_id']}, "
            f"total_ingredients_count={formatted_recipe.get('total_ingredients_count')}"
        )
        logger.info(f"formatted_recipe 전체 내용: {formatted_recipe}")
        recommended.append(formatted_recipe)  # recipe_info가 아닌 formatted_recipe를 추가
        used_recipe_ids.add(best_recipe)  # 재사용 방지

        # 최대 결과 수에 도달하면 조기 중단
        if max_results is not None and len(recommended) >= max_results:
            return recommended, remaining_stock, True

    # 추천된 레시피와 남은 재고를 반환
    return recommended, remaining_stock, False


def get_recipe_url(recipe_id: int) -> str:
    """
    만개의 레시피 상세페이지 URL 동적 생성
    """
    return f"https://www.10000recipe.com/recipe/{recipe_id}"


def format_recipe_for_response(recipe_info: Dict, used_ingredients: List[Dict], total_ingredients: int) -> Dict:
    """
    레시피 정보를 API 응답 형식으로 포맷팅
    """
    return {
        "recipe_id": recipe_info.get('RECIPE_ID'),
        "recipe_title": recipe_info.get('RECIPE_TITLE'),
        "cooking_name": recipe_info.get('COOKING_NAME'),
        "scrap_count": recipe_info.get('SCRAP_COUNT'),
        "cooking_case_name": recipe_info.get('COOKING_CASE_NAME'),
        "cooking_category_name": recipe_info.get('COOKING_CATEGORY_NAME'),
        "cooking_introduction": recipe_info.get('COOKING_INTRODUCTION'),
        "number_of_serving": recipe_info.get('NUMBER_OF_SERVING'),
        "thumbnail_url": recipe_info.get('THUMBNAIL_URL'),
        "recipe_url": recipe_info.get('RECIPE_URL'),
        "matched_ingredient_count": len(used_ingredients),
        "total_ingredients_count": total_ingredients,
        "used_ingredients": used_ingredients
    }


def normalize_unit(unit: str) -> str:
    """
    단위를 정규화 (소문자 + 앞뒤 공백 제거)
    """
    return (unit or "").strip().lower()


def can_use_ingredient(stock_amount: float, stock_unit: str, req_amount: float, req_unit: str) -> bool:
    """
    재료 사용 가능 여부 판단
    """
    if stock_amount <= 1e-3:
        return False
    
    if req_amount is None:
        return False
    
    # 단위가 일치하거나 둘 중 하나라도 명시되지 않았으면 사용 가능
    if not stock_unit or not req_unit:
        return True
    
    return normalize_unit(stock_unit) == normalize_unit(req_unit)


def calculate_used_amount(stock_amount: float, req_amount: float) -> float:
    """
    실제 사용할 양 계산 (재고와 필요량 중 작은 값)
    """
    try:
        return min(req_amount, stock_amount)
    except (ValueError, TypeError):
        return 0.0


__all__ = [
    "recommend_sequentially_for_inventory",
    "get_recipe_url",
    "format_recipe_for_response",
    "normalize_unit",
    "can_use_ingredient",
    "calculate_used_amount"
]
