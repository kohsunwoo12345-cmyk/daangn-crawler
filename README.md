# 🥕 당근마켓 동네업체 크롤러 v2

> 지역(시/도→구/군→동) 선택 + 카테고리별 010 번호 즉시 추출 + 엑셀 다운로드

> 🖥️ **디지털 사이니지** — 두 가지 버전 제공
> - **웹 버전** (`index.html`): 설치 없이 브라우저에서 바로 사진·영상 재생. Cloudflare Pages(`daangn-crawler.pages.dev`)로 호스팅. 멀티 모니터는 화면 창을 띄워 동기화 재생.
> - **데스크톱 버전** (`signage/`): Electron 앱. HDMI 3개 화면에 전체화면 자동 배치. [`signage/README.md`](./signage/README.md) 참고.

### Cloudflare Pages 배포 메모
- 정적 사이트이므로 **빌드 명령 없음 / 출력 디렉터리 `/`(루트)** 로 두면 루트 `index.html`이 그대로 서빙됩니다.
- `*.pages.dev` 루트 도메인은 **프로덕션 브랜치(main)** 의 내용을 보여줍니다. 기능 브랜치 푸시는 별도 미리보기 URL로 배포되니, 루트 도메인 반영은 **main 병합** 후 적용됩니다.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/kohsunwoo12345-cmyk/daangn-crawler)

---

## 기능

- **지역 선택**: 시/도 → 구/군 → 동 캐스케이딩 드롭다운 (전국 17개 시도)
- **카테고리**: 음식점, 카페, 뷰티, 병원 등 16개 업종 선택
- **010 번호 자동 추출**: 010 이외 번호 자동 제외
- **실시간 스트리밍**: SSE로 결과 즉시 표시
- **엑셀(xlsx) 다운로드**: 주황 헤더·번호 강조 서식
- **CSV / TXT 다운로드**: UTF-8 BOM, 정렬된 010 번호 목록
- **프록시 로테이션**: 공개 프록시 자동 수집·검증 (선택)

---

## 배포 (Render.com — 무료)

### 원클릭 배포
위의 **Deploy to Render** 버튼 클릭 → GitHub 연동 → Deploy

### 수동 배포
```
1. https://dashboard.render.com → New → Web Service
2. GitHub 저장소 연결: kohsunwoo12345-cmyk/daangn-crawler
3. Runtime: Python 3
4. Build Command: pip install -r requirements.txt
5. Start Command: gunicorn server:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 --worker-class gthread
6. Deploy!
```

---

## 로컬 실행

```bash
pip install -r requirements.txt
python server.py
# → http://localhost:7979
```

---

## 파일 구성

```
daangn-crawler/
├── server.py          ← Flask 웹 서버 (API + SSE + 다운로드)
├── crawler.py         ← 크롤링 핵심 로직 (010 필터, 지역 기반)
├── regions.py         ← 전국 시도/구군/동 데이터 + Daangn 지역 ID
├── proxy_manager.py   ← 프록시 자동 수집·검증·로테이션
├── exporter.py        ← CLI 전용 CSV/JSON/TXT 저장
├── main.py            ← CLI 진입점
├── static/
│   └── index.html     ← Web UI (캐스케이딩 드롭다운, 실시간 결과)
├── requirements.txt
├── Procfile
└── render.yaml
```

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/regions` | 시도→구군→동 트리 반환 |
| GET | `/api/categories` | 카테고리 목록 |
| POST | `/api/crawl` | 크롤링 작업 시작 |
| GET | `/api/stream/{jid}` | SSE 실시간 스트림 |
| GET | `/api/job/{jid}` | 작업 상태/결과 조회 |
| GET | `/api/download/{jid}/xlsx` | 엑셀 다운로드 |
| GET | `/api/download/{jid}/csv` | CSV 다운로드 |
| GET | `/api/download/{jid}/phones` | 010번호 TXT 다운로드 |

---

## 주의사항

- 당근마켓 이용약관 및 robots.txt를 확인하여 개인 연구 목적으로만 사용하세요.
- 수집한 개인정보(전화번호)는 관련 법령을 준수하여 처리하세요.
