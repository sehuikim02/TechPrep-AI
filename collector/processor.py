import re
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
        기술 트렌드 기사에서 실무 핵심 인사이트 및 주요 엔지니어링 포인트를 도출
        """
        text = f"{title} {content}".lower()

        # 1. IT 트렌드 (사회 전반의 IT 서비스, 디지털 신원, 플랫폼 규제, 스마트워크)
        if category == "IT 트렌드":
            if "신분증" in text or "인증" in text or "did" in text:
                return {
                    "insight": "중앙 집중형 DB 유출 위험을 줄이고 사용자 자기주권 신원(SSI)을 보장하는 블록체인/DID 기반 아키텍처가 공공·금융 전반으로 일상화되고 있습니다. 개인키 분실 시 소셜 복구 및 영지식 증명(ZKP)을 통한 프라이버시 보호가 기술적 핵심 과제입니다.",
                    "target_role": "플랫폼 / 서비스 엔지니어"
                }
            elif "기본법" in text or "규제" in text or "윤리" in text:
                return {
                    "insight": "AI 기본법 입법과 함께 대고객 서비스의 투명성, 개인정보 비식별화(마스킹) 파이프라인, 그리고 딥페이크 및 편향 출력을 방지하는 가드레일(Guardrails) 컴플라이언스 체계 구축이 엔터프라이즈의 필수 요건으로 떠올랐습니다.",
                    "target_role": "IT 기획 / AI 서비스 개발자"
                }
            else:
                return {
                    "insight": "원격 근무의 정착으로 단순 사설망(VPN)을 넘어선 제로트러스트 네트워크 액세스(ZTNA)와 가상 데스크톱(VDI), 세분화된 SSO/MFA 통합 정책을 통해 보안성과 생산성을 동시에 확보하는 추세입니다.",
                    "target_role": "시스템 엔지니어 / IT 기획"
                }

        # 2. 클라우드 아키텍처 (Cloud / AWS / Serverless / FinOps)
        elif category == "클라우드 아키텍처":
            if "serverless" in text or "lambda" in text or "서버리스" in text:
                return {
                    "insight": "가변적인 트래픽 대응 시 비용 효율성이 뛰어나지만, 콜드 스타트 지연과 상태 비저장(Stateless) 특성을 감안해 프로비저닝된 동시성 설정, RDS Proxy를 통한 DB 커넥션 풀링 최적화가 필수적입니다.",
                    "target_role": "클라우드 / 백엔드 엔지니어"
                }
            else:
                return {
                    "insight": "단일 벤더 종속(Lock-in) 방지와 고가용성(DR)을 위해 멀티클라우드 도입이 늘고 있으나, Egress 네트워크 비용과 보안 정책 일원화의 복잡성이 커집니다. 테라폼 모듈화와 FinOps 태깅 정책이 실무 성공의 핵심입니다.",
                    "target_role": "Cloud Architect / DevOps"
                }

        # 3. 인프라/DevOps (K8s, Docker, Linux, CI/CD)
        elif category == "인프라/DevOps":
            if "kubernetes" in text or "k8s" in text or "쿠버네티스" in text:
                return {
                    "insight": "쿠버네티스 1.32의 인플레이스(In-place) 파드 리소스 변경 및 향상된 메모리 매니저를 통해 무중단 수직 스케일링이 한층 유연해졌습니다. 노드 장애 시 파드 퇴출(Eviction)과 PDB 정책 설정이 서비스 가용성을 좌우합니다.",
                    "target_role": "DevOps / SRE 엔지니어"
                }
            else:
                return {
                    "insight": "대규모 트래픽 환경에서는 단순 인프라 증설보다 Prometheus/Grafana 지표 수집, 분산 트레이싱, Kafka 메시지 큐 완충을 통해 병목 구간(Bottleneck)을 격리하고 부하를 분산시키는 설계가 결정적입니다.",
                    "target_role": "인프라 / SRE 엔지니어"
                }

        # 4. 보안/침해사고 (Security, CVE, Ransomware, Hack)
        elif category == "보안/침해사고":
            if "openssh" in text or "cve" in text or "취약점" in text:
                return {
                    "insight": "원격 코드 실행(RCE) 취약점 발생 시 영향도 패키지 전수 조사와 즉각적인 인바운드 보안그룹/방화벽 포트 격리(VPN 경유 필수화)가 최우선 조치입니다. 무중단 롤링 패치와 침입 탐지 로그 감시가 병행되어야 합니다.",
                    "target_role": "보안 엔지니어 / 인프라 담당자"
                }
            else:
                return {
                    "insight": "랜섬웨어가 백업 스토리지까지 암호화하는 이중 갈취 공격이 보편화됨에 따라, WORM(Write Once Read Many) 불변 정책, 오프사이트 백업, 그리고 최소 권한 기반의 제로트러스트 IAM 격리가 필수 방어선입니다.",
                    "target_role": "보안 / 클라우드 엔지니어"
                }

        # 5. AI/머신러닝 (AI, LLM, Agent, MLOps)
        else:
            if "에이전트" in text or "agent" in text:
                return {
                    "insight": "자율형 AI 에이전트는 기획(Planning)-도구 사용(Tool-use)-피드백 루프를 스스로 실행하므로, 예측 불가능한 무한 루프를 막기 위한 최대 홉 수 제한, 샌드박스 실행 격리, 사람 승인(Human-in-the-loop) 가드레일이 핵심입니다.",
                    "target_role": "AI 엔지니어 / 백엔드 개발자"
                }
            else:
                return {
                    "insight": "대규모 모델 서빙 환경에서는 하이브리드 검색(키워드+벡터) RAG 파이프라인과 vLLM PagedAttention 메모리 최적화, INT8/FP4 양자화를 통해 GPU 비용을 줄이고 서빙 처리량(Throughput)을 극대화해야 합니다.",
                    "target_role": "AI/ML 개발자 / MLOps"
                }

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
