# 🚀 TechPrep-AI: 개발자 실시간 IT 트렌드 & 핵심 인사이트 관제탑

[![Update TechPrep-AI Pipeline](https://github.com/sehuikim02/TechPrep-Ai/actions/workflows/update_feed.yml/badge.svg)](https://github.com/sehuikim02/TechPrep-Ai/actions/workflows/update_feed.yml)
[![GitHub Pages](https://img.shields.io/badge/Live-GitHub%20Pages-success?style=flat&logo=github)](https://sehuikim02.github.io/TechPrep-Ai/)

> **5대 핵심 도메인별 실시간 IT 트렌드 수집 및 AI 기반 실무 인사이트 & 시니어 면접 코칭 플랫폼**

---

## 🌐 라이브 웹 데모 (Live Demo)
👉 **[TechPrep-AI 바로가기 (GitHub Pages)](https://sehuikim02.github.io/TechPrep-Ai/)**

---

## 💡 주요 기능 (Key Features)

1. **5대 핵심 도메인 필터링 & 큐레이션**:
   - **IT 트렌드**: 빅테크 동향, 디지털 전환, 정책/플랫폼
   - **클라우드 아키텍처**: AWS, Serverless, FinOps, 다중 리전 DR
   - **인프라 / DevOps**: Kubernetes, Docker, CI/CD, 대규모 트래픽 분산
   - **보안 / 침해사고**: CVE 취약점 분석, 제로트러스트, 침해사고 대응
   - **AI / 머신러닝**: LLM 서빙, RAG 아키텍처, AI 에이전트, MLOps

2. **노이즈 필터링 엔진 (`collector/processor.py`)**:
   - 일반 학습지, 아동 교육, 단순 소비재 기사 등 비IT 노이즈를 100% 자동 필터링
   - 고순도 IT 엔지니어링 기술 기사만 자동 분류 및 보존

3. **실무 핵심 인사이트 (Key Insights)**:
   - 기사 내용에서 단순 요약을 넘어, 실제 시스템 아키텍처 관점의 장단점 및 면접관이 주목하는 실무 시사점을 자동 도출

4. **AI 면접 멘토 챗봇 (Gemini & Client-side)**:
   - IT 대기업 10년 차 시니어 DevOps / 백엔드 면접관 페르소나 탑재
   - 면접 답변 요령, STAR 기법 가이드, 기술 꼬리 질문(Follow-up) 실시간 코칭 제공
   - **GitHub Pages 환경에서도 100% 동작하는 지능형 클라이언트 엔진 내장**

5. **완전자동 GitHub Actions 파이프라인**:
   - 매일 주기적으로 전 세계 및 국내 IT RSS 피드를 자동 수집하여 GitHub Pages에 즉시 반영

---

## 🛠️ 기술 스택 (Tech Stack)

- **Frontend**: HTML5, Tailwind CSS, FontAwesome, Vanilla JS
- **Automation / Pipeline**: GitHub Actions (`.github/workflows/update_feed.yml`), Python 3.12
- **Data Engineering**: Python RSS Fetcher & AI Insight Engine
- **Hosting**: GitHub Pages (정적 호스팅 및 실시간 데이터 동기화)

---

## 💻 로컬 실행 가이드 (Local Development)

```bash
# 1. 저장소 클론
git clone https://github.com/sehuikim02/TechPrep-Ai.git
cd TechPrep-Ai

# 2. 파이프라인 즉시 실행 (데이터 수집)
python3 -m collector.main

# 3. 로컬 웹 서버 실행 (포트 8080)
python3 -m http.server 8080
```
웹 브라우저에서 `http://localhost:8080`으로 접속하시면 즉시 확인하실 수 있습니다.
