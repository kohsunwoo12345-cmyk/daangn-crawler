# 당근마켓 동네업체 전화번호 크롤러

> **격리 독립 모듈** – `daangn-crawler/` 디렉토리 내에서만 동작하며 외부 파일에 영향 없음.

---

## 파일 구성

```
daangn-crawler/
├── main.py            ← 진입점 (CLI)
├── crawler.py         ← 크롤링 핵심 로직
├── proxy_manager.py   ← 프록시 자동 수집·검증·로테이션
├── exporter.py        ← CSV / JSON / TXT 저장
└── README.md
```

---

## 동작 방식

```
1. proxy_manager.py
   └─ 공개 프록시 소스(5곳) → HTTP 수집 → 병렬 유효성 검증 → 풀 구성

2. crawler.py
   ├─ 검색/카테고리 목록 페이지 → 업체 상세 URL 수집
   ├─ 상세 페이지 HTML 파싱 (og:title, JSON 내부 데이터)
   └─ BusinessInfo(업체명, 전화번호, 안심번호, 주소, 카테고리) 추출

3. exporter.py
   └─ CSV (UTF-8 BOM) / JSON / 전화번호 TXT 저장
```

---

## 설치

```bash
pip install playwright requests httpx fake-useragent aiohttp lxml beautifulsoup4 rich colorama
playwright install chromium
```

---

## 사용법

### 기본 실행 (기본 키워드 전체)
```bash
cd daangn-crawler
python main.py
```

### 특정 키워드로 검색
```bash
python main.py -k 카페 미용실 학원 병원
```

### 카테고리로 수집
```bash
python main.py -c CAFE_AND_BAKERY FOOD_AND_BEVERAGES BEAUTY
```

### 프록시 없이 (빠른 테스트)
```bash
python main.py --no-proxy -k 카페 -n 20
```

### 대량 수집
```bash
python main.py -k 카페 음식점 미용실 헬스장 학원 -n 100 -w 5
```

### 전화번호만 텍스트로 저장
```bash
python main.py --format phones -k 카페 음식점
```

---

## 전체 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `-k KEYWORD [...]` | 기본 키워드 목록 | 검색할 키워드 |
| `-c CATEGORY [...]` | — | 카테고리 코드 |
| `-n N` | 30 | 키워드당 최대 업체 수 |
| `-w N` | 3 | 병렬 워커 수 (5 이하 권장) |
| `--no-proxy` | — | 프록시 없이 직접 연결 |
| `--delay-min SEC` | 1.5 | 최소 요청 딜레이(초) |
| `--delay-max SEC` | 3.5 | 최대 요청 딜레이(초) |
| `-o PREFIX` | 자동 타임스탬프 | 출력 파일 접두어 |
| `--format` | both | csv / json / both / phones |
| `--list-categories` | — | 카테고리 목록 출력 |
| `-v` | — | 상세 로그 |

---

## 카테고리 목록

```bash
python main.py --list-categories
```

| 카테고리 이름 | 코드 |
|--------------|------|
| 전체 | (없음) |
| 음식점 | FOOD_AND_BEVERAGES |
| 카페/디저트 | CAFE_AND_BAKERY |
| 뷰티/미용 | BEAUTY |
| 운동/스포츠 | SPORTS_AND_FITNESS |
| 교육 | EDUCATION |
| 병원/의원 | MEDICAL |
| 반려동물 | PET |
| 인테리어 | INTERIOR |
| 자동차 | AUTOMOBILE |
| 청소 | CLEANING |
| 세탁 | LAUNDRY |
| 사진 | PHOTO |
| 여행/숙박 | TRAVEL |
| 부동산 | REAL_ESTATE |
| 기타 | OTHER |

---

## 출력 파일

| 파일 | 설명 |
|------|------|
| `*.csv` | 업체명, 전화번호, 안심번호, 카테고리, 주소, 지역, 설명, URL |
| `*.json` | 동일 내용 JSON |
| `*_phones.txt` | 전화번호만 (중복 제거, 정렬) |
| `daangn_crawler.log` | 실행 로그 |

---

## 프록시 동작 방식

```
공개 프록시 소스 5곳에서 최대 300개 수집
  → 30개 스레드로 병렬 유효성 검증 (Google 접속 확인)
  → 유효한 프록시 풀 구성 (최대 30개)
  → 크롤링 시 랜덤 프록시 선택 & 로테이션
  → 실패 3회 이상 프록시 자동 블랙리스트 처리
```

> **유효 프록시가 없으면** 자동으로 직접 연결로 전환합니다.

---

## 주의사항

- 당근마켓 이용약관 및 robots.txt를 확인하여 개인 연구 목적으로만 사용하세요.
- 과도한 요청은 IP 차단을 유발할 수 있으므로 딜레이 설정을 유지하세요.
- 수집한 개인정보(전화번호)는 관련 법령을 준수하여 처리하세요.
