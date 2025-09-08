# syntax=docker/dockerfile:1.7

############################################
# 1) Builder: 의존성 빌드/컴파일 전용
############################################
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 빌드 전용 툴/헤더(최종 이미지에는 안 들어감)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ \
    libmariadb-dev libpq-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 먼저 복사 → 레이어 캐시 최대 활용
COPY requirements.txt ./

# BuildKit 캐시로 빠른 재빌드 + 런타임 복사용 경로(/install)에 설치
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

############################################
# 2) Runtime: 경량 실행 전용
############################################
FROM python:3.11-slim AS runtime

# 런타임에 필요한 최소 라이브러리만 설치
# - libmariadb3: MariaDB 클라이언트 런타임
# - libpq5: PostgreSQL 클라이언트 런타임
# - curl: HEALTHCHECK에서 사용
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 libpq5 curl \
  && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# 빌더에서 준비한 site-packages만 복사(빌드 툴은 제외됨)
COPY --from=builder /install /usr/local

# 애플리케이션 소스만 복사
COPY . .

# 비루트 유저 권장
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# 포트 노출 (FastAPI)
EXPOSE 9000

# 헬스체크 (curl 사용 가능)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -sf http://localhost:9000/api/health || exit 1

# 애플리케이션 실행
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "9000"]
