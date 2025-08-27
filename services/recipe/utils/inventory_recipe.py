# -*- coding: utf-8 -*-
"""
Recipe 추천 시스템 유틸리티
- 순차적 재고 소진 알고리즘
- 레시피 추천 관련 유틸리티 함수들
"""

import copy
import pandas as pd
from typing import List, Dict, Optional, Tuple
from common.logger import get_logger

logger = get_logger("recipe_recommendation_utils")


def recommend_sequentially_for_inventory(initial_ingredients, recipe_material_map, recipe_df, max_results: Optional[int] = None):
    """
    순차적 재고 소진 알고리즘으로 레시피 추천
    - 재료를 가장 효율적으로 사용하는 레시피를 순서대로 추천
    - max_results에 도달하면 조기 중단하여 성능 최적화
    """
    # 내부 함수: 단위를 정규화 (소문자 + 앞뒤 공백 제거)
    def _norm(u):
        return (u or "").strip().lower()

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
        # 현재 재고 중 양이 0.001 이상인 재료 목록
        current_ingredients = [k for k, v in remaining_stock.items() if v.get('amount', 0) > 1e-3]
        if not current_ingredients:
            break  # 재료가 다 떨어졌으면 종료

        best_recipe = None         # 이번 라운드에서 추천할 최고의 레시피 ID
        best_usage = {}            # 그 레시피에서 실제 사용된 재료들
        max_used = 0               # 가장 많은 종류의 재료를 사용한 수치

        # 모든 레시피를 하나씩 탐색
        for rid, materials in recipe_material_map.items():
            try:
                rid = int(rid)
            except (ValueError, TypeError) as e:
                logger.error(f"레시피 ID 변환 실패: {rid}, 에러: {e}")
                continue
            
            if rid in used_recipe_ids:
                continue  # 이미 추천된 레시피는 스킵

            temp_stock = copy.deepcopy(remaining_stock)  # 재고 복사본 (시뮬레이션용)
            used_ingredients = {}  # 현재 레시피에서 사용된 재료

            # 이 레시피에 필요한 모든 재료를 순회
            for m in materials:
                mat = m['mat']      # 재료 이름
                req_amt = m['amt']  # 필요한 양
                req_unit = m['unit']  # 단위

                # 조건:
                # - 재고에 그 재료가 있음
                # - 필요한 양이 명시되어 있음
                # - 재고 수량이 충분함
                # - 단위가 일치하거나 둘 중 하나라도 명시되지 않았음
                if (
                    mat in temp_stock and
                    req_amt is not None and
                    temp_stock[mat].get('amount', 0) > 1e-3 and
                    (not temp_stock[mat].get('unit') or not req_unit
                     or _norm(temp_stock[mat]['unit']) == _norm(req_unit))
                ):
                    # 실제 사용할 양은 현재 재고와 필요량 중 작은 값
                    try:
                        used_amt = min(req_amt, temp_stock[mat]['amount'])
                        if used_amt > 1e-3:
                            temp_stock[mat]['amount'] -= used_amt  # 재고에서 차감
                            used_ingredients[mat] = {'amount': used_amt, 'unit': req_unit}
                    except (ValueError, TypeError) as e:
                        logger.error(f"재료 사용량 계산 실패: {mat}, req_amt: {req_amt}, stock: {temp_stock[mat]}, 에러: {e}")
                        continue

            # 현재 레시피가 지금까지 중 가장 많은 재료를 사용했다면 선택
            if used_ingredients and len(used_ingredients) > max_used:
                best_recipe = rid
                best_usage = used_ingredients
                max_used = len(used_ingredients)

        # 이번 라운드에 추천할 레시피가 없다면 종료
        if not best_recipe:
            break

        # 선택된 레시피의 재료를 실제 재고에서 차감
        for mat, detail in best_usage.items():
            try:
                amount_to_subtract = float(detail.get('amount', 0)) if detail.get('amount') is not None else 0
                remaining_stock[mat]['amount'] -= amount_to_subtract
            except (ValueError, TypeError) as e:
                logger.error(f"재료 수량 차감 실패: {mat}, detail: {detail}, 에러: {e}")
                continue

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
