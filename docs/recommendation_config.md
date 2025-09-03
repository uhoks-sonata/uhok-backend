# 추천 시스템 설정 가이드

## 환경 변수 설정

추천 시스템의 동작을 제어하는 환경 변수들을 설정할 수 있습니다.

### 기본 설정 (선택사항)

프로젝트 루트에 `.env` 파일을 생성하고 다음 변수들을 설정하세요:

```bash
# 추천 시스템 동적 파라미터
DYN_MAX_TERMS=32          # n-gram 최대 용어 수
DYN_MAX_EXTRAS=20         # 추가 키워드 최대 수
DYN_SAMPLE_ROWS=4000      # 샘플링 행 수

# Tail / n-gram 필터 동작 파라미터
TAIL_MAX_DF_RATIO=0.35    # 희소 토큰 판정 기준 (문서비율 ≤ 0.35)
TAIL_MAX_TERMS=3          # tail 후보로 쓸 최대 토큰 수
NGRAM_N=2                 # n-gram 기본값 (bi-gram)

# n-gram 생성 범위
DYN_NGRAM_MIN=2           # 최소 n-gram 길이
DYN_NGRAM_MAX=4           # 최대 n-gram 길이

# 카운트 범위
DYN_COUNT_MIN=3           # 최소 카운트
DYN_COUNT_MAX=30000       # 최대 카운트

# 스토어명 비교 옵션
GATE_COMPARE_STORE=false  # true/false (스토어명도 검색에 포함할지)

# 리랭크 모드
RERANK_MODE=off           # off/boost/strict

# 사전 파일 경로 (선택사항)
CATEGORY_DICT_PATH=       # 카테고리 사전 YAML 파일 경로
KEYWORDS_DICT_PATH=       # 키워드 사전 YAML 파일 경로
```

### 환경 변수별 상세 설명

#### 1. 동적 파라미터
- **DYN_MAX_TERMS**: n-gram을 통한 용어 추론 시 최대 용어 수
- **DYN_MAX_EXTRAS**: 추가 키워드 확장 시 최대 수
- **DYN_SAMPLE_ROWS**: 대용량 데이터 처리 시 샘플링 행 수

#### 2. 필터 동작 파라미터
- **TAIL_MAX_DF_RATIO**: 희소 토큰을 판정하는 기준값 (0.35 = 35% 이하)
- **TAIL_MAX_TERMS**: tail 키워드로 사용할 최대 토큰 수
- **NGRAM_N**: n-gram 겹침 계산 시 사용할 기본 n값

#### 3. n-gram 생성 범위
- **DYN_NGRAM_MIN**: 생성할 n-gram의 최소 길이
- **DYN_NGRAM_MAX**: 생성할 n-gram의 최대 길이

#### 4. 스토어명 비교 옵션
- **GATE_COMPARE_STORE**: 
  - `false`: 상품명만으로 검색
  - `true`: 상품명 + 스토어명으로 검색

#### 5. 리랭크 모드
- **RERANK_MODE**:
  - `off`: 기본 거리 정렬만 사용
  - `boost`: 부스팅 기반 리랭크
  - `strict`: 엄격한 리랭크

### 사전 파일 설정 (고급 기능)

#### 카테고리 사전 (CATEGORY_DICT_PATH)

```yaml
categories:
  김치:
    detect: ["김치", "포기김치", "열무김치"]
    candidate_like: ["김치", "김치류"]
    exclude: ["김치볶음", "김치찌개"]
  
  육류:
    detect: ["소고기", "돼지고기", "닭고기"]
    candidate_like: ["육류", "고기"]
    exclude: ["육수", "육개장"]
```

#### 키워드 사전 (KEYWORDS_DICT_PATH)

```yaml
roots:
  - "육수"
  - "다시"
  - "사골"
  - "곰탕"

strong_ngrams:
  - "사골곰탕"
  - "포기김치"
  - "왕교자"

variants:
  주꾸미: ["쭈꾸미"]
  가쓰오: ["가츠오", "가쓰오부시"]
  어묵: ["오뎅"]

stopwords:
  - "세트"
  - "선물세트"
  - "모음"
```

### 기본값

환경 변수를 설정하지 않으면 다음과 같은 기본값이 사용됩니다:

- `DYN_MAX_TERMS`: 32
- `TAIL_MAX_DF_RATIO`: 0.35
- `TAIL_MAX_TERMS`: 3
- `NGRAM_N`: 2
- `DYN_NGRAM_MIN`: 2
- `DYN_NGRAM_MAX`: 4
- `GATE_COMPARE_STORE`: false
- `RERANK_MODE`: off

### 성능 튜닝 팁

1. **검색 정확도 향상**: `GATE_COMPARE_STORE=true`로 설정
2. **처리 속도 향상**: `DYN_MAX_TERMS`를 줄이거나 `DYN_SAMPLE_ROWS`를 줄임
3. **필터링 강화**: `TAIL_MAX_DF_RATIO`를 낮춤 (예: 0.25)
4. **키워드 확장**: `DYN_MAX_EXTRAS`를 늘림

### 주의사항

- 환경 변수는 서버 재시작 시에만 적용됩니다
- 숫자 값은 정수여야 합니다 (소수점 불가)
- 불린 값은 `true`/`false`, `1`/`0`, `yes`/`no`, `on`/`off` 중 하나여야 합니다
- 사전 파일 경로는 절대 경로 또는 프로젝트 루트 기준 상대 경로를 사용하세요
