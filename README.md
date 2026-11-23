# 🚀 TechPrep-AI: 개발자 실시간 IT 트렌드 & 핵심 인사이트 관제탑

[![Update TechPrep-AI Pipeline](https://github.com/sehuikim02/TechPrep-AI/actions/workflows/update_feed.yml/badge.svg)](https://github.com/sehuikim02/TechPrep-AI/actions/workflows/update_feed.yml)
[![GitHub Pages](https://img.shields.io/badge/Live-GitHub%20Pages-success?style=flat&logo=github)](https://sehuikim02.github.io/TechPrep-AI/)
[![E2E Testing](https://img.shields.io/badge/Playwright-E2E%20Automated-blueviolet?style=flat&logo=playwright)](https://playwright.dev/)

> **5대 핵심 도메인별 실시간 IT 트렌드 수집 및 기사별 실무 인사이트(Key Insight) 도출, Intent Routing 기반 선택적 RAG, 대시보드 기사 이동 자율 제어(Agentic Navigation), Playwright E2E & AI 실패 진단 파이프라인, 풀스택 텔레메트리(프론트엔드 런타임 오류 실시간 관제)를 갖춘 엔터프라이즈급 AI 커리어 & 기술 멘토링 플랫폼**

---

## 🌐 라이브 웹 데모 (Live Demo)
👉 **[TechPrep-AI 바로가기 (GitHub Pages)](https://sehuikim02.github.io/TechPrep-AI/)**  
👉 **[백엔드 API 서버 (Render)](https://techprep-ai-vspr.onrender.com)**

---

## 💡 핵심 기능 및 신규 개발 사항 (Key Highlights)

### 1. 🤖 대시보드 기사 자동 이동 & 하이라이트 (Agentic Navigation Engine)
- **자율형 UI 제어 (UI Action)**: 사용자가 챗봇에 *"쿠버네티스 관련 기사 찾아서 보여줘"*, *"그 기사 어디 있어"* 등 기사 탐색/이동을 요청하면, AI가 텍스트 답변과 함께 실행 가능한 UI 액션(`ui_action = { type: "navigate_to_article", article_id, title, ... }`)을 반환합니다.
- **자동 화면 전환, 페이징 및 포커싱**: 프론트엔드가 해당 기사가 위치한 페이지를 자동 계산(`goToPage`)하여 렌더링하고, 대상 기사 카드로 부드럽게 스크롤(`scrollIntoView`)한 뒤 눈에 띄는 하이라이트 테두리(`agentic-highlight`)를 3초간 적용합니다.
- **대기 상태(Pending State) & 문맥 되묻기(Follow-up)**: *"기사 보여줘"*처럼 구체적인 키워드가 빠진 요청이 들어오면 바로 실패하거나 엉뚱한 기사로 이동하지 않고 실행을 대기(`pending_action`)하며 되묻고, 다음 턴에 *"쿠버네티스"* 등 단답형 키워드만 입력해도 의도를 이어받아 기사 이동을 즉시 실행합니다.
- **복수 후보 Quick Reply & 실시간 선택 피드백**: 검색 결과 매칭되는 후보가 여러 건일 경우 상위 2~3개 후보를 Quick Reply 버튼으로 제시하며, 버튼 클릭 시 즉각적인 시각적 활성 강조(`active-candidate`)와 함께 해당 기사로 이동합니다.
- **안정적인 챗봇 패널 이동성**: 사용자가 마우스/터치로 챗봇 패널을 화면 내에서 자유롭게 드래그하거나 좌/우 도킹 토글 및 접기/최소화할 수 있으며, 기사 이동 시 챗봇이 멋대로 널뛰지 않도록 패널 위치 고정성을 보장합니다.

### 2. 📡 풀스택 텔레메트리 & 프론트엔드 런타임 오류 실시간 감사 관제
- **전역 클라이언트 에러 자동 캡처**: 프론트엔드 최상단에 `window.addEventListener('error')` 및 `unhandledrejection` 전역 리스너를 배치하여, 브라우저에서 발생하는 자바스크립트 구문 오류, 런타임 예외, 비동기 Promise 실패를 자동 수집합니다.
- **백엔드 감사 로그 연동 (`POST /api/audit/client-error`)**: 수집된 브라우저 에러를 기존 감사 로그(`usage_logs`)에 `action = 'FRONTEND_ERROR'`, `status = 'CLIENT_ERROR'` 형태로 적재하며, 에러 메시지, 발생 위치(소스 파일/라인 번호), 호출 스택(Stack Trace), 기능 맥락(`context`), 로그인 계정명을 상세히 보존합니다.
- **도배 방지 및 쿨다운 (Dual Debounce)**: 동일 에러 시그니처에 대해 프론트엔드(3초) 및 백엔드 인메모리 캐시(5초) 단위 쿨다운을 적용하여 무한 루프나 네트워크 폭주를 원천 차단합니다.
- **관리자 관제탑 통합 필터**: 관리자 대시보드 'API / 조회 사용 로그'에서 프론트엔드 오류를 빨간색 `CLIENT_ERR` 뱃지로 식별할 수 있으며, `[실패·차단만 보기]` 빠른 필터로 백엔드 차단 로그와 함께 일괄 관제할 수 있습니다.

### 3. 🧪 Playwright 기반 E2E 테스트 & AI 실패 진단 자동화 파이프라인
- **핵심 시나리오 엔드투엔드 검증 (`tests/e2e/`)**:
  - `test_auth_flow.py`: 미인증 첫 접속 시 깜빡임(Flash) 없는 단독 로그인 화면 노출, 로그인 후 새로고침 시 대시보드 유지 및 로그아웃 검증.
  - `test_registration_audit_flow.py`: 8자+특수문자 비밀번호 정책 검증, 신규 가입 후 관리자 감사 로그 즉시 반영 및 5회 실패 시 계정 자동 차단 검증.
  - `test_chatbot_and_admin_flow.py`: 일상 대화 스몰토크(Bypass) vs 기술 질문(RAG 활성) Intent Routing 라우팅 검증 및 관리자 권한 제어 UI 즉시 반영 검증.
  - `test_agentic_navigation.py`: Agentic Navigation 기사 이동, 하이라이트, Quick Reply 선택 강조, Pending 되묻기 이어달리기 E2E 검증.
- **AI 기반 실패 원인 자동 분석 리포트 (`analyze_failures.py`)**:
  - 테스트 중 발생하는 브라우저 콘솔 에러, DOM 스냅샷, 네트워크 실패 로그를 `tests/e2e/artifacts/`에 자동 수집합니다.
  - 테스트 실패 시 Gemini API가 수집된 아티팩트를 정밀 분석하여 실패 원인 요약, 근본 원인 분석, 권장 수정 방안을 담은 마크다운 리포트(`AI_FAILURE_ANALYSIS_REPORT.md`)를 자동 생성합니다.
- **원클릭 로컬 테스트 실행 스크립트**: `bash tests/e2e/run_e2e_tests.sh` 하나로 로컬 FastAPI 서버 가동 ➔ 브라우저 테스트 ➔ 실패 분석 ➔ 서버 종료까지 완전 자동화.

### 4. 🛡️ 단일 전용 인증 게이트 (Dedicated Auth Gate) & 깜빡임 방지
- **완전 폐쇄형 보안 게이트**: 비로그인 상태에서는 상단 헤더, 메인 기사 목록, 챗봇 위젯을 숨기고 단일 전용 인증 게이트 화면만 노출하여 인가되지 않은 접근을 원천 차단합니다.
- **깜빡임(Flash) 현상 제거**: 페이지 로딩 시 로컬 JWT 토큰 유효성 검증이 완료될 때까지 게이트 카드의 노출을 지연시켜 화면 깜빡임을 완전히 해소했습니다.
- **강력한 비밀번호 보안 정책**: 회원가입 시 8자 이상 및 특수문자(`!@#$%^&*...`) 포함 여부를 실시간 검사하는 인터랙티브 정책 체크 UI를 제공합니다.
- **무차별 대입 공격(Brute-Force) 방어**: 로그인 5회 연속 실패 시 계정을 자동으로 차단(`blocked`)하며 관리자 감사 로그에 즉시 기록합니다.

### 5. 🎯 의도 기반 RAG 라우팅 (Intent-Based Hybrid RAG)
- **10년 차 시니어 엔지니어 페르소나**: 단순 요약을 넘어 질문자의 의도와 배경을 짚어주는 깊이 있는 모범 답변 및 꼬리 질문(Follow-up) 코칭을 제공합니다.
- **지능형 바이패스 (Selective RAG)**:
  - 일상 대화나 단순 안부, 커리어 고민 시에는 불필요한 RAG 검색을 건너뛰고(Bypass) 일반 대화 모드로 빠르고 따뜻하게 응답합니다.
  - 클라우드, 쿠버네티스, 보안, IT 트렌드 등 기술 주제 질의 시에만 실시간 IT 기사를 검색하여 `RAG 활성` 모드로 정밀 분석합니다.
- **다중 모델 폴백 (Fallback Strategy)**: `gemini-2.5-flash` ➔ `gemini-3.5-flash-lite` ➔ Google AI Studio REST 직접 호출로 이어지는 견고한 장애 대응 아키텍처를 구현했습니다.

### 6. 📊 관리자 전용 보안 관제탑 (Admin Operations Dashboard)
- **실시간 사용자 권한 제어**: 회원 목록 조회 및 각 회원의 API 키 사용 권한을 원클릭으로 **`[허용(Approve)]`** / **`[차단(Block)]`** 전환.
- **`admin` 계정 최상단 고정**: 신규 회원 가입이나 정렬 상태 변경과 무관하게 `admin` 관리자 계정은 항상 테이블 최상단(1행)에 고정 표시되며 `관리자 계정보호`가 적용됩니다.
- **다차원 감사 로그 (Audit Logs)**:
  - `로그인 시도 로그(login_logs)`: 시각, 계정명, IP, 성공/실패 여부 및 실패 원인 실시간 추적.
  - `API/조회 사용 로그(usage_logs)`: 사용자별 챗봇 호출, 대시보드 조회, 프론트엔드 오류(`FRONTEND_ERROR`), 기사 자동 정리(`ARTICLE_AUTO_CLEANUP`) 통합 모니터링.
  - **빠른 필터링**: `[실패·차단만 보기]`, `[챗봇 API만 보기]`, `[대시보드 조회 숨기기]` 제공.
- **Gemini 사용량 및 쿼터 실시간 모니터링**:
  - API 연동 상태(`ACTIVE`), 누적 호출 횟수, 토큰 사용량 실시간 집계.
  - 무료 티어 한도 대비 잔여량 및 소진율 게이지 바 제공.

### 7. 📑 오늘의 AI 보안 & 운영 리포트 (CrewAI 3단계 멀티 에이전트 감사 파이프라인)
- **CrewAI 멀티 에이전트 협업 구조 (`backend/crew_pipeline.py`)**: 단일 프롬프트 생성 방식에서 벗어나 3가지 전문 역할을 지닌 독립 에이전트 팀이 순차 협업(Sequential Process)하여 신뢰도 높은 리포트를 도출합니다:
  1. **지표 집계·검산 에이전트 (Audit Metrics Aggregator & Verifier)**: 대상 일자의 API 로그, 로그인 시도/실패, 토큰 사용량, 클라이언트 에러/차단 건수를 교차 검산하여 상단 요약 배너와 본문 수치 간 불일치를 원천 차단.
  2. **보안·운영 분석 에이전트 (Security & DevOps Operations Analyst)**: 인증 실패 패턴, 비정상 차단, 프론트엔드 에러 스택, 30일 경과 기사 정리 현황에서 핵심 인사이트와 잠재 리스크 도출.
  3. **리포트 작성 에이전트 (Executive Report Writer & Synthesizer)**: 관리자 관제탑 및 마크다운 다운로드에 최적화된 경영진 브리핑 양식의 4대 표준 목차(종합 요약, 보안 분석, 시스템 안정성, 권장 조치) 한국어 마크다운 최종 리포트 작성.
- **무한 대기(Hang) 방지 및 견고한 장애 대응 아키텍처**:
  - CrewAI 내부 원격 텔레메트리/OTLP 전송 및 대화형 trace 프롬프트 블로킹을 원천 차단(`CREWAI_TRACING_ENABLED=false`, `CREWAI_DISABLE_TELEMETRY=true`, `OTEL_SDK_DISABLED=true`, `CREWAI_TESTING=true`).
  - Google GenAI `HttpOptions`에 단일 요청 재시도(`HttpRetryOptions(attempts=1)`)를 적용하고 에이전트별 실행 제한(`max_iter=2`, `max_retry_limit=1`, `max_execution_time=25`)을 부여하여 외부 네트워크 지연이나 쿼터 초과(429) 시에도 무한 대기 없이 수초 내에 안전 Fallback 리포트로 즉시 전환.
- **관제탑 내부 서브 뷰/탭 전환 & 일자별 영구 저장 (UPSERT)**:
  - 관제탑 모달 헤더 상단의 `[관제 현황]` ↔ `[오늘의 AI 리포트]` 탭을 통해 세로 스크롤 과대화 없이 깔끔하게 화면 전환.
  - `daily_ai_reports` 테이블에 날짜 단위로 리포트와 분석 통계 메타데이터를 영구 저장(동일 날짜 재생성 시 멱등 갱신)하며, 상단의 **저장된 날짜 알약(Pills)** 클릭으로 과거 리포트 즉시 재조회 및 `.md` 원본 다운로드 지원.

### 8. 🔖 대시보드 북마크 & 30일 기사 자동 정리 보호 연계
- **대시보드 중심 북마크**: 별도의 마이페이지 없이 메인 대시보드 기사 카드의 북마크 버튼(★) 토글을 통해 사용자 계정별로 관심 기사를 저장 및 해제합니다.
- **'북마크만 보기' 필터**: 상단 추천 키워드 영역 옆의 토글 버튼으로 북마크된 기사만 모아볼 수 있으며, 북마크가 0건일 때도 친절한 안내 메시지를 표시합니다.
- **30일 자동 삭제 대상 제외(보호)**: 30일 경과 기사 자동 정리(`DELETE`) 및 미리보기(`Preview`) 실행 시, **사용자가 북마크한 기사는 30일이 경과했더라도 삭제 대상에서 완전히 제외되어 영구 보존**됩니다.

### 9. 🧹 30일 경과 기사 자동 정리 및 미리보기 (Data Lifecycle Engine)
- **자동 정리 실행**: 서버 시작 시(`startup_event`) 및 백그라운드 주기 작업(12시간)으로 30일(`ARTICLE_RETENTION_DAYS`)이 지난 오래된 기사를 JSON 파일 및 DB에서 자동 정리합니다.
- **삭제 대상 미리보기 (Preview)**: 관리자 관제탑 내 전용 카드를 통해 실제로 기사가 삭제되기 전 어떤 기사들이 30일 경과 대상인지 후보 목록과 건수를 사전 점검하고 필요 시 수동 정리를 즉시 실행할 수 있습니다.
- **감사 로그 상세 기록**: 삭제 실행 시 삭제된 기준일, 건수뿐 아니라 삭제된 대표 기사 제목 요약(상위 3건 + 외 N건)을 관리자 감사 로그(`ARTICLE_AUTO_CLEANUP`)에 영구 보존합니다.

---

## 🏗️ 시스템 아키텍처 (System Architecture)

```text
+---------------------------------------------------------------------------------------------------+
| 📡 1단계: 뉴스 수집 파이프라인 (collector/fetcher.py)                                              |
| - 주요 IT 언론사 및 기술 블로그(전자신문, AWS 공식, K8s, HackerNews 등)에서 RSS 피드 자동 수집     |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
| 🧠 2단계: 노이즈 필터링 & 실무 인사이트 생성 (collector/processor.py)                             |
| - 비(非)IT 기사 100% 제거, 5대 도메인 자동 분류, 기사별 고유 면접/실무 포인트(interview_insight) 생성    |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
| 🤖 3단계: 자동화 스케줄러 (GitHub Actions - update_feed.yml)                                      |
| - 매일 정기 크론으로 최신 데이터 수집 및 GitHub Pages 자동 배포                                    |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
| 💻 4단계: 프론트엔드 관제탑 (index.html)                                                          |
| - 단일 전용 인증 게이트 (깜빡임 방지 & 강력한 비밀번호 검증)                                       |
| - Agentic Navigation: 기사 위치 자동 스크롤, 하이라이트 및 Quick Reply 후보 선택 인터랙션          |
| - 드래그/도킹 지원 지능형 AI 챗봇 패널 & 전역 클라이언트 에러 실시간 감시 엔진                    |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
| ⚡ 5단계: 백엔드 API & 보안 관제 (FastAPI + SQLite + Render)                                      |
| 1) SQLite/Postgres DB: users, login_logs, usage_logs (클라이언트 런타임 에러 포함) 감사 추적       |
| 2) Intent Routing: 질문 유형 분석 ➔ 스몰토크(Bypass) vs 도메인 RAG vs 기사 이동(UI Action)         |
| 3) AI Generation: Google Gemini API (gemini-2.5-flash / gemini-3.5-flash-lite / REST Fallback)     |
| 4) Multi-Agent Audit: CrewAI 3단계 감사 파이프라인 (지표 검산 ➔ 보안/운영 분석 ➔ 리포트 합성)      |
| 5) Playwright E2E & AI Failure Analysis: 자동화 테스트 및 Gemini 실패 원인 분석 파이프라인        |
+---------------------------------------------------------------------------------------------------+
```

---

## ⚙️ 주요 API 명세 (Backend Endpoints)

| Method | Endpoint | 설명 | 권한 |
|---|---|---|---|
| `POST` | `/api/auth/register` | 신규 회원가입 (8자+특수문자 검증, 기본 `pending` 상태) | Public |
| `POST` | `/api/auth/login` | 로그인 및 JWT 토큰 발급 (5회 실패 시 자동 차단) | Public |
| `GET` | `/api/auth/me` | 현재 로그인된 사용자 정보 및 역할 확인 | Bearer Token |
| `POST` | `/api/chat` | Intent Routing RAG 검색, Agentic Navigation UI Action 반환 | 승인된 회원 / Admin |
| `GET` | `/api/chats` | 현재 사용자의 격리된 채팅방 목록 조회 | Bearer Token |
| `POST` | `/api/chats` | 새로운 대화방(`+ New Chat`) 생성 | Bearer Token |
| `GET` | `/api/chats/{room_id}/messages` | 특정 대화방의 과거 메시지 내역 조회 | Bearer Token |
| `DELETE` | `/api/chats/{room_id}` | 특정 대화방 삭제 | Bearer Token |
| `POST` | `/api/audit/client-error` | **프론트엔드 런타임/문법 오류 실시간 수집 및 감사 로그 적재** | Public / Token |
| `POST` | `/api/bookmarks/toggle` | 로그인 사용자의 기사 북마크 추가/해제 (토글) | Bearer Token |
| `GET` | `/api/bookmarks` | 현재 사용자가 저장한 전체 북마크 목록 조회 | Bearer Token |
| `GET` | `/api/bookmarks/ids` | 현재 사용자가 저장한 북마크 ID 배열 고속 조회 | Bearer Token |
| `GET` | `/api/admin/articles/cleanup-preview` | 30일 경과 기사 자동 삭제 대상 목록 및 건수 미리보기 | Admin Only |
| `POST` | `/api/admin/articles/cleanup` | 30일 경과 기사 수동 즉시 정리 실행 (감사 로그 자동 기록) | Admin Only |
| `GET` | `/api/admin/reports/dates` | 저장된 날짜별 AI 감사 리포트 목록 조회 | Admin Only |
| `GET` | `/api/admin/reports/{report_date}` | 특정 일자의 AI 운영/보안 감사 리포트 조회 | Admin Only |
| `POST` | `/api/admin/reports/generate` | 특정 일자 감사 데이터 기반 **CrewAI 3단계 멀티 에이전트 감사 리포트** 생성 및 저장 (UPSERT) | Admin Only |
| `GET` | `/api/admin/stats` | 관리자 대시보드 종합 지표, 토큰 사용량, 사용자 통계 조회 | Admin Only |
| `POST` | `/api/admin/users/status` | 특정 사용자의 API 권한 변경 (`approved` / `blocked`) | Admin Only |
| `POST` | `/api/admin/users/bulk-approve` | 승인 대기 회원 일괄 승인 | Admin Only |
| `GET` | `/api/admin/logs/login` | 로그인 시도 감사 로그 목록 조회 (사용자별 필터 지원) | Admin Only |
| `GET` | `/api/admin/logs/usage` | API 호출, 대시보드 조회 및 **프론트엔드 에러** 감사 로그 조회 | Admin Only |
| `GET` | `/api/status` | 타겟 인프라 상태 및 가상 시뮬레이션 지표 확인 | Public |

---

## 🛠️ 기술 스택 (Tech Stack)

| 영역 | 기술 / 라이브러리 |
|---|---|
| **Frontend** | HTML5, Tailwind CSS, FontAwesome, Pretendard CDN, Vanilla JS (Event Delegation, Global Error Telemetry) |
| **Backend API** | Python 3.11+, FastAPI, Uvicorn, Pydantic, PyJWT, Passlib(Bcrypt), Requests |
| **Database** | SQLite3 / PostgreSQL (users, login_logs, usage_logs, daily_ai_reports) |
| **AI / Multi-Agent** | Google Gemini (`gemini-2.5-flash`, `gemini-3.5-flash-lite`, REST Fallback), **CrewAI (3단계 멀티 에이전트 감사 파이프라인)**, Agentic Navigation Engine |
| **Testing / QA** | Playwright, Pytest, Pytest-Playwright, Pytest-Asyncio, Gemini AI Failure Analyzer |
| **Automation** | GitHub Actions (`update_feed.yml`), Cron Schedule |
| **Deployment** | GitHub Pages (프론트엔드 정적 호스팅), Render (FastAPI 백엔드 웹 서비스) |

---

## 💻 로컬 개발 및 테스트 가이드 (Local Development & Testing)

### 1. 환경 설정 및 실행
```bash
# 1. 저장소 클론
git clone https://github.com/sehuikim02/TechPrep-AI.git
cd TechPrep-AI

# 2. 필수 의존성 설치
pip install -r requirements.txt
playwright install chromium

# 3. 환경 변수 설정 (.env 파일 생성)
cat << 'EOF' > .env
GEMINI_API_KEY="your_gemini_api_key_here"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin1234"
JWT_SECRET_KEY="your-custom-jwt-secret-key-32bytes"
EOF

# 4. 데이터 수집 파이프라인 수동 실행 (선택)
python3 -m collector.main

# 5. 백엔드 & 통합 웹 서버 실행 (포트 8000)
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 2. CrewAI 멀티 에이전트 감사 파이프라인 단독 실행 (선택)
```bash
# 특정 날짜(또는 오늘) 기준으로 3단계 협업 감사 리포트 단독 생성
python3 -u backend/crew_pipeline.py 2026-11-23
```
- 지표 검산, 보안·운영 분석, 비즈니스 마크다운 합성까지 3개 에이전트가 협업하며, 외부 API 쿼터 초과 시 안전 Fallback 리포트로 자동 전환됩니다.

### 3. Playwright E2E 테스트 및 AI 진단 리포트 실행
```bash
# 원클릭 테스트 실행 (서버 자동 가동 및 테스트 후 리포트 생성)
bash tests/e2e/run_e2e_tests.sh
```
- 테스트 실패 시 `tests/e2e/artifacts/AI_FAILURE_ANALYSIS_REPORT.md`에서 Gemini가 분석한 근본 원인 및 권장 수정 코드를 바로 확인하실 수 있습니다.
