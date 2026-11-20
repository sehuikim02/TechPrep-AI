# 🚀 TechPrep-AI: 개발자 실시간 IT 트렌드 & 핵심 인사이트 관제탑

[![Update TechPrep-AI Pipeline](https://github.com/sehuikim02/TechPrep-AI/actions/workflows/update_feed.yml/badge.svg)](https://github.com/sehuikim02/TechPrep-AI/actions/workflows/update_feed.yml)
[![GitHub Pages](https://img.shields.io/badge/Live-GitHub%20Pages-success?style=flat&logo=github)](https://sehuikim02.github.io/TechPrep-AI/)

> **5대 핵심 도메인별 실시간 IT 트렌드 수집 및 기사별 고유 실무 인사이트(Key Insight) 도출, Intent Routing 기반 선택적 RAG, SQLite 회원/API 키 권한 제어, 감사 로그 및 관리자 대시보드를 갖춘 엔터프라이즈급 AI 커리어 & 기술 멘토링 플랫폼**

---

## 🌐 라이브 웹 데모 (Live Demo)
👉 **[TechPrep-AI 바로가기 (GitHub Pages)](https://sehuikim02.github.io/TechPrep-AI/)**  
👉 **[백엔드 API 서버 (Render)](https://techprep-ai-vspr.onrender.com)**

---

## 💡 핵심 최신 기능 (Key Highlights)

### 1. 🛡️ 회원 인증(JWT) 및 로그인 게이트 (Login Wall)
- **폐쇄형 실무 플랫폼 게이트**: 비로그인 상태에서는 최신 기술 기사 및 AI 챗봇이 잠금 처리되며, 중앙에 직관적인 로그인/회원가입 게이트 모달이 노출됩니다.
- **SQLite 기반 사용자 관리**: `users` 테이블을 구축하고 비밀번호는 `bcrypt` 솔트 해싱으로 암호화하여 저장합니다.
- **Render 무중단 관리자 계정 시딩(Seeding)**: Render 무료 티어의 파일 초기화 특성을 고려하여, 서버 구동 시 환경 변수(`ADMIN_USERNAME`, `ADMIN_PASSWORD`)를 감지해 관리자 계정(`admin`)을 자동으로 시딩하고 `role='admin'`, `api_status='approved'`를 영구 보장합니다.

### 2. 🔐 GEMINI API 키 권한 제어 (승인/차단/실패 추적)
- **권한 상태 체계**: 사용자는 가입 시 기본적으로 `pending`(승인 대기) 상태로 생성됩니다.
- **API 호출 통제**: 오직 관리자(`admin`) 또는 관리자가 `approved`(허용)로 승인한 계정만 서버에 등록된 `GEMINI_API_KEY`를 사용할 수 있습니다.
- **403 Forbidden 방어 및 로깅**: 미승인(`pending`)이나 차단(`blocked`) 계정의 API 호출 시도는 `403 Forbidden` 에러와 함께 친절한 안내를 반환하며, 실패 감사 로그(`usage_logs`)에 기록됩니다.

### 3. 🎯 의도 기반 RAG 라우팅 (Intent-Based RAG Routing)
- **시니어 면접관 페르소나 유지**: 다정하고 지혜로운 10년 차 시니어 엔지니어 톤앤매너를 일관되게 유지합니다.
- **선택적 RAG 우회(Bypass)**:
  - 일상 대화, 스몰토크(날씨, 안부 등), 일반 커리어/신입 어필 포인트, 진로 상담 질의 시에는 **불필요한 RAG 검색을 건너뛰고(Bypass)**, Gemini 모델이 시니어 멘토 페르소나로 직접 자연스럽고 따뜻하게 답변합니다.
  - 최신 IT 트렌드, 보안(CVE), 클라우드/인프라/k8s 등 실제 기술 이슈 질의 시에만 지능형 RAG 검색을 수행합니다.
- **하드코딩 템플릿 제거**: 문맥에 맞지 않던 고정형 fallback 문구(`TechPrep AI Mentor (Built-in) + RAG` 등)를 전면 제거하고, RAG 기사 매칭 여부와 무관하게 맥락에 맞는 고품질 시니어 코칭을 제공합니다.

### 4. 📊 관리자 전용 관제탑 대시보드 (Admin Dashboard)
- 관리자 계정 로그인 시 상단 네비게이션에 `[관리자 대시보드]` 탭 활성화.
- **사용자 권한 관리**: 회원 목록 조회 및 각 회원의 API 키 사용 권한을 원클릭으로 **`[허용(Approve)]`** / **`[차단(Block)]`** 제어.
- **보안 및 감사 로그 (Audit Logs)**:
  - `로그인 시도 로그(login_logs)`: 시각, 계정명, IP, 성공/실패 여부 및 실패 원인 추적.
  - `API/조회 사용 로그(usage_logs)`: 사용자별 대시보드 조회수, 챗봇 호출 횟수, 토큰 사용량 실시간 기록.
- **Gemini 사용량 및 쿼터 모니터링**:
  - API 연동 상태(`ACTIVE`), 일일 누적 호출 횟수, 입/출력 토큰(`usage_metadata` 추출) 실시간 집계.
  - Gemini 일일 무료 한도(1,500 RPD / 1,000,000 TPM) 대비 잔여량 및 소진율 프로그레스 바 시각화.

### 5. 🔒 로그인 사용자별 챗봇 대화방 격리 (User Isolation)
- 프론트엔드 로컬 스토리지 키(`techprep_chat_rooms_{username}`)와 백엔드 세션 스토어(`user:{username}`)를 사용자 계정별로 격리.
- 다른 계정으로 로그인 시 이전 사용자의 대화 기록이 절대 노출되지 않으며, 로그아웃 시 화면이 즉시 초기화됩니다.

---

## 🏗️ 시스템 아키텍처 (System Architecture)

```text
+---------------------------------------------------------------------------------------------------+
| 📡 1단계: 뉴스 수집 파이프라인 (fetcher.py)                                                        |
| - 주요 IT 언론사 및 기술 블로그(전자신문, AWS 공식, K8s, HackerNews 등)에서 RSS 피드 자동 수집     |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
| 🧠 2단계: 노이즈 필터링 & 실무 인사이트 생성 (processor.py)                                       |
| - 비(非)IT 기사 100% 제거, 5대 도메인 자동 분류, 기사별 고유 면접/실무 포인트(interview_insight) 생성    |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
| 🤖 3단계: 자동화 스케줄러 (GitHub Actions - update_feed.yml)                                      |
| - 하루 2회(09:00 / 21:00 KST) 크론으로 최신 데이터 수집 및 GitHub Pages 자동 배포                |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
| 💻 4단계: 프론트엔드 관제탑 (index.html)                                                          |
| - 로그인 게이트 (Login Wall) 통과 후 메인 대시보드 및 5대 도메인 카드뉴스 접근                    |
| - 실시간 검색, 추천 키워드 필터링, 관리자 대시보드 모달 제공                                      |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------+
| ⚡ 5단계: 백엔드 API & 보안 관제 (FastAPI + SQLite + Render)                                      |
| 1) SQLite DB: users, login_logs, usage_logs 테이블을 통한 권한/감사 추적                           |
| 2) Intent Routing: 질문 유형 분석 ➔ 일상/진로 상담(Bypass) vs 도메인 기술 이슈(RAG 검색)          |
| 3) AI Generation: Google Gemini API (gemini-2.5-flash / gemini-3.5-flash-lite) 시니어 면접관 답변  |
+---------------------------------------------------------------------------------------------------+
```

---

## ⚙️ 주요 API 명세 (Backend Endpoints)

| Method | Endpoint | 설명 | 권한 |
|---|---|---|---|
| `POST` | `/api/auth/register` | 신규 회원가입 (기본 `pending` 상태) | Public |
| `POST` | `/api/auth/login` | 로그인 및 JWT 토큰 발급, 로그인 시도 감사 로그 기록 | Public |
| `GET` | `/api/auth/me` | 현재 로그인된 사용자 정보 및 역할 확인 | Bearer Token |
| `POST` | `/api/chat` | Intent Routing RAG 검색 및 Gemini 시니어 멘토 답변 생성 | 승인된 회원 / Admin |
| `GET` | `/api/chats` | 현재 사용자의 격리된 채팅방 목록 조회 | Bearer Token |
| `POST` | `/api/chats` | 새로운 대화방(`+ New Chat`) 생성 | Bearer Token |
| `GET` | `/api/chats/{room_id}/messages` | 특정 대화방의 과거 메시지 내역 조회 | Bearer Token |
| `DELETE` | `/api/chats/{room_id}` | 특정 대화방 삭제 | Bearer Token |
| `GET` | `/api/admin/stats` | 관리자 대시보드 종합 지표, 토큰 사용량, 사용자 통계 조회 | Admin Only |
| `POST` | `/api/admin/users/status` | 특정 사용자의 API 권한 변경 (`approved` / `blocked`) | Admin Only |
| `GET` | `/api/admin/logs/login` | 로그인 시도 감사 로그 목록 조회 | Admin Only |
| `GET` | `/api/admin/logs/usage` | API 호출 및 페이지 조회 감사 로그 목록 조회 | Admin Only |
| `GET` | `/api/status` | 타겟 인프라 상태 및 가상 시뮬레이션 지표 확인 | Public |

---

## 🛠️ 기술 스택 (Tech Stack)

| 영역 | 기술 / 라이브러리 |
|---|---|
| **Frontend** | HTML5, Tailwind CSS, FontAwesome, Pretendard CDN, Vanilla JS |
| **Backend API** | Python 3.12+, FastAPI, Uvicorn, Pydantic, PyJWT, Bcrypt |
| **Database** | SQLite3 (users, login_logs, usage_logs) |
| **AI / RAG** | Google Gemini (`gemini-2.5-flash`, `gemini-3.5-flash-lite`), Intent-Based Hybrid RAG Engine |
| **Automation** | GitHub Actions (`update_feed.yml`), Cron Schedule |
| **Deployment** | GitHub Pages (프론트엔드 정적 호스팅), Render (FastAPI 백엔드 웹 서비스) |

---

## 💻 로컬 실행 가이드 (Local Development)

```bash
# 1. 저장소 클론
git clone https://github.com/sehuikim02/TechPrep-AI.git
cd TechPrep-AI

# 2. 필수 의존성 설치
pip install -r requirements.txt

# 3. 환경 변수 설정 (.env 파일 생성)
cat << 'EOF' > .env
GEMINI_API_KEY="your_gemini_api_key_here"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin1234"
JWT_SECRET_KEY="your-custom-jwt-secret-key-32bytes"
EOF

# 4. 데이터 파이프라인 수동 실행 (기사 수집 및 고유 인사이트 가공)
python3 -m collector.main

# 5. 백엔드 & 통합 웹 서버 실행 (포트 8080)
uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

브라우저에서 `http://localhost:8080`에 접속하시면 로그인 게이트가 표시되며, 기본 관리자 계정(`admin` / `admin1234`)으로 로그인하여 모든 기능을 바로 테스트하실 수 있습니다.
