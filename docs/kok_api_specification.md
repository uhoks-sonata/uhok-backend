# Kok 서비스 API 명세서

## 개요
Kok 서비스는 쇼핑몰 기능을 제공하는 API 서비스입니다. 상품 조회, 장바구니 관리, 주문 처리, 레시피 추천 등의 기능을 포함합니다.

## 주요 기능
- 상품 조회 및 검색
- 장바구니 관리 (추가, 수량 변경, 삭제)
- 프론트엔드 기반 상품 선택/해제 및 수량 조정
- 선택된 상품들로 주문 생성 (동일한 주문 ID)
- 선택된 상품들로 레시피 추천

## API 엔드포인트

### 1. 상품 관련 API

#### 1.1 할인 특가 상품 조회
- **기능**: 할인 중인 특가 상품 목록 조회
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/discounted`
- **헤더**: Authorization: Bearer {token}
- **응답 예시**:
  ```json
  {
    "products": [
      {
        "kok_product_id": 1,
        "kok_product_name": "신선한 소고기 500g",
        "kok_product_price": 15000,
        "kok_discount_rate": 20,
        "kok_discounted_price": 12000,
        "kok_product_image": "beef_500g.jpg",
        "kok_product_description": "신선한 국내산 소고기"
      },
      {
        "kok_product_id": 2,
        "kok_product_name": "양파 1kg",
        "kok_product_price": 3000,
        "kok_discount_rate": 15,
        "kok_discounted_price": 2550,
        "kok_product_image": "onion_1kg.jpg",
        "kok_product_description": "신선한 양파"
      }
    ]
  }
  ```

#### 1.2 인기 상품 조회
- **기능**: 판매율이 높은 상품 목록 조회
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/top-selling`
- **헤더**: Authorization: Bearer {token}
- **응답 예시**:
  ```json
  {
    "products": [
      {
        "kok_product_id": 3,
        "kok_product_name": "김치 1kg",
        "kok_product_price": 8000,
        "kok_sales_count": 150,
        "kok_product_image": "kimchi_1kg.jpg",
        "kok_product_description": "맛있는 김치"
      }
    ]
  }
  ```

#### 1.3 스토어 베스트 상품 조회
- **기능**: 사용자별 스토어 베스트 상품 목록 조회
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/store-best-items`
- **헤더**: Authorization: Bearer {token}
- **응답 예시**:
  ```json
  {
    "store_best_items": [
      {
        "kok_product_id": 4,
        "kok_product_name": "당근 500g",
        "kok_product_price": 2000,
        "kok_product_image": "carrot_500g.jpg",
        "kok_product_description": "신선한 당근"
      }
    ]
  }
  ```

#### 1.4 상품 기본 정보 조회
- **기능**: 상품의 기본 정보 조회 (상품명, 가격, 할인율 등)
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/product/{product_id}/basic-info`
- **헤더**: Authorization: Bearer {token}
- **응답 예시**:
  ```json
  {
    "kok_product_id": "1",
    "kok_product_name": "신선한 소고기 500g",
    "kok_store_name": "신선식품",
    "kok_thumbnail": "beef_500g.jpg",
    "kok_product_price": 15000,
    "kok_discount_rate": 20,
    "kok_discounted_price": 12000,
    "kok_review_cnt": 15
  }
  ```

#### 1.5 상품설명 탭 조회
- **기능**: 상품설명 탭에 표시할 이미지들 조회
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/product/{product_id}/tabs`
- **헤더**: Authorization: Bearer {token}
- **응답 예시**:
  ```json
  {
    "images": [
      {
        "kok_img_id": 1,
        "kok_img_url": "https://example.com/product_detail_1.jpg"
      },
      {
        "kok_img_id": 2,
        "kok_img_url": "https://example.com/product_detail_2.jpg"
      },
      {
        "kok_img_id": 3,
        "kok_img_url": "https://example.com/product_detail_3.jpg"
      }
    ]
  }
  ```

#### 1.6 상품 리뷰 조회
- **기능**: 상품의 리뷰 통계 정보와 개별 리뷰 목록 조회
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/product/{product_id}/reviews`
- **헤더**: Authorization: Bearer {token}
- **응답 예시**:
  ```json
  {
    "stats": {
      "kok_review_score": 4.5,
      "kok_review_cnt": 15,
      "kok_5_ratio": 60,
      "kok_4_ratio": 25,
      "kok_3_ratio": 10,
      "kok_2_ratio": 3,
      "kok_1_ratio": 2,
      "kok_aspect_price": 4.2,
      "kok_aspect_price_ratio": 85,
      "kok_aspect_delivery": 4.8,
      "kok_aspect_delivery_ratio": 92,
      "kok_aspect_quality": 4.6,
      "kok_aspect_quality_ratio": 88
    },
    "reviews": [
      {
        "kok_review_id": 1,
        "kok_review_score": 5,
        "kok_review_text": "정말 신선하고 맛있어요!",
        "kok_review_date": "2024-01-15",
        "kok_review_user": "김철수"
      },
      {
        "kok_review_id": 2,
        "kok_review_score": 4,
        "kok_review_text": "가격 대비 훌륭합니다.",
        "kok_review_date": "2024-01-14",
        "kok_review_user": "이영희"
      }
    ]
  }
  ```

#### 1.7 상품 판매자 정보 및 상세정보 조회
- **기능**: 상품의 **판매자 정보 및 상세정보**만 조회 (이미지, 리뷰 제외)
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/product/{product_id}/seller-details`
- **헤더**: Authorization: Bearer {token}
- **응답 예시**:
  ```json
  {
    "seller_info": {
      "kok_co_ceo": "신선식품",
      "kok_co_reg_no": "123-45-67890",
      "kok_co_ec_reg": "제2024-서울강남-1234호",
      "kok_tell": "02-1234-5678",
      "kok_ver_item": "HACCP, ISO22000",
      "kok_ver_date": "2024-01-01",
      "kok_co_addr": "서울시 강남구 테헤란로 123",
      "kok_return_addr": "서울시 강남구 테헤란로 123"
    },
    "detail_info": [
      {
        "kok_detail_col": "제품명",
        "kok_detail_val": "신선한 소고기 500g"
      },
      {
        "kok_detail_col": "원산지",
        "kok_detail_val": "국내산"
      },
      {
        "kok_detail_col": "보관방법",
        "kok_detail_val": "냉장보관"
      },
      {
        "kok_detail_col": "유통기한",
        "kok_detail_val": "제조일로부터 7일"
      }
    ]
  }
  ```

#### 1.8 상품 전체 상세 정보 조회
- **기능**: 상품의 **전체 상세 정보** 조회 (이미지, 리뷰, 가격 정보 등 모든 정보 포함)
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/product/{product_id}/full-detail`
- **헤더**: Authorization: Bearer {token}
- **응답 예시**:
  ```json
  {
    "kok_product_id": 1,
    "kok_product_name": "신선한 소고기 500g",
    "kok_product_price": 15000,
    "kok_product_description": "신선한 국내산 소고기",
    "kok_product_image": "beef_500g.jpg",
    "images": [
      {
        "kok_img_id": 1,
        "kok_img_url": "https://example.com/product_detail_1.jpg"
      }
    ],
    "detail_infos": [
      {
        "kok_detail_id": 1,
        "kok_detail_col": "제품명",
        "kok_detail_val": "신선한 소고기 500g"
      }
    ],
    "review_examples": [
      {
        "kok_review_id": 1,
        "kok_review_score": 5,
        "kok_review_text": "정말 신선하고 맛있어요!"
      }
    ],
    "price_infos": [
      {
        "kok_price_id": 1,
        "kok_discount_rate": 20,
        "kok_discounted_price": 12000
      }
    ]
  }
  ```

### 2. 장바구니 관련 API

#### 2.1 장바구니 상품 목록 조회
- **기능**: 사용자의 장바구니 상품 목록 조회
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/carts`
- **헤더**: Authorization: Bearer {token}
- **Query Parameter**: limit (기본값: 100)
- **응답 예시**:
  ```json
  {
    "cart_items": [
      {
        "kok_cart_id": 1,
        "kok_product_id": 1,
        "kok_product_name": "신선한 소고기 500g",
        "kok_product_price": 15000,
        "kok_quantity": 2,
        "kok_product_image": "beef_500g.jpg",
        "kok_discount_rate": 20,
        "kok_discounted_price": 12000,
        "total_price": 24000
      },
      {
        "kok_cart_id": 2,
        "kok_product_id": 3,
        "kok_product_name": "김치 1kg",
        "kok_product_price": 8000,
        "kok_quantity": 1,
        "kok_product_image": "kimchi_1kg.jpg",
        "kok_discount_rate": 0,
        "kok_discounted_price": 8000,
        "total_price": 8000
      }
    ],
    "total_items": 2,
    "total_amount": 32000
  }
  ```

#### 2.2 장바구니에 상품 추가
- **기능**: 장바구니에 상품 추가 (수량은 1개로 고정, 기존 상품이 있으면 추가하지 않음)
- **HTTP 메서드**: POST
- **엔드포인트**: `/api/kok/carts`
- **헤더**: Authorization: Bearer {token}
- **요청 Body 예시**:
  ```json
  {
    "kok_product_id": 1,
    "kok_quantity": 1
  }
  ```
  > **참고**: `kok_quantity` 필드는 요청에 포함되지만 항상 1개로 고정됩니다.
- **응답 예시 (새로 추가된 경우)**:
  ```json
  {
    "kok_cart_id": 3,
    "message": "장바구니에 추가되었습니다."
  }
  ```
- **응답 예시 (이미 있는 경우)**:
  ```json
  {
    "kok_cart_id": 1,
    "message": "이미 장바구니에 있습니다."
  }
  ```



#### 2.3 장바구니 상품 수량 토글
- **기능**: 장바구니 상품의 수량을 1-10 사이의 특정 수량으로 설정
- **HTTP 메서드**: POST
- **엔드포인트**: `/api/kok/carts/{cart_item_id}/quantity-toggle?quantity={수량}`
- **헤더**: Authorization: Bearer {token}
- **Query Parameter**: quantity (1-10 사이의 정수)
- **요청 예시**: `POST /api/kok/carts/1/quantity-toggle?quantity=5`
- **응답 예시**:
  ```json
  {
    "kok_cart_id": 1,
    "kok_quantity": 5,
    "message": "수량이 5개로 변경되었습니다."
  }
  ```
- **에러 응답** (수량이 1-10 범위를 벗어난 경우):
  ```json
  {
    "detail": "수량은 1-10 사이여야 합니다."
  }
  ```

#### 2.4 장바구니 상품 삭제
- **기능**: 장바구니에서 상품 삭제
- **HTTP 메서드**: DELETE
- **엔드포인트**: `/api/kok/carts/{cart_item_id}`
- **헤더**: Authorization: Bearer {token}
- **응답 예시**:
  ```json
  {
    "message": "장바구니에서 삭제되었습니다.",
    "deleted_cart_id": 1
  }
  ```

### 3. 주문 관련 API

#### 3.1 선택된 상품들로 주문 생성
- **기능**: 프론트엔드에서 선택된 상품들과 수량으로 주문 생성
- **HTTP 메서드**: POST
- **엔드포인트**: `/api/kok/carts/order`
- **헤더**: Authorization: Bearer {token}
- **요청 Body 예시**:
  ```json
  {
    "selected_items": [
      {
        "cart_id": 1,
        "quantity": 2
      },
      {
        "cart_id": 3,
        "quantity": 1
      },
      {
        "cart_id": 5,
        "quantity": 3
      }
    ]
  }
  ```
- **응답 예시**:
  ```json
  {
    "order_id": 12345,
    "total_amount": 63700,
    "order_count": 3,
    "order_details": [
      {
        "kok_order_id": 1,
        "kok_product_id": 1,
        "kok_product_name": "신선한 소고기 500g",
        "quantity": 2,
        "unit_price": 12000,
        "total_price": 24000
      },
      {
        "kok_order_id": 2,
        "kok_product_id": 3,
        "kok_product_name": "김치 1kg",
        "quantity": 1,
        "unit_price": 8000,
        "total_price": 8000
      },
      {
        "kok_order_id": 3,
        "kok_product_id": 5,
        "kok_product_name": "양파 1kg",
        "quantity": 3,
        "unit_price": 3000,
        "total_price": 9000
      }
    ],
    "message": "3개의 상품이 주문되었습니다.",
    "order_time": "2024-01-15T10:30:00"
  }
  ```

### 4. 레시피 추천 API

#### 4.1 선택된 상품들로 레시피 추천
- **기능**: 선택된 장바구니 상품들의 재료로 레시피 추천
- **HTTP 메서드**: POST
- **엔드포인트**: `/api/kok/carts/recipe-recommend`
- **헤더**: Authorization: Bearer {token}
- **요청 Body 예시**:
  ```json
  {
    "selected_cart_ids": [1, 3, 5],
    "page": 1,
    "size": 5
  }
  ```
- **응답 예시**:
  ```json
  {
    "recipes": [
      {
        "recipe_id": 1,
        "title": "소고기 김치찌개",
        "ingredients": ["소고기", "김치", "양파", "대파"],
        "instructions": [
          "1. 소고기를 적당한 크기로 썰어주세요.",
          "2. 김치를 썰어주세요.",
          "3. 양파와 대파를 썰어주세요.",
          "4. 냄비에 기름을 두르고 소고기를 볶아주세요.",
          "5. 김치를 넣고 볶아주세요.",
          "6. 물을 넣고 끓여주세요.",
          "7. 양파와 대파를 넣고 끓여주세요."
        ],
        "cooking_time": "30분",
        "difficulty": "보통",
        "servings": 2,
        "image_url": "beef_kimchi_stew.jpg",
        "rating": 4.8,
        "review_count": 125
      },
      {
        "recipe_id": 2,
        "title": "소고기 양파볶음",
        "ingredients": ["소고기", "양파", "간장", "설탕"],
        "instructions": [
          "1. 소고기를 얇게 썰어주세요.",
          "2. 양파를 채썰어주세요.",
          "3. 간장, 설탕으로 양념장을 만들어주세요.",
          "4. 팬에 기름을 두르고 소고기를 볶아주세요.",
          "5. 양파를 넣고 볶아주세요.",
          "6. 양념장을 넣고 볶아주세요."
        ],
        "cooking_time": "20분",
        "difficulty": "쉬움",
        "servings": 1,
        "image_url": "beef_onion_stirfry.jpg",
        "rating": 4.5,
        "review_count": 89
      }
    ],
    "page": 1,
    "size": 5,
    "total": 10,
    "ingredients_used": ["소고기", "김치", "양파"],
    "total_pages": 2
  }
  ```

### 5. 검색 관련 API

#### 5.1 상품 검색
- **기능**: 키워드로 상품 검색
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/search`
- **헤더**: Authorization: Bearer {token}
- **Query Parameter**: 
  - keyword (필수): 검색 키워드
  - page (기본값: 1): 페이지 번호
  - size (기본값: 20): 페이지 크기
- **응답 예시**:
  ```json
  {
    "products": [
      {
        "kok_product_id": 1,
        "kok_product_name": "신선한 소고기 500g",
        "kok_product_price": 15000,
        "kok_product_image": "beef_500g.jpg",
        "kok_discount_rate": 20,
        "kok_discounted_price": 12000
      },
      {
        "kok_product_id": 6,
        "kok_product_name": "소고기 다짐육 300g",
        "kok_product_price": 12000,
        "kok_product_image": "beef_minced_300g.jpg",
        "kok_discount_rate": 0,
        "kok_discounted_price": 12000
      }
    ],
    "total": 2,
    "page": 1,
    "size": 20,
    "keyword": "소고기"
  }
  ```

#### 5.2 검색 이력 조회
- **기능**: 사용자의 검색 이력 조회
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/search/history`
- **헤더**: Authorization: Bearer {token}
- **Query Parameter**: limit (기본값: 10)
- **응답 예시**:
  ```json
  {
    "search_history": [
      {
        "search_history_id": 1,
        "keyword": "소고기",
        "search_date": "2024-01-15T10:30:00"
      },
      {
        "search_history_id": 2,
        "keyword": "김치",
        "search_date": "2024-01-14T15:20:00"
      }
    ],
    "total": 2
  }
  ```

#### 5.3 검색 이력 추가
- **기능**: 검색 이력 추가
- **HTTP 메서드**: POST
- **엔드포인트**: `/api/kok/search/history`
- **헤더**: Authorization: Bearer {token}
- **요청 Body 예시**:
  ```json
  {
    "keyword": "소고기"
  }
  ```
- **응답 예시**:
  ```json
  {
    "search_history_id": 3,
    "keyword": "소고기",
    "search_date": "2024-01-15T10:30:00",
    "message": "검색 이력이 추가되었습니다."
  }
  ```

#### 5.4 검색 이력 삭제
- **기능**: 특정 검색 이력 삭제
- **HTTP 메서드**: DELETE
- **엔드포인트**: `/api/kok/search/history/{history_id}`
- **헤더**: Authorization: Bearer {token}
- **응답 예시**:
  ```json
  {
    "message": "검색 이력이 삭제되었습니다.",
    "deleted_history_id": 1
  }
  ```

### 6. 찜 관련 API

#### 6.1 찜 등록/해제
- **기능**: 상품 찜 등록 또는 해제
- **HTTP 메서드**: POST
- **엔드포인트**: `/api/kok/likes/toggle`
- **헤더**: Authorization: Bearer {token}
- **요청 Body 예시**:
  ```json
  {
    "kok_product_id": 123
  }
  ```
- **응답 예시 (찜 등록)**:
  ```json
  {
    "liked": true,
    "message": "찜이 등록되었습니다.",
    "product_id": 123
  }
  ```
- **응답 예시 (찜 해제)**:
  ```json
  {
    "liked": false,
    "message": "찜이 해제되었습니다.",
    "product_id": 123
  }
  ```

#### 6.2 찜한 상품 목록 조회
- **기능**: 사용자가 찜한 상품 목록 조회
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/likes`
- **헤더**: Authorization: Bearer {token}
- **Query Parameter**: limit (기본값: 50)
- **응답 예시**:
  ```json
  {
    "liked_products": [
      {
        "kok_product_id": 1,
        "kok_product_name": "신선한 소고기 500g",
        "kok_product_price": 15000,
        "kok_product_image": "beef_500g.jpg",
        "kok_discount_rate": 20,
        "kok_discounted_price": 12000,
        "like_date": "2024-01-15T10:30:00"
      },
      {
        "kok_product_id": 3,
        "kok_product_name": "김치 1kg",
        "kok_product_price": 8000,
        "kok_product_image": "kimchi_1kg.jpg",
        "kok_discount_rate": 0,
        "kok_discounted_price": 8000,
        "like_date": "2024-01-14T15:20:00"
      }
    ],
    "total": 2
  }
  ```

### 7. 알림 관련 API

#### 7.1 알림 목록 조회
- **기능**: 사용자의 알림 목록 조회
- **HTTP 메서드**: GET
- **엔드포인트**: `/api/kok/notifications`
- **헤더**: Authorization: Bearer {token}
- **Query Parameter**: limit (기본값: 50)
- **응답 예시**:
  ```json
  {
    "notifications": [
      {
        "notification_id": 1,
        "notification_type": "order_status",
        "title": "주문 상태 변경",
        "message": "주문번호 12345의 배송이 시작되었습니다.",
        "is_read": false,
        "created_at": "2024-01-15T10:30:00"
      },
      {
        "notification_id": 2,
        "notification_type": "discount",
        "title": "할인 알림",
        "message": "소고기 상품이 20% 할인 중입니다!",
        "is_read": true,
        "created_at": "2024-01-14T15:20:00"
      }
    ],
    "total": 2,
    "unread_count": 1
  }
  ```

## 데이터 모델

### KokCartOrderItem
```json
{
  "cart_id": 1,
  "quantity": 2
}
```

### KokCartOrderRequest
```json
{
  "selected_items": [
    {
      "cart_id": 1,
      "quantity": 2
    },
    {
      "cart_id": 3,
      "quantity": 1
    }
  ]
}
```

### KokCartOrderResponse
```json
{
  "order_id": 12345,
  "total_amount": 63700,
  "order_count": 2,
  "message": "2개의 상품이 주문되었습니다."
}
```

## 사용 예시

### 장바구니에서 주문하기
1. 프론트엔드에서 장바구니 상품들을 선택/해제
2. 각 상품의 수량을 조정
3. 주문하기 버튼 클릭 시 선택된 상품들과 수량을 백엔드로 전송
4. 백엔드에서 동일한 주문 ID로 여러 상품 주문 생성

### 레시피 추천
1. 장바구니에서 상품들을 선택
2. 레시피 추천 버튼 클릭 시 선택된 상품 ID들을 백엔드로 전송
3. 백엔드에서 상품명에서 재료명을 추출하여 레시피 추천

## 주의사항
- 모든 API는 JWT 토큰 인증이 필요합니다
- 장바구니 상품 선택/해제와 수량 조정은 프론트엔드에서 처리됩니다
- 장바구니에 이미 있는 상품을 다시 추가하면 수량이 증가하지 않고 "이미 장바구니에 있습니다" 메시지가 반환됩니다
- 주문 시에는 선택된 상품들과 수량을 함께 전송해야 합니다
- 레시피 추천은 상품명에서 재료명을 추출하여 처리됩니다
