
# ============================================================================
# 주석 처리된 기존 API들 (참고용)
# ============================================================================

# @router.get("/kok")
# async def get_kok_products(
#     ingredient: str = Query(..., description="검색할 식재료명(예: 감자, 양파 등)"),
#     current_user = Depends(get_current_user),
#     background_tasks: BackgroundTasks = None,
#     db: AsyncSession = Depends(get_maria_service_db)
# ):
#     """
#     콕 쇼핑몰 내 ingredient(식재료명) 관련 상품 정보 조회
#     - 반환 필드명은 kok 모델 변수명(소문자)과 100% 일치
#     """
#     logger.info(f"콕 상품 검색 API 호출: user_id={current_user.user_id}, ingredient={ingredient}")
#     products = await get_kok_products_by_ingredient(db, ingredient)
    
#     # 식재료 기반 상품 검색 로그 기록
#     if background_tasks:
#         background_tasks.add_task(
#             send_user_log, 
#             user_id=current_user.user_id, 
#             event_type="ingredient_product_search", 
#             event_data={
#                 "ingredient": ingredient,
#                 "product_count": len(products)
#             }
#         )
    
#     return products

# @router.get("/homeshopping", response_model=HomeshoppingProductsResponse)
# async def get_homeshopping_products(
#     ingredient: str = Query(..., description="검색할 식재료명(예: 감자, 양파 등)"),
#     current_user = Depends(get_current_user),
#     background_tasks: BackgroundTasks = None,
#     db: AsyncSession = Depends(get_maria_service_db)
# ):
#     """
#     재료와 관련된 홈쇼핑 내 관련 상품 정보(상품이미지, 상품명, 브랜드명, 가격)를 조회한다.
#     """
#     logger.info(f"홈쇼핑 상품 검색 API 호출: user_id={current_user.user_id}, ingredient={ingredient}")
    
#     try:
#         products = await get_homeshopping_products_by_ingredient(db, ingredient)
        
#         # 홈쇼핑 상품 검색 로그 기록
#         if background_tasks:
#             background_tasks.add_task(
#                 send_user_log, 
#                 user_id=current_user.user_id, 
#                 event_type="homeshopping_product_search", 
#                 event_data={
#                     "ingredient": ingredient,
#                     "product_count": len(products)
#                 }
#             )
        
#         logger.info(f"홈쇼핑 상품 검색 완료: ingredient={ingredient}, 상품 개수={len(products)}")
        
#         return {
#             "ingredient": ingredient,
#             "products": products,
#             "total_count": len(products)
#         }
        
#     except Exception as e:
#         logger.error(f"홈쇼핑 상품 검색 실패: ingredient={ingredient}, user_id={current_user.user_id}, error={e}")
#         raise HTTPException(
#             status_code=500, 
#             detail="홈쇼핑 상품 검색 중 오류가 발생했습니다."
#         )

###########################################################
# @router.get("/{recipe_id}/comments", response_model=RecipeCommentListResponse)
# async def list_comments(
#         recipe_id: int,
#         page: int = 1,
#         size: int = 10,
#         db: AsyncSession = Depends(get_maria_service_db)
# ):
#     """
#         레시피별 후기(코멘트) 목록(페이지네이션)
#     """
#     comments, total = await get_recipe_comments(db, recipe_id, page, size)
#     return {"comments": comments, "total": total}
#
#
# @router.post("/{recipe_id}/comment", response_model=RecipeComment)
# async def create_comment(
#         recipe_id: int,
#         req: RecipeCommentCreate,
#         db: AsyncSession = Depends(get_maria_service_db)
# ):
#     """
#         레시피 후기(코멘트) 등록
#     """
#     # 실서비스에서는 user_id를 인증에서 추출
#     comment = await add_recipe_comment(db, recipe_id, user_id=1, comment=req.comment)
#     return comment
#
# # 소진 횟수 포함
# @router.get("/by-ingredients")
# async def by_ingredients(
#     ingredient: List[str] = Query(..., min_length=3, description="식재료 리스트 (최소 3개)"),
#     amount: Optional[List[str]] = Query(None, description="각 재료별 분량(옵션)"),
#     unit: Optional[List[str]] = Query(None, description="각 재료별 단위(옵션)"),
#     consume_count: Optional[int] = Query(None, description="재료 소진 횟수(옵션)"),
#     page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
#     size: int = Query(5, ge=1, le=50, description="페이지당 결과 개수"),
#     db: AsyncSession = Depends(get_maria_service_db)
# ):
#     """
#     재료/분량/단위/소진횟수 기반 레시피 추천 (페이지네이션)
#     - matched_ingredient_count 포함
#     - 응답: recipes(추천 목록), page(현재 페이지), total(전체 결과 개수)
#     """
#     # amount/unit 길이 체크
#     if (amount and len(amount) != len(ingredient)) or (unit and len(unit) != len(ingredient)):
#         from fastapi import HTTPException
#         raise HTTPException(status_code=400, detail="amount, unit 파라미터 개수가 ingredient와 일치해야 합니다.")
#     # 추천 결과 + 전체 개수 반환
#     recipes, total = await recommend_recipes_by_ingredients(
#         db, ingredient, amount, unit, consume_count, page=page, size=size
#     )
#     return {
#         "recipes": recipes,
#         "page": page,
#         "total": total
#     }
