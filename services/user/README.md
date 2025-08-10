# User Service

사용자 관리 서비스 (회원가입, 로그인, 로그아웃)

## 주요 기능

### 1. 회원가입
- 이메일 중복 체크
- 사용자 계정 생성
- 사용자 설정 초기화

### 2. 로그인
- 이메일/비밀번호 인증
- JWT 액세스 토큰 발급
- 로그인 로그 기록

### 3. 로그아웃
- JWT 토큰을 블랙리스트에 추가
- 토큰 재사용 방지
- 로그아웃 로그 기록

### 4. 사용자 정보 조회
- JWT 토큰 기반 인증
- 사용자 기본 정보 반환

## API 엔드포인트

### 인증 관련
- `POST /api/user/signup` - 회원가입
- `GET /api/user/signup/email/check` - 이메일 중복 확인
- `POST /api/user/login` - 로그인
- `POST /api/user/logout` - 로그아웃
- `POST /api/user/logout/all` - 모든 디바이스에서 로그아웃

### 사용자 정보
- `GET /api/user/info` - 사용자 정보 조회

### 관리자 기능
- `GET /api/user/admin/blacklist/stats` - 블랙리스트 통계 조회
- `POST /api/user/admin/blacklist/cleanup` - 만료된 토큰 정리

## 보안 기능

### JWT 블랙리스트
- 로그아웃된 토큰을 데이터베이스에 저장
- 토큰 재사용 시도 시 자동 차단
- 만료된 토큰 자동 정리

### 토큰 검증
- 모든 보호된 엔드포인트에서 블랙리스트 확인
- 유효하지 않은 토큰 자동 거부

## 데이터베이스 스키마

### JWT Blacklist Table
```sql
CREATE TABLE jwt_blacklist (
    token_hash VARCHAR(255) PRIMARY KEY,
    blacklisted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    user_id VARCHAR(36),
    metadata TEXT,
    INDEX ix_jwt_blacklist_token_hash (token_hash),
    INDEX ix_jwt_blacklist_user_id (user_id),
    INDEX ix_jwt_blacklist_expires_at (expires_at)
);
```

## 사용 예시

### 로그아웃
```bash
curl -X POST "http://localhost:8000/api/user/logout" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 블랙리스트 통계 조회
```bash
curl -X GET "http://localhost:8000/api/user/admin/blacklist/stats" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 주의사항

1. **토큰 보안**: JWT 토큰은 클라이언트에서 안전하게 저장해야 합니다.
2. **블랙리스트 크기**: 만료된 토큰은 정기적으로 정리해야 합니다.
3. **권한 관리**: 관리자 기능은 향후 권한 시스템과 연동 예정입니다.
