# 홈쇼핑 통합 알림 시스템 (기존 테이블 활용)

## 개요
홈쇼핑 주문 상태 변경 알림과 방송 시작 알림을 통합 관리하는 시스템입니다. 기존 `HOMESHOPPING_NOTIFICATION` 테이블을 수정하여 두 가지 타입의 알림을 모두 지원합니다.

## 🎯 주요 특징

### 1. **기존 테이블 활용**
- `HOMESHOPPING_NOTIFICATION` 테이블을 수정하여 방송 찜과 주문 상태 변경 알림을 모두 지원
- 별도의 알림 테이블 생성 불필요
- 기존 데이터와의 호환성 유지

### 2. **자동 알림 생성**
- 상품 찜 시 자동으로 방송 시작 알림 레코드 생성
- 찜 해제 시 자동으로 방송 알림 레코드 삭제
- 주문 상태 변경 시 자동으로 주문 알림 레코드 생성

### 3. **유연한 조회 옵션**
- 주문 알림만 조회
- 방송 알림만 조회
- 모든 알림 통합 조회
- 읽음 여부별 필터링

## 🗄️ 데이터베이스 구조

### **수정된 HOMESHOPPING_NOTIFICATION 테이블**

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `NOTIFICATION_ID` | BIGINT | 알림 고유번호 (PK) | 1, 2, 3... |
| `USER_ID` | INT | 사용자 ID | 123 |
| `NOTIFICATION_TYPE` | VARCHAR(50) | 알림 타입 | "broadcast_start", "order_status" |
| `RELATED_ENTITY_TYPE` | VARCHAR(50) | 관련 엔티티 타입 | "product", "order" |
| `RELATED_ENTITY_ID` | BIGINT | 관련 엔티티 ID | 제품 ID 또는 주문 ID |
| `HOMESHOPPING_LIKE_ID` | INT | 관련 찜 ID (방송 알림) | NULL 또는 찜 ID |
| `HOMESHOPPING_ORDER_ID` | INT | 관련 주문 ID (주문 알림) | NULL 또는 주문 ID |
| `STATUS_ID` | INT | 상태 ID (주문 알림) | NULL 또는 상태 ID |
| `TITLE` | VARCHAR(100) | 알림 제목 | "상품명 방송 시작 알림" |
| `MESSAGE` | VARCHAR(255) | 알림 메시지 | "방송 시작 시간 안내" |
| `IS_READ` | SMALLINT | 읽음 여부 | 0: 안읽음, 1: 읽음 |
| `CREATED_AT` | DATETIME | 생성 시각 | 2024-01-15 10:30:00 |
| `READ_AT` | DATETIME | 읽음 처리 시각 | NULL 또는 읽음 시각 |

## 🚀 API 엔드포인트

### **1. 주문 알림만 조회**
```
GET /api/homeshopping/notifications/orders
```
- 주문 상태 변경 알림만 조회
- 페이지네이션 지원 (limit, offset)

### **2. 방송 알림만 조회**
```
GET /api/homeshopping/notifications/broadcasts
```
- 방송 시작 알림만 조회
- 페이지네이션 지원 (limit, offset)

### **3. 모든 알림 통합 조회**
```
GET /api/homeshopping/notifications/all
```
- 주문 알림과 방송 알림을 시간순으로 통합 조회
- 페이지네이션 지원 (limit, offset)
- `has_more` 필드로 더 많은 알림 존재 여부 표시

### **4. 알림 읽음 처리**
```
PUT /api/homeshopping/notifications/{notification_id}/read
```
- 특정 알림을 읽음으로 표시
- `read_at` 필드에 현재 시각 기록

## 📊 응답 데이터 구조

### **알림 응답**
```json
{
  "notifications": [
    {
      "notification_id": 123,
      "user_id": 456,
      "notification_type": "broadcast_start",
      "related_entity_type": "product",
      "related_entity_id": 789,
      "homeshopping_like_id": 101,
      "homeshopping_order_id": null,
      "status_id": null,
      "title": "신선한 채소 세트 방송 시작 알림",
      "message": "2024-01-15 20:00:00에 방송이 시작됩니다.",
      "is_read": false,
      "created_at": "2024-01-14T15:00:00",
      "read_at": null
    }
  ],
  "total_count": 25,
  "has_more": true
}
```

## ⚙️ 자동 알림 생성 로직

### **1. 방송 찜 알림**
- **생성 시점**: `toggle_homeshopping_likes` API 호출 시
- **조건**: 상품을 찜하고, 해당 상품에 방송 정보가 있는 경우
- **자동 삭제**: 찜 해제 시 자동으로 관련 알림도 삭제

### **2. 주문 상태 변경 알림**
- **생성 시점**: 주문 상태 변경 시 (별도 트리거 또는 API 호출)
- **조건**: `HOMESHOPPING_ORDER_STATUS_HISTORY` 테이블에 새 레코드 생성 시
- **수동 생성**: `create_order_status_notification` 함수 호출 필요

## 🔧 구현 세부사항

### **1. 찜 토글 시 자동 처리**
```python
# 찜 등록 시
if not existing_like:
    # 찜 레코드 생성
    new_like = HomeshoppingLikes(...)
    
    # 방송 정보 조회하여 알림 생성
    if live_info:
        await create_broadcast_notification(...)

# 찜 해제 시
if existing_like:
    # 방송 알림도 함께 삭제
    await delete_broadcast_notification(...)
    
    # 찜 레코드 삭제
    await db.delete(existing_like)
```

### **2. 주문 상태 변경 알림 생성**
```python
# 주문 상태 변경 시 호출
await create_order_status_notification(
    db=db,
    user_id=user_id,
    homeshopping_order_id=order_id,
    status_id=status_id,
    status_name=status_name,
    order_id=order_id
)
```

### **3. 알림 조회 및 필터링**
```python
# 주문 알림만 조회
notifications = await get_notifications_with_filter(
    db, user_id, 
    notification_type="order_status"
)

# 방송 알림만 조회
notifications = await get_notifications_with_filter(
    db, user_id, 
    notification_type="broadcast_start"
)

# 모든 알림 조회
notifications = await get_notifications_with_filter(db, user_id)
```

## 📈 성능 최적화

### **1. 인덱스 활용**
- `USER_ID + NOTIFICATION_TYPE`: 사용자별 알림 타입별 조회
- `RELATED_ENTITY_TYPE + RELATED_ENTITY_ID`: 엔티티별 조회
- `CREATED_AT`: 시간순 정렬
- `IS_READ`: 읽음 여부별 필터링

### **2. 조인 최적화**
- 필요한 테이블만 조인
- 페이지네이션을 통한 결과 제한

## 🚨 주의사항

### **1. 데이터 일관성**
- 찜 해제 시 반드시 관련 방송 알림도 함께 삭제
- 주문 상태 변경 시 반드시 알림 생성 함수 호출
- 트랜잭션 처리로 데이터 일관성 보장

### **2. 마이그레이션**
- 기존 데이터가 있는 경우 마이그레이션 실행 필요
- 기존 알림은 `order_status` 타입으로 자동 설정
- `RELATED_ENTITY_ID`는 기존 `HOMESHOPPING_ORDER_ID` 값으로 설정

## 🔮 향후 개선 사항

### **1. 알림 설정 개선**
- 사용자별 알림 타입별 수신 여부 설정
- 알림 시간대 설정 (방송 시작 10분 전, 1시간 전 등)

### **2. 알림 채널 확장**
- 푸시 알림 (FCM, APNS)
- 이메일 알림
- SMS 알림

### **3. 고급 기능**
- 알림 그룹화 (같은 시간대 방송 알림 묶기)
- 알림 우선순위 설정
- 알림 템플릿 커스터마이징

## 📝 사용 예시

### **1. 모든 알림 통합 조회**
```bash
curl -X GET "http://localhost:8000/api/homeshopping/notifications/all?limit=20&offset=0" \
  -H "Authorization: Bearer {token}"
```

### **2. 주문 알림만 조회**
```bash
curl -X GET "http://localhost:8000/api/homeshopping/notifications/orders?limit=10" \
  -H "Authorization: Bearer {token}"
```

### **3. 방송 알림만 조회**
```bash
curl -X GET "http://localhost:8000/api/homeshopping/notifications/broadcasts?limit=10" \
  -H "Authorization: Bearer {token}"
```

### **4. 알림 읽음 처리**
```bash
curl -X PUT "http://localhost:8000/api/homeshopping/notifications/123/read" \
  -H "Authorization: Bearer {token}"
```

### **5. 상품 찜하여 방송 알림 자동 등록**
```bash
curl -X POST "http://localhost:8000/api/homeshopping/likes/toggle" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 12345}'
```

## 🎉 장점 요약

1. **기존 테이블 활용**: 새로운 테이블 생성 불필요
2. **자동 알림 관리**: 찜 등록/해제 시 자동으로 알림 생성/삭제
3. **데이터 일관성**: 트랜잭션 처리로 데이터 무결성 보장
4. **유연한 조회**: 타입별 개별 조회 또는 통합 조회 가능
5. **확장성**: 새로운 알림 타입 추가 시 스키마 변경 불필요
6. **성능 최적화**: 인덱스와 페이지네이션으로 효율적인 조회

## 🚀 마이그레이션 실행

```bash
# 마이그레이션 실행
alembic upgrade head

# 마이그레이션 상태 확인
alembic current

# 롤백 (필요시)
alembic downgrade -1
```
