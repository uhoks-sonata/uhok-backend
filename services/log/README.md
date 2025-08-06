# services/log/README.md

## 📦 목적
- **USER_LOG** (사용자 행동 로그) 테이블 관리 및 로그 적재/조회 API 제공
- 서비스 내 유저 행동, 비즈니스 이벤트를 일관성 있게 기록하여
  - 사용자 분석, 추천, 마케팅, 통계, 모니터링, 장애 추적 등에 활용

---

## 🏗️ 주요 파일 구조

| 파일명             | 설명                                   |
|--------------------|----------------------------------------|
| models/log_model.py| USER_LOG 테이블(ORM) 모델               |
| schemas/log_schema.py | 로그 요청/응답용 Pydantic 스키마      |
| crud/log_crud.py   | 로그 DB 적재/조회 함수                  |
| routers/log_router.py | 로그 적재/조회 API 엔드포인트        |

---

## 📝 event_type 설계 가이드

- **영문 소문자 + 밑줄(snake_case)**  
  ex) `order_create`, `login`, `cart_add`
- **액션 중심, 성공/실패 명확 구분**  
  ex) `order_create`, `order_fail`, `payment_success`, `payment_fail`
- **같은 행동이면 같은 event_type 사용** (서비스 전반 일관성)
- **상세 정보는 event_data(JSON)에 분리**
- **전체 규칙은 최상위 event_type 설계 가이드 참고**

#### 대표 event_type 예시

| 카테고리 | event_type        | 설명         |
|----------|------------------|--------------|
| 회원     | signup           | 회원가입     |
| 회원     | login            | 로그인       |
| 회원     | logout           | 로그아웃     |
| 주문     | order_create     | 주문 생성    |
| 주문     | order_cancel     | 주문 취소    |
| 주문     | order_fail       | 주문 실패    |
| 결제     | payment_success  | 결제 성공   |
| 결제     | payment_fail     | 결제 실패   |
| 장바구니 | cart_add         | 장바구니 담기|
| 장바구니 | cart_remove      | 장바구니 삭제|
| 검색     | search           | 상품/레시피 검색|
| 상품     | product_view     | 상품 상세 진입|
| 리뷰     | review_write     | 상품 리뷰 작성|
| 기타     | error            | 시스템/기능 에러|

---

## 📚 API 엔드포인트 요약

| 메서드 | 경로                        | 설명                 |
|--------|-----------------------------|----------------------|
| POST   | `/log/`                     | 로그 적재            |
| GET    | `/log/user/{user_id}`       | 특정 사용자 로그 조회 |

- [POST] /log/
    - Body 예시:
        ```json
        {
          "user_id": 101,
          "event_type": "order_create",
          "event_data": {
            "order_id": 12345,
            "amount": 25000
          }
        }
        ```
- [GET] /log/user/{user_id}
    - 쿼리: `user_id` (ex. 101)
    - 응답: 해당 사용자의 최신 로그 리스트

---

## 🛠️ 개발/운영 팁

- **모든 서비스(주문, 장바구니, 검색 등)에서 BackgroundTasks 등으로 로그 적재 권장**
- **event_type은 반드시 공통 룰 문서 참고 후 사용/추가**
- **Kafka, 대용량 분석 연동 시 확장 용이하게 설계**
- **USER_ID는 MariaDB(USERS 테이블)의 USER_ID와 동일 값**

---

## 🛠️ TODO / 개선 방향

- Kafka 등 이벤트 스트림 연동시 구조 업데이트
- event_type 정기 리뷰/관리
- event_data 필드 스키마 표준화 검토

---

## 📖 참고

- event_type/설계 룰 문서: `/docs/event_type_guide.md` 또는 최상위 가이드 참고
- 서비스 운영/배포 환경에 따라 `.env`의 LOG_API_URL 값 조정
- 장애, DB, 서비스 로그는 common/logger.py 사용

---

> **이 디렉터리의 모든 코드는 실서비스의 사용자 행동 로그 기록 및 분석을 목적으로 하며,
> 개발/운영/분석팀 모두가 공동 관리, 확장, 개선하는 것을 원칙으로 합니다.**
