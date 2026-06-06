# DB 레벨 동시성 제어 — SELECT FOR UPDATE & SERIALIZABLE

## 배경

웹훅 기반 결제 구조 전환 이후, 동시 요청에 의한 DB 레벨 race condition이 잠재적 취약점으로 식별됨.
애플리케이션 레벨의 `asyncio.Lock`은 인메모리 자료구조(웹훅 브리지)를 보호하지만,
DB 레코드에 대한 동시 접근은 별도의 DB 레벨 제어가 필요함.

---

## 1. 장바구니 주문 생성 — SELECT FOR UPDATE

### 문제

사용자가 동일한 장바구니 항목으로 중복 주문 요청을 보내는 경우
(빠른 연속 클릭, 네트워크 재시도 등):

```
요청 A: SELECT KokCart WHERE cart_id=1  → 존재함 확인
요청 B: SELECT KokCart WHERE cart_id=1  → 존재함 확인
요청 A: Order 생성, KokOrder 생성, Cart 삭제
요청 B: Order 생성, KokOrder 생성, Cart 삭제  ← 동일 장바구니로 중복 주문 생성
```

### 해결

`SELECT ... FOR UPDATE`로 장바구니 row 조회 시점에 DB 레벨 락을 획득.

```
요청 A: SELECT KokCart FOR UPDATE  → 락 획득
요청 B: SELECT KokCart FOR UPDATE  → 요청 A 완료까지 대기
요청 A: Order 생성, Cart 삭제, COMMIT → 락 해제
요청 B: SELECT 재실행 → Cart 없음 → 에러 반환
```

### 적용 위치

`services/order/crud/kok/kok_order_create_crud.py` — `create_orders_from_selected_carts`

```python
stmt = (
    select(KokCart, KokProductInfo)
    .join(...)
    .where(KokCart.kok_cart_id.in_(kok_cart_ids))
    .where(KokCart.user_id == user_id)
    .with_for_update()          # 추가
)
```

---

## 2. 결제 상태 변경 — SERIALIZABLE

### 문제

결제 서버가 네트워크 불안정 등으로 동일한 웹훅을 두 번 전송하는 경우,
두 요청이 동시에 처리되면:

```
웹훅 A: 주문 상태 조회 → PAYMENT_REQUESTED
웹훅 B: 주문 상태 조회 → PAYMENT_REQUESTED
웹훅 A: PAYMENT_COMPLETED로 변경, StatusHistory 삽입
웹훅 B: PAYMENT_COMPLETED로 변경, StatusHistory 삽입  ← 상태 이력 중복 삽입
```

MariaDB 기본 격리 수준인 REPEATABLE READ는 같은 row의 반복 읽기는 보장하지만,
다른 트랜잭션이 INSERT한 새 row(팬텀 리드)는 차단하지 못함.

### 해결

`SERIALIZABLE` 격리 수준은 트랜잭션을 순차 실행처럼 처리해,
웹훅 B가 반드시 웹훅 A의 커밋 결과를 보도록 강제.

```
웹훅 A: 트랜잭션 시작 (SERIALIZABLE)
웹훅 B: 트랜잭션 시작 (SERIALIZABLE) → 웹훅 A와 충돌 감지 → 대기 또는 rollback
웹훅 A: PAYMENT_COMPLETED 변경, COMMIT
웹훅 B: 재실행 → 이미 PAYMENT_COMPLETED → 중복 처리 없이 종료
```

### 적용 위치

`services/order/crud/payment_v2_crud.py` — `apply_payment_webhook_v2`

```python
# payment.completed — 결제 완료 상태 반영 전
await db.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
await _mark_all_children_payment_completed(...)

# payment.failed / payment.cancelled — 주문 취소 전
await db.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
await cancel_order(...)
```

`services/order/crud/kok/kok_order_create_crud.py` — `create_orders_from_selected_carts`

```python
# 주문 생성 시작 전
await db.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
```

### 주의사항

`SET TRANSACTION ISOLATION LEVEL`은 MariaDB에서 트랜잭션 시작 전에만 유효.
SQLAlchemy `autocommit=False` 환경에서 앞선 조회 쿼리가 있는 경우
이미 트랜잭션이 시작된 상태이므로 실제 적용되지 않을 수 있음.
완전한 적용을 위해서는 엔진 레벨 `isolation_level` 설정 또는 `connection.execution_options()` 사용 권장.

---

## 격리 수준 비교 요약

| 격리 수준 | Dirty Read | Non-Repeatable Read | Phantom Read |
|---|---|---|---|
| READ COMMITTED | 방지 | 발생 가능 | 발생 가능 |
| REPEATABLE READ (MariaDB 기본) | 방지 | 방지 | 발생 가능 |
| SERIALIZABLE | 방지 | 방지 | 방지 |

---

## 관련 파일

| 파일 | 적용 내용 |
|---|---|
| `services/kok/crud/likes_crud.py` | `toggle_kok_likes` — FOR UPDATE |
| `services/homeshopping/crud/likes_crud.py` | `toggle_homeshopping_likes` — FOR UPDATE |
| `services/order/crud/kok/kok_order_create_crud.py` | `create_orders_from_selected_carts` — FOR UPDATE + SERIALIZABLE |
| `services/order/crud/payment_v2_crud.py` | `apply_payment_webhook_v2` — SERIALIZABLE 3곳 |
| `tests/test_acid_fixes.py` | 위 변경사항 단위 테스트 (8개) |
