import urllib.parse

# 수집 대상 채널 (국내 IT 전문 미디어 + 글로벌 개발자/클라우드 소스)
MEDIA_FEEDS = [
    # 1. 국내 대표 IT 전문 미디어
    {
        "name": "전자신문 (AI·SW)",
        "url": "http://rss.etnews.com/04.xml",
        "default_category": "AI/머신러닝"
    },
    {
        "name": "전자신문 (보안)",
        "url": "http://rss.etnews.com/04045.xml",
        "default_category": "보안/침해사고"
    },
    {
        "name": "전자신문 (정책·사회)",
        "url": "http://rss.etnews.com/22.xml",
        "default_category": "IT 트렌드"
    },
    {
        "name": "IT조선",
        "url": "https://it.chosun.com/rss/allArticle.xml",
        "default_category": "IT 트렌드"
    },
    {
        "name": "IT동아",
        "url": "https://it.donga.com/feeds/rss/",
        "default_category": "IT 트렌드"
    },
    # 2. 글로벌 클라우드 & 쿠버네티스 & 인프라 공식 피드
    {
        "name": "AWS Architecture & News",
        "url": "https://aws.amazon.com/blogs/aws/feed/",
        "default_category": "클라우드 아키텍처"
    },
    {
        "name": "Kubernetes Official Blog",
        "url": "https://kubernetes.io/feed.xml",
        "default_category": "인프라/DevOps"
    },
    # 3. 글로벌 보안 & 빅테크
    {
        "name": "The Hacker News",
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "default_category": "보안/침해사고"
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "default_category": "AI/머신러닝"
    }
]

FEEDS = MEDIA_FEEDS

# 5대 핵심 도메인 카테고리 정의
CATEGORY_KEYWORDS = {
    "클라우드 아키텍처": [
        "aws", "azure", "gcp", "cloud", "serverless", "lambda", "ec2", "s3", 
        "vpc", "iam", "hybrid cloud", "multi cloud", "클라우드", "온프레미스", 
        "csp", "saas", "paas", "finops", "비용 최적화"
    ],
    "인프라/DevOps": [
        "kubernetes", "k8s", "docker", "container", "devops", "ci/cd", "linux", 
        "terraform", "ansible", "istio", "helm", "networking", "인프라", "서버", 
        "가상화", "datacenter", "데이터센터", "sre", "모니터링", "prometheus", "grafana",
        "트래픽", "로드밸런서", "kafka"
    ],
    "보안/침해사고": [
        "security", "vulnerability", "malware", "ransomware", "cve", "cyberattack", 
        "phishing", "zero-day", "hacker", "보안", "취약점", "해킹", "악성코드", 
        "침해사고", "개인정보보호", "사용자 인증", "jwt", "ddos", "권한 탈취", "제로트러스트", "mfa"
    ],
    "AI/머신러닝": [
        "ai", "llm", "gpt", "gemini", "claude", "machine learning", "deep learning", 
        "neural network", "인공지능", "머신러닝", "딥러닝", "생성형 ai", "ai 에이전트", "transformer",
        "rag", "vector db", "prompt", "파인튜닝", "gpu", "vllm"
    ],
    "IT 트렌드": [
        "it 트렌드", "빅테크", "개발자 채용", "디지털 전환", "dx", "ax", 
        "테크 스타트업", "소프트웨어 산업", "반도체 생태계", "테크 트렌드",
        "오픈소스", "it 거버넌스"
    ]
}

# 수집 제외 불필요 키워드 (학습지, 일반 아동/초등 교육, 단순 가전/PC케이스, 포토 뉴스 등)
EXCLUDE_KEYWORDS = [
    "구몬", "눈높이", "씽크빅", "학습지", "유아·초등", "자녀 학습", "신학기", "겨울방학", "여름방학",
    "교과 학습", "학부모", "수능", "모의고사", "입시", "학원가", "어린이집", "유치원",
    "케이스 출시", "pc 케이스", "곡면 유리", "선풍기", "가습기", "무드등", "안마의자",
    "[포토]", "[인사]", "[부고]", "[동정]", "결혼식", "광고대행사 인수"
]
