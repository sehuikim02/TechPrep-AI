import re
import os
import json
import logging
import urllib.request
from typing import List, Dict, Optional
from collector.config import CATEGORY_KEYWORDS, EXCLUDE_KEYWORDS

class InterviewInsightEngine:
    """
    기사 텍스트를 분석하여 5대 핵심 도메인별 분류 및 실무 핵심 인사이트 도출:
    1. IT 트렌드 (사회 전반의 IT/디지털 전환, 모바일 신분증, AI 기본법/규제, 스마트워크, 플랫폼 정책)
    2. 클라우드 아키텍처 (AWS, Serverless, FinOps, IaC)
    3. 인프라/DevOps (K8s, Docker, CI/CD, 대규모 트래픽 장애 대응)
    4. 보안/침해사고 (CVE, RCE, 랜섬웨어, 제로트러스트)
    5. AI/머신러닝 (LLM, RAG, AI 에이전트, MLOps)
    """

    def clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        clean_text = re.sub(r'<[^>]+>', ' ', raw_html)
        clean_text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', clean_text)
        return re.sub(r'\s+', ' ', clean_text).strip()

    def is_relevant_it_article(self, title: str, text: str) -> bool:
        """
        비IT 기사(학습지, 아동 교육, 단순 가전제품, 포토/인사/부고 등) 필터링 및
        IT 핵심 기술 키워드 포함 여부 검증
        """
        combined = f"{title} {text}".lower()

        # 1. 블랙리스트 키워드가 제목이나 본문에 포함되어 있으면 제외
        for ex in EXCLUDE_KEYWORDS:
            if ex.lower() in combined:
                return False

        # 2. 5대 핵심 카테고리 중 적어도 1개 이상의 전문 기술 키워드가 매칭되는지 확인
        # (구몬, 단순 마케팅 기사가 fallback으로 IT 트렌드나 AI로 들어가는 것 차단)
        high_priority_tech = [
            "kubernetes", "k8s", "docker", "컨테이너", "devops", "ci/cd", "인프라", "클라우드", "aws", "azure", "gcp",
            "serverless", "보안", "취약점", "해킹", "랜섬웨어", "cve", "ddos", "llm", "ai", "인공지능", "머신러닝",
            "딥러닝", "gpt", "rag", "데이터센터", "sre", "모니터링", "반도체", "오픈소스", "빅테크", "소프트웨어", "개발자", "디지털 전환"
        ]
        
        if any(tech in combined for tech in high_priority_tech):
            return True

        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in combined:
                    return True

        return False

    def classify_category(self, text: str, fallback_category: str = "IT 트렌드") -> Optional[str]:
        text_lower = text.lower()
        
        # 1. 인프라/쿠버네티스/컨테이너/데브옵스 우선 판별
        infra_core = ["kubernetes", "k8s", "쿠버네티스", "docker", "도커", "container", "컨테이너", "devops", "데브옵스", "ci/cd", "argo", "terraform", "sre"]
        if any(w in text_lower for w in infra_core):
            return "인프라/DevOps"

        # 2. 클라우드 아키텍처 우선 판별
        cloud_core = ["aws", "azure", "gcp", "클라우드", "cloud", "serverless", "서버리스", "finops", "vpc"]
        if any(w in text_lower for w in cloud_core):
            return "클라우드 아키텍처"

        # 3. 보안/침해사고 우선 판별
        security_core = ["vulnerability", "취약점", "해킹", "랜섬웨어", "cve", "openssh", "침해사고", "제로트러스트", "악성코드", "cyberattack"]
        if any(w in text_lower for w in security_core):
            return "보안/침해사고"

        # 4. AI/머신러닝 우선 판별
        ai_core = ["llm", "rag", "ai 에이전트", "bedrock", "gpt", "머신러닝", "딥러닝", "파인튜닝", "생성형 ai", "vllm"]
        if any(w in text_lower for w in ai_core):
            return "AI/머신러닝"

        # 5. IT 트렌드 판별
        trend_core = ["디지털 전환", "빅테크", "오픈소스", "개발자", "dx", "ax", "반도체 생태계", "it 거버넌스"]
        if any(w in text_lower for w in trend_core):
            return "IT 트렌드"

        scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                matches = len(re.findall(re.escape(kw), text_lower))
                scores[category] += matches

        best_category = max(scores, key=scores.get)
        if scores[best_category] > 0:
            return best_category
        return fallback_category if fallback_category in CATEGORY_KEYWORDS else "IT 트렌드"

    def extract_keywords(self, text: str, top_n: int = 4) -> List[str]:
        words = re.findall(r'[A-Za-z0-9가-힣]{2,}', text)
        stopwords = {
            "this", "that", "with", "from", "have", "were", "been", "their", "about",
            "which", "using", "service", "these", "there", "based", "today", "news",
            "그리고", "하지만", "통해", "위해", "있는", "대한", "관련", "지난", "이번", "기자", "출시", "발표"
        }
        freq = {}
        for w in words:
            w_lower = w.lower()
            if w_lower in stopwords or len(w_lower) < 2:
                continue
            freq[w] = freq.get(w, 0) + 1

        sorted_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [k for k, _ in sorted_keywords[:top_n]]

    def generate_key_insight(self, category: str, title: str, content: str) -> Dict:
        """
        기술 트렌드 기사에서 실무 핵심 인사이트 및 주요 엔지니어링 포인트를 도출 (규칙 기반 폴백)
        """
        text = f"{title} {content}".lower()

        # 1. IT 트렌드 (사회 전반의 IT 서비스, 디지털 신원, 플랫폼 규제, 스마트워크)
        if category == "IT 트렌드":
            if "신분증" in text or "인증" in text or "did" in text:
                return {
                    "insight": f"'{title[:20]}...' 이슈처럼 분산 신원(DID)/인증 아키텍처 도입 시, 중앙 DB 탈취 위험을 원천 차단하기 위한 개인키 소셜 복구와 영지식 증명(ZKP) 설계가 핵심입니다.",
                    "target_role": "플랫폼 / 보안 엔지니어"
                }
            elif "기본법" in text or "규제" in text or "윤리" in text:
                return {
                    "insight": f"'{title[:20]}...'와 같은 AI 거버넌스 강화 국면에서는 대고객 서비스의 출력 편향 및 환각을 방지하는 가드레일(Guardrails)과 개인정보 마스킹 파이프라인 검증이 필수입니다.",
                    "target_role": "AI 서비스 개발자 / 컴플라이언스 엔지니어"
                }
            elif "스타트업" in text or "창업" in text or "글로벌" in text:
                return {
                    "insight": f"'{title[:20]}...' 글로벌 확장 국면에서는 멀티 리전 레이턴시 최소화를 위한 글로벌 CDN 및 서버리스 Edge 아키텍처 설계가 비즈니스 성패를 결정합니다.",
                    "target_role": "풀스택 / 글로벌 플랫폼 엔지니어"
                }
            else:
                return {
                    "insight": f"'{title[:20]}...'와 관련된 디지털 전환(DX) 프로젝트에서는 레거시 시스템과의 연동 안정성과 점진적 마이그레이션(Strangler Fig 패턴) 전략이 중요합니다.",
                    "target_role": "시스템 엔지니어 / IT 기획"
                }

        # 2. 클라우드 아키텍처 (Cloud / AWS / Serverless / FinOps)
        elif category == "클라우드 아키텍처":
            if "serverless" in text or "lambda" in text or "서버리스" in text:
                return {
                    "insight": f"'{title[:20]}...' 환경에서는 트래픽 급증 시의 콜드 스타트를 완화하기 위한 프로비저닝된 동시성 설정과 RDS Proxy 커넥션 풀링 최적화가 필수적입니다.",
                    "target_role": "클라우드 / 백엔드 엔지니어"
                }
            elif "비용" in text or "finops" in text or "최적화" in text:
                return {
                    "insight": f"'{title[:20]}...'와 같은 인프라 운영에서는 리소스 태깅 자동화와 Spot/Graviton 인스턴스 전환을 통한 FinOps 비용 절감 및 유휴 자원 회수가 핵심 경쟁력입니다.",
                    "target_role": "Cloud Architect / DevOps"
                }
            else:
                return {
                    "insight": f"'{title[:20]}...' 구축 시 멀티 AZ/리전 고가용성(DR) 구성과 IaC(Terraform) 모듈화를 통한 인프라 불변성(Immutability) 유지가 실무 합격 포인트입니다.",
                    "target_role": "Cloud Architect / DevOps"
                }

        # 3. 인프라/DevOps (K8s, Docker, Linux, CI/CD)
        elif category == "인프라/DevOps":
            if "kubernetes" in text or "k8s" in text or "쿠버네티스" in text:
                return {
                    "insight": f"'{title[:20]}...' 환경에서는 Pod의 Liveness/Readiness Probe 정밀 튜닝과 HPA/KEDA 기반 오토스케일링을 통해 장애 격리 및 무중단 배포를 달성해야 합니다.",
                    "target_role": "DevOps / SRE 엔지니어"
                }
            elif "ci/cd" in text or "배포" in text or "파이프라인" in text:
                return {
                    "insight": f"'{title[:20]}...' 파이프라인에서는 카나리(Canary) 배포와 ArgoCD 기반 GitOps를 통해 장애 발생 시 1분 내 자동 롤백되는 가드레일을 확보하는 것이 핵심입니다.",
                    "target_role": "DevOps / 빌드 엔지니어"
                }
            else:
                return {
                    "insight": f"'{title[:20]}...'와 같은 대규모 트래픽 분산 환경에서는 분산 트레이싱(OpenTelemetry)과 Kafka 완충 큐를 통해 병목 구간을 빠르게 격리하는 설계가 필수적입니다.",
                    "target_role": "인프라 / SRE 엔지니어"
                }

        # 4. 보안/침해사고 (Security, CVE, Ransomware, Hack)
        elif category == "보안/침해사고":
            if "cve" in text or "취약점" in text or "해킹" in text:
                return {
                    "insight": f"'{title[:20]}...' 취약점 대응에서는 SBOM(소프트웨어 자재명세서) 기반 취약점 전수 스캔과 mTLS 기반 제로트러스트 심층 방어가 최우선 방어선입니다.",
                    "target_role": "보안 엔지니어 / 인프라 담당자"
                }
            elif "개인정보" in text or "유출" in text or "인증" in text:
                return {
                    "insight": f"'{title[:20]}...' 관련 보안 사고 방지를 위해 DB 컬럼 단위의 암호화, 최소 권한 원칙 IAM, 불변 WORM 스토리지 백업 정책을 결합한 격리가 필수적입니다.",
                    "target_role": "보안 / 클라우드 엔지니어"
                }
            else:
                return {
                    "insight": f"'{title[:20]}...' 보안 전략에서는 침입 탐지(IDS/IPS) 로그의 실시간 SIEM 상관분석과 사고 발생 시 침해 호스트의 네트워크 자동 격리(SOAR)가 핵심입니다.",
                    "target_role": "보안 관제 / 엔지니어"
                }

        # 5. AI/머신러닝 (AI, LLM, Agent, MLOps)
        else:
            if "에이전트" in text or "agent" in text:
                return {
                    "insight": f"'{title[:20]}...'와 같은 AI 에이전트 구축 시에는 Tool-use 피드백 루프의 무한 루프를 방지하는 최대 홉 수 제한과 샌드박스 실행 격리, Human-in-the-loop 검증이 필수입니다.",
                    "target_role": "AI 엔지니어 / 백엔드 개발자"
                }
            elif "서빙" in text or "추론" in text or "반도체" in text or "gpu" in text:
                return {
                    "insight": f"'{title[:20]}...' 환경에서는 vLLM PagedAttention 메모리 최적화와 FP8/INT4 양자화를 통해 GPU 서빙 비용을 절감하고 Throughput을 극대화하는 엔지니어링이 핵심입니다.",
                    "target_role": "MLOps / AI 서빙 엔지니어"
                }
            else:
                return {
                    "insight": f"'{title[:20]}...' 도메인에서는 하이브리드 검색(BM25 + Dense) RAG 파이프라인과 Re-ranking 모델을 결합하여 환각 현상을 최소화하는 정밀 튜닝이 관건입니다.",
                    "target_role": "AI/ML 개발자 / 데이터 엔지니어"
                }

    def enrich_insights_with_llm(self, articles: List[Dict]) -> None:
        """
        Gemini API를 활용하여 수집된 각 기사마다 완전히 고유한 실무 기술 면접 인사이트를 일괄 도출
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
            if os.path.exists(env_file):
                try:
                    with open(env_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("GEMINI_API_KEY="):
                                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                                break
                except Exception:
                    pass

        if not api_key:
            logging.info("Gemini API key not found. Using advanced template insight engine.")
            return

        # 전체 기사 중 최신 30개 기사에 대해 집중적으로 고유 LLM 인사이트 생성
        target_articles = articles[:30]
        batch_size = 5
        import time

        for i in range(0, len(target_articles), batch_size):
            batch = target_articles[i:i + batch_size]
            prompt = (
                "너는 IT 대기업 10년 차 수석 아키텍트이자 시니어 기술 면접관이야.\n"
                "아래 기사 목록 각각에 대해, 해당 기사의 구체적인 기술 내용과 맥락을 바탕으로 주니어/시니어 개발자가 기술 면접이나 실무에서 어필할 수 있는 '고유한 실무 핵심 인사이트(interview_insight)' 1~2문장과 '추천 대상 직무(target_role)'를 도출해 줘.\n\n"
                "규칙:\n"
                "1. 모든 기사의 인사이트가 완전히 달라야 하며, 해당 기사의 구체적인 기술명/사례를 언급할 것.\n"
                "2. 뻔한 일반론이 아니라 실무 엔지니어링 관점(아키텍처, 트레이드오프, 성능 최적화, 장애 대응, 보안 격리 등)에서 작성할 것.\n"
                "3. 반드시 아래와 같은 순수 JSON 배열 형식으로만 응답할 것:\n"
                "[{\"index\": 0, \"insight\": \"...\", \"target_role\": \"...\"}, ...]\n\n"
                "기사 목록:\n"
            )
            for idx, a in enumerate(batch):
                prompt += f"{idx}. 제목: {a.get('title')}\n   카테고리: {a.get('category')}\n   내용: {a.get('summary')}\n\n"

            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                data = json.dumps({
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"response_mime_type": "application/json"}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                resp = urllib.request.urlopen(req, timeout=30)
                res_json = json.loads(resp.read().decode("utf-8"))
                text_out = res_json["candidates"][0]["content"]["parts"][0]["text"]
                results = json.loads(text_out)
                for r in results:
                    idx = r.get("index")
                    if idx is not None and 0 <= idx < len(batch):
                        if r.get("insight"):
                            batch[idx]["interview_insight"] = r["insight"].strip()
                        if r.get("target_role"):
                            batch[idx]["target_role"] = r["target_role"].strip()
                logging.info(f"✅ Generated {len(results)} unique LLM insights for batch {i // batch_size + 1}")
                time.sleep(1) # API Rate Limit 방어
            except Exception as e:
                logging.warning(f"⚠️ Failed to generate LLM insights for batch {i}: {e}")

    def process(self, raw_item: dict) -> Optional[dict]:
        title = raw_item.get("title", "").strip()
        link = raw_item.get("link", "").strip()
        published = raw_item.get("published", "")
        source = raw_item.get("source", "Unknown")
        raw_desc = raw_item.get("description", "")

        clean_desc = self.clean_html(raw_desc)
        combined_text = f"{title} {clean_desc}"

        # 비IT 및 무관한 기사 필터링
        if not self.is_relevant_it_article(title, clean_desc):
            return None

        category = self.classify_category(combined_text, raw_item.get("default_category", "IT 트렌드"))
        keywords = self.extract_keywords(combined_text)
        prep_data = self.generate_key_insight(category, title, clean_desc)

        return {
            "title": title,
            "link": link,
            "source": source,
            "published": published,
            "category": category,
            "summary": clean_desc[:200] + ("..." if len(clean_desc) > 200 else ""),
            "keywords": keywords,
            "interview_insight": prep_data["insight"],
            "target_role": prep_data["target_role"],
            "raw_snippet": clean_desc[:300]
        }
