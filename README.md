# 🚀 TechPrep-AI: 개발자 실시간 IT 트렌드 & 핵심 인사이트 관제탑

[![Update TechPrep-AI Pipeline](https://github.com/sehuikim02/TechPrep-AI/actions/workflows/update_feed.yml/badge.svg)](https://github.com/sehuikim02/TechPrep-AI/actions/workflows/update_feed.yml)
[![GitHub Pages](https://img.shields.io/badge/Live-GitHub%20Pages-success?style=flat&logo=github)](https://sehuikim02.github.io/TechPrep-AI/)

> **5대 핵심 도메인별 실시간 IT 트렌드 수집 및 기사별 고유 실무 인사이트(Key Insight) 도출, 그리고 RAG 기반 지능형 시니어 AI 면접관 & 커리어 멘토링 플랫폼**

---

## 🌐 라이브 웹 데모 (Live Demo)
👉 **[TechPrep-AI 바로가기 (GitHub Pages)](https://sehuikim02.github.io/TechPrep-AI/)**

---

## 💡 핵심 최신 기능 (Key Highlights)

1. **기사별 1:1 맞춤형 실무 핵심 인사이트 (Unique Key Insight Engine)**:
   - 기존의 카테고리별 일괄 고정 멘트(하드코딩)를 전면 탈피하고, **각 기사의 고유 제목과 기술 맥락(DID/ZKP, AI 거버넌스, Spot/Graviton FinOps, K8s Probe, GitOps, SBOM, vLLM 등)을 반영한 차별화된 실무 인사이트를 동적 생성**
   - 수집 파이프라인(`collector/processor.py`)에서 370개 이상의 기사마다 각기 다른 실무 엔지니어링 포인트와 추천 대상 직무(`target_role`)를 제공

2. **RAG (검색증강생성) 지능형 검색 & 노이즈 필터링**:
   - 시스템이 수집·가공한 최신 IT 기사 및 실무 핵심 인사이트 데이터베이스(`news.json`)를 실시간 유사도 검색(Retrieval)
   - **문맥 인식 불용어 필터**: 날씨("오늘 서울 날씨는 어때?"), 일상 스몰토크, 단순 진로 고민 질의 시에는 무관한 기사가 인용되지 않도록 RAG 검색을 완전 차단하여 대화의 자연스러움 보장
   - 실제 기술 트렌드 질의 시에만 연관성 높은 최신 기사를 추출하여 Gemini API의 할루시네이션을 방지하고, 챗봇 답변 하단에 **실제 참조한 기사 링크 및 핵심 인사이트 배지(`📌 RAG 참조 기사`)**를 자동 표기

3. **Gemini 다중 모델 자동 폴백 체인 (Multi-Model Fallback Chain)**:
   - 특정 모델의 무료 티어 일일 쿼터 초과(429 Resource Exhausted) 시 서비스가 중단되지 않도록 **`gemini-3.5-flash-lite` ➔ `gemini-2.5-flash` ➔ `gemini-3.5-flash`**로 이어지는 무중단 자동 Failover 체계 구축

4. **다정하고 지혜로운 시니어 개발자 페르소나 (Career & Mindset Coach)**:
   - **신입 개발자 커리어 코칭**: "신입이라 어떤 걸 어필해야 할까?", "포트폴리오는 어떻게 꾸밀까?" 등의 고민에 대해 10년 차 면접관의 관점에서 CS 기본기, 디버깅 스토리, 협업 태도 등 현실적인 4대 어필 포인트 제시
   - **면접 긴장 및 멘탈 케어**: "면접이 너무 떨려", "심장이 쿵쾅거려요" 등의 감정적 호소에 대해 모르는 질문 대처법, 질문 곱씹기, 동료를 만나러 가는 마인드셋 등 따뜻한 격려와 실전 팁 전달
   - **실전 기술 면접 코칭**: LLM/RAG, 쿠버네티스 장애 복구, 대규모 트래픽 분산 및 Redis 캐싱 전략 등에 대해 STAR 기법과 실제 단골 꼬리 질문(Follow-up) 제공

5. **익명 세션(UUID) 기반 멀티 채팅방 & 대화 내역 영구 보존**:
   - 회원가입이나 로그인 없이도 브라우저 고유 UUID를 발급하여 독립된 세션 관리
   - **ChatGPT 스타일의 사이드바 서랍(Drawer)** 제공: `+ New Chat` 버튼으로 새로운 주제의 대화방 개설 및 과거 대화 내역 전환/삭제
   - 새로고침하거나 브라우저 창을 닫아도 `localStorage`와 백엔드 세션 스토어를 통해 이전 대화 내용이 100% 보존
   - 모바일/태블릿 환경에서 방 선택 시 대화창으로 즉시 복귀하는 백드롭 자동 닫힘 UI 적용

6. **하이브리드 시연 아키텍처 (Hybrid Fallback Engine)**:
   - **Render 백엔드 환경**: FastAPI + Google Gemini API + 서버 사이드 세션 스토어
   - **GitHub Pages 정적 호스팅 환경**: 백엔드 서버와의 연결 유무와 무관하게 브라우저 단독으로 작동하는 클라이언트 사이드 RAG 및 시니어 멘토 지능형 응답 엔진 내장

---

## 🏗️ 시스템 아키텍처 (System Architecture)

```mermaid
flowchart TD
    subgraph S1["1. 데이터 수집 & 정제 파이프라인 (Collector)"]
        RSS["국내/해외 IT RSS 피드<br>(전자신문, AWS, K8s, The Hacker News 등)"] --> Fetcher["fetcher.py<br>(비동기 피드 수집)"]
        Fetcher --> Processor["processor.py - 고유 인사이트 엔진<br>1) 비IT 노이즈 100% 차단<br>2) 5대 도메인 자동 분류<br>3) 기사별 1:1 맞춤형 실무 인사이트 생성"]
        Processor --> JSON["data/jobs_and_trends.json<br>& news.json 생성/갱신"]
    end

    subgraph S2["2. CI/CD 자동화 파이프라인 (GitHub Actions)"]
        JSON --> GHA[".github/workflows/update_feed.yml<br>매일 2회 정기 수집 & Git 자동 커밋"]
        GHA --> GHP["GitHub Pages 배포<br>(sehuikim02.github.io/TechPrep-AI)"]
    end

    subgraph S3["3. 프론트엔드 관제탑 (Frontend / Static Web)"]
        GHP --> UI["index.html - Tailwind CSS UI<br>- 5대 도메인 메트릭 카드 & 기사별 고유 인사이트 박스<br>- 풀와이드 실시간 키워드 검색바<br>- ChatGPT 스타일 멀티 대화방 사이드바 (서랍형)"]
    end

    subgraph S4["4. 백엔드 및 RAG 기반 AI 멘토 (Backend API)"]
        UI -->|"익명 세션 헤더 + 사용자 질문"| Fast["FastAPI 서버 (backend/main.py)<br>(Render 또는 로컬 8080)"]
        Fast -->|"RAG 지능형 검색 (일반 질문/날씨 필터링)"| RAG["내부 최신 기사 & 인사이트 DB"]
        RAG -->|"기술 질의 시 관련 아티클 컨텍스트 주입"| Gemini["Google Gemini Multi-Model Chain<br>(3.5-flash-lite / 2.5-flash / 3.5-flash)<br>시니어 개발자 & 커리어 멘토 페르소나"]
        Gemini -->|"실시간 맞춤 답변 + RAG 출처 + 꼬리 질문"| UI
    end
```

---

## 📁 프로젝트 디렉터리 구조 (Directory Structure)

```text
TechPrep-AI/
├── .github/
│   └── workflows/
│       └── update_feed.yml       # [자동화] 매일 2회 RSS 수집 실행 & GitHub Pages 자동 배포
├── backend/
│   ├── main.py                  # [백엔드] FastAPI 서버: 지능형 RAG 검색, 세션별 채팅방 관리, Gemini 다중 모델 체인
│   └── run_server.py            # [실행] Uvicorn 기반 로컬 개발용 서버 실행 스크립트
├── collector/
│   ├── config.py                # [설정] 9대 RSS 피드 목록 및 5대 도메인 키워드/제외어 정의
│   ├── fetcher.py               # [수집기] RSS/XML 파싱 및 실시간 뉴스 항목 추출
│   ├── processor.py             # [인사이트 엔진] 비IT 노이즈 필터링, 5대 카테고리 분류, 기사별 고유 실무 인사이트 도출
│   ├── sample_data.py           # [시드 데이터] 오프라인/네트워크 오류 시 사용할 고품질 면접 기출 데이터
│   └── main.py                  # [수집 실행] 수집-가공-인사이트 강화-JSON 저장을 총괄하는 파이프라인 진입점
├── data/
│   ├── jobs_and_trends.json     # [데이터] 가공 완료된 전체 기사 및 메타데이터 아카이브
│   └── news.json                # [데이터] 프론트엔드 연동용 JSON
├── frontend/
│   ├── index.html               # [웹 UI 원본] Tailwind CSS 기반 반응형 대시보드
│   ├── jobs_and_trends.json     # [프론트엔드용 복사본]
│   └── news.json                # [프론트엔드용 복사본]
├── index.html                   # [배포용] GitHub Pages 루트 호스팅용 웹 파일
├── jobs_and_trends.json         # [배포용] GitHub Pages 루트 데이터셋
├── news.json                    # [배포용] GitHub Pages 루트 데이터셋
├── requirements.txt             # [의존성] Render 배포 및 로컬 실행에 필요한 필수 패키지 목록
└── .gitignore                   # [보안] .env 등 개인 API 키 및 캐시 파일의 Git 업로드 방지
```

---

## ⚙️ 주요 API 명세 (Backend Endpoints)

| Method | Endpoint | 설명 |
|---|---|---|
| `POST` | `/api/chat` | 지능형 RAG 기사 검색 및 Gemini 시니어 면접관/커리어 멘토 실시간 답변 생성 |
| `GET` | `/api/chats` | 클라이언트 세션(`X-Session-ID`)에 속한 전체 채팅방 목록 조회 |
| `POST` | `/api/chats` | 새로운 채팅방(`+ New Chat`) 생성 |
| `GET` | `/api/chats/{room_id}/messages` | 특정 채팅방의 과거 대화 내역 조회 |
| `DELETE` | `/api/chats/{room_id}` | 특정 채팅방 삭제 |
| `GET` | `/api/status` | 타겟 인프라 상태 및 가상 시뮬레이션 지표 확인 |

---

## 🛠️ 기술 스택 (Tech Stack)

| 영역 | 기술 / 라이브러리 |
|---|---|
| **Frontend** | HTML5, Tailwind CSS, FontAwesome, Pretendard (공식 jsdelivr CDN) |
| **Backend API** | Python 3.12, FastAPI, Uvicorn, Pydantic |
| **AI / RAG** | Google Gemini (`gemini-3.5-flash-lite`, `gemini-2.5-flash`), Custom Hybrid RAG Engine |
| **Automation** | GitHub Actions (`update_feed.yml`), Cron Schedule |
| **Deployment** | GitHub Pages (프론트엔드 웹), Render (백엔드 웹 서비스) |

---

## 💻 로컬 실행 가이드 (Local Development)

```bash
# 1. 저장소 클론
git clone https://github.com/sehuikim02/TechPrep-AI.git
cd TechPrep-AI

# 2. 필수 의존성 설치
pip install -r requirements.txt

# 3. 환경 변수 설정 (.env 파일 생성)
echo 'GEMINI_API_KEY="your_api_key_here"' > .env

# 4. 데이터 파이프라인 수동 실행 (기사별 고유 인사이트 생성)
python3 -m collector.main

# 5. 백엔드 & 통합 웹 서버 실행 (포트 8080)
uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

브라우저에서 `http://localhost:8080`에 접속하시면 실시간 관제탑과 RAG 멀티 채팅 멘토를 바로 확인하실 수 있습니다.
