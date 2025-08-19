#!/usr/bin/env python3
"""
조합 시스템 테스트 예제
"""

import asyncio
from services.recipe.combination_tracker import combination_tracker

async def test_combination_tracker():
    """조합 추적 시스템 테스트"""
    
    # 테스트 데이터
    user_id = 123
    ingredients = ["김치", "돼지고기", "두부"]
    amounts = [200.0, 300.0, 100.0]
    units = ["g", "g", "g"]
    
    print("=== 조합 추적 시스템 테스트 ===")
    
    # 1. 재료 해시 생성
    ingredients_hash = combination_tracker.generate_ingredients_hash(ingredients, amounts, units)
    print(f"재료 해시: {ingredients_hash}")
    
    # 2. 1조합에서 사용된 레시피 추적
    combo1_recipe_ids = [101, 102, 103]  # 김치찌개, 김치볶음밥, 두부조림
    combination_tracker.track_used_recipes(user_id, ingredients_hash, 1, combo1_recipe_ids)
    print(f"1조합 추적 완료: {combo1_recipe_ids}")
    
    # 3. 2조합에서 제외할 레시피 ID 조회
    excluded_ids = combination_tracker.get_excluded_recipe_ids(user_id, ingredients_hash, 2)
    print(f"2조합에서 제외할 레시피 ID: {excluded_ids}")
    
    # 4. 2조합에서 사용된 레시피 추적
    combo2_recipe_ids = [201, 202, 203]  # 돼지고기볶음, 김치국, 두부김치
    combination_tracker.track_used_recipes(user_id, ingredients_hash, 2, combo2_recipe_ids)
    print(f"2조합 추적 완료: {combo2_recipe_ids}")
    
    # 5. 3조합에서 제외할 레시피 ID 조회
    excluded_ids = combination_tracker.get_excluded_recipe_ids(user_id, ingredients_hash, 3)
    print(f"3조합에서 제외할 레시피 ID: {excluded_ids}")
    
    # 6. 3조합에서 사용된 레시피 추적
    combo3_recipe_ids = [301, 302, 303]  # 김치전, 돼지고기김치찌개, 두부볶음
    combination_tracker.track_used_recipes(user_id, ingredients_hash, 3, combo3_recipe_ids)
    print(f"3조합 추적 완료: {combo3_recipe_ids}")
    
    # 7. 전체 조합 정보 조회
    combination_info = combination_tracker.get_combination_info(user_id, ingredients_hash)
    print(f"전체 조합 정보: {combination_info}")
    
    # 8. 추적 데이터 삭제
    combination_tracker.clear_user_combinations(user_id, ingredients_hash)
    print("추적 데이터 삭제 완료")
    
    # 9. 삭제 확인
    combination_info_after = combination_tracker.get_combination_info(user_id, ingredients_hash)
    print(f"삭제 후 조합 정보: {combination_info_after}")

def test_ingredients_hash():
    """재료 해시 생성 테스트"""
    
    print("\n=== 재료 해시 생성 테스트 ===")
    
    # 동일한 재료, 다른 순서
    ingredients1 = ["김치", "돼지고기", "두부"]
    amounts1 = [200.0, 300.0, 100.0]
    units1 = ["g", "g", "g"]
    
    ingredients2 = ["돼지고기", "김치", "두부"]
    amounts2 = [300.0, 200.0, 100.0]
    units2 = ["g", "g", "g"]
    
    hash1 = combination_tracker.generate_ingredients_hash(ingredients1, amounts1, units1)
    hash2 = combination_tracker.generate_ingredients_hash(ingredients2, amounts2, units2)
    
    print(f"순서 1 해시: {hash1}")
    print(f"순서 2 해시: {hash2}")
    print(f"해시 동일 여부: {hash1 == hash2}")

if __name__ == "__main__":
    # 동기 함수 테스트
    test_ingredients_hash()
    
    # 비동기 함수 테스트
    asyncio.run(test_combination_tracker())
