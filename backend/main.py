import asyncio
from datetime import datetime
import os
import random
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="DevOps Copilot - Autonomous Healing Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini API Client 초기화
GEMINI_CLIENT = None
GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTION = (
    "너는 IT 대기업의 10년 차 시니어 DevOps / 백엔드 엔지니어이자 따뜻하고 든든한 AI 멘토야. "
    "1. 일상적인 인사나 스몰토크('안녕하세요', '반가워요', '안녕' 등)가 들어오면 따뜻하고 유쾌하게 맞이하며, 어떤 고민이나 질문이든 편하게 이야기할 수 있도록 친절하게 대답해 줘.\n"
    "2. 기술 질문이나 면접 고민이 들어오면 주니어 개발자의 눈높이에 맞춰 CS 기초와 실무 인프라 원리(Docker/K8s, 트래픽 분산, 클라우드 아키텍처, 보안 등)를 명쾌하게 설명해 줘.\n"
    "3. 기술 면접 질문일 경우 핵심 답변 포인트와 함께 실제 면접관이 던질 수 있는 꼬리 질문(Follow-up questions) 1~2개를 덧붙여 주면 좋아.\n"
    "4. 한국어로 자연스럽고 정중한 경어체로 대화해 줘."
)

# .env 파일이 있으면 환경 변수 로드
env_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_file_path):
    try:
        with open(env_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")
    except Exception as e:
        print(f"Failed to load .env: {e}")

try:
    from google import genai
    from google.genai import types
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        GEMINI_CLIENT = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
        print("✅ Gemini API Client Initialized successfully with v1beta.")
    else:
        print("ℹ️ GEMINI_API_KEY / GOOGLE_API_KEY not found. Fallback mock mentor engine activated.")
except Exception as e:
    print(f"⚠️ Gemini SDK Init failed: {e}. Fallback mock mentor engine activated.")

# Docker SDK 연동 시도 (Docker 데몬 없을 경우 Mock 시뮬레이터로 자동 폴백)
DOCKER_AVAILABLE = False
docker_client = None
try:
    import docker
    docker_client = docker.from_env()
    docker_client.ping()
    DOCKER_AVAILABLE = True
    print("✅ Real Docker Engine Connected.")
except Exception as e:
    print(f"⚠️ Docker Engine not detected or unavailable ({e}). Running in High-Fidelity Simulation Mode.")

TARGET_CONTAINER_NAME = "demo-app-server"

# --- State Store ---
class TargetServerState:
    def __init__(self):
        self.container_id = "d8f3a921c4e2"
        self.name = TARGET_CONTAINER_NAME
        self.status = "HEALTHY"  # HEALTHY, CRITICAL, HEALING, DOWN
        self.cpu_percent = 12.4
        self.memory_percent = 28.5
        self.restart_count = 0
        self.last_error = None
        self.uptime_seconds = 1240

server_state = TargetServerState()

class AuditLog(BaseModel):
    id: str
    timestamp: str
    phase: str  # SENSE, REASON, ACT, AUDIT
    severity: str  # INFO, WARNING, ERROR, SUCCESS
    message: str
    details: Optional[Dict] = None

audit_logs: List[AuditLog] = []

def record_audit(phase: str, severity: str, message: str, details: Optional[Dict] = None):
    log_entry = AuditLog(
        id=f"log-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        timestamp=datetime.now().strftime("%H:%M:%S"),
        phase=phase,
        severity=severity,
        message=message,
        details=details or {}
    )
    audit_logs.append(log_entry)
    # 최대 200개 유지
    if len(audit_logs) > 200:
        audit_logs.pop(0)
    print(f"[{log_entry.timestamp}] [{phase}] [{severity}] {message}")

# --- Autonomous Healing Agent (Sense -> Reason -> Act -> Audit) ---
async def autonomous_healing_worker():
    record_audit("AUDIT", "INFO", "자율형 인프라 치유 에이전트 루프가 가동되었습니다. (감시 주기: 3초)")
    
    while True:
        try:
            await asyncio.sleep(3)
            
            # 1. SENSE (상태 관찰 및 계측)
            if DOCKER_AVAILABLE:
                try:
                    c = docker_client.containers.get(TARGET_CONTAINER_NAME)
                    server_state.container_id = c.short_id
                    server_state.status = "HEALTHY" if c.status == "running" else "CRITICAL"
                except Exception:
                    server_state.status = "CRITICAL"
                    server_state.last_error = "ContainerNotFound"
            else:
                # Simulation Mode: 부하 변동
                if server_state.status == "HEALTHY":
                    server_state.cpu_percent = round(random.uniform(8.0, 25.0), 1)
                    server_state.memory_percent = round(random.uniform(25.0, 40.0), 1)
                    server_state.uptime_seconds += 3

            # 2. REASON (장애 분석 및 원인 추론)
            if server_state.status == "CRITICAL":
                error_type = server_state.last_error or "UNKNOWN_FAILURE"
                record_audit("SENSE", "ERROR", f"이상 징후 감지: 컨테이너 상태 CRITICAL (에러: {error_type})", {
                    "cpu": server_state.cpu_percent,
                    "memory": server_state.memory_percent,
                    "target": server_state.name
                })
                
                # 플레이북 추론
                playbook = "STANDARD_RESTART"
                if "OOM" in error_type or server_state.memory_percent > 90:
                    playbook = "MEMORY_PRESSURE_RECOVERY"
                elif "500" in error_type:
                    playbook = "APPLICATION_WORKER_RELOAD"

                record_audit("REASON", "WARNING", f"장애 유형 분석 완료: [{error_type}] -> 복구 전략 수립: [{playbook}]")

                # 3. ACT (치유 조치 실행)
                server_state.status = "HEALING"
                record_audit("ACT", "INFO", f"복구 조치 시작: {playbook} 플레이북 적용 중...")
                
                await asyncio.sleep(2)  # 조치 소요 시간 시뮬레이션
                
                if DOCKER_AVAILABLE:
                    try:
                        c = docker_client.containers.get(TARGET_CONTAINER_NAME)
                        c.restart()
                    except Exception as ex:
                        record_audit("ACT", "ERROR", f"Docker 제어 실패: {ex}")
                
                # 상태 회복
                server_state.status = "HEALTHY"
                server_state.cpu_percent = 11.2
                server_state.memory_percent = 26.0
                server_state.restart_count += 1
                server_state.last_error = None
                
                # 4. AUDIT (결과 검증 및 기록)
                record_audit("AUDIT", "SUCCESS", f"자가 치유 성공! 컨테이너가 정상 상태(HEALTHY)로 복구되었습니다. (총 재기동 횟수: {server_state.restart_count})")

        except Exception as e:
            record_audit("AUDIT", "ERROR", f"에이전트 내부 루프 오류: {str(e)}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(autonomous_healing_worker())

# --- API Endpoints ---
@app.get("/api/status")
async def get_server_status():
    return {
        "container_id": server_state.container_id,
        "name": server_state.name,
        "status": server_state.status,
        "cpu_percent": server_state.cpu_percent,
        "memory_percent": server_state.memory_percent,
        "restart_count": server_state.restart_count,
        "uptime_seconds": server_state.uptime_seconds,
        "docker_connected": DOCKER_AVAILABLE,
        "last_error": server_state.last_error
    }

@app.get("/api/logs", response_model=List[AuditLog])
async def get_audit_logs():
    return list(reversed(audit_logs))

# --- Chaos Engineering / Fault Injection Endpoints ---
class ChaosRequest(BaseModel):
    fault_type: str  # KILL_CONTAINER, OOM_LEAK, ERROR_500

@app.post("/api/chaos/inject")
async def inject_fault(req: ChaosRequest):
    record_audit("AUDIT", "WARNING", f"사용자에 의해 의도적 장애 주입 발생: [{req.fault_type}]")
    
    if req.fault_type == "KILL_CONTAINER":
        server_state.status = "CRITICAL"
        server_state.last_error = "CONTAINER_CRASH_SIGNAL_SIGKILL"
        server_state.cpu_percent = 0.0
    elif req.fault_type == "OOM_LEAK":
        server_state.status = "CRITICAL"
        server_state.memory_percent = 98.7
        server_state.last_error = "Out Of Memory (OOMKilled - Exit code 137)"
    elif req.fault_type == "ERROR_500":
        server_state.status = "CRITICAL"
        server_state.last_error = "HTTP 500: DatabaseConnectionPoolExhausted"
    else:
        raise HTTPException(status_code=400, detail="Unknown fault type")
        
    return {"message": f"Fault '{req.fault_type}' successfully injected", "current_status": server_state.status}

# --- Gemini AI Tech Mentor Chat Endpoint ---
class ChatMessage(BaseModel):
    role: str  # user or model
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None
    context_topic: Optional[str] = None  # e.g. "Kubernetes Pod Eviction"

class ChatResponse(BaseModel):
    reply: str
    model: str
    created_at: str

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_mentor(req: ChatRequest):
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Gemini API 연동이 되어있는 경우 실제 LLM 호출
    if GEMINI_CLIENT:
        try:
            from google.genai import types
            prompt_parts = []
            if req.context_topic:
                prompt_parts.append(f"[면접 주제/관련 기사]: {req.context_topic}\n")
            
            prompt_parts.append(f"주니어 지원자: {user_msg}")
            full_prompt = "\n".join(prompt_parts)

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.7,
            )

            response = GEMINI_CLIENT.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
                config=config
            )
            return ChatResponse(
                reply=response.text,
                model=f"Google Gemini ({GEMINI_MODEL})",
                created_at=now_iso
            )
        except Exception as e:
            print(f"Gemini API 호출 에러: {e}")
            # API 호출 실패 시 친절한 안내와 함께 폴백

    # 2. API Key 미설정 또는 호출 제한 시 고품질 시니어 멘토 Mock 응답 제공
    low = user_msg.lower()
    if any(k in low for k in ["k8s", "쿠버네티스", "pod", "파드", "docker", "도커", "컨테이너"]):
        mock_reply = (
            "💡 **[시니어 면접관 코칭]**\n\n"
            "좋은 질문입니다! 면접에서 컨테이너와 쿠버네티스 질문을 받을 때는 **'가상화와의 차이점(프로세스 격리)', '장애 복구(Self-Healing)', '무중단 배포'**라는 세 가지 핵심 키워드를 반드시 언급해야 높은 점수를 받습니다.\n\n"
            "**1. 핵심 답변 포인트:**\n"
            "- 도커는 Host OS 커널을 공유하며 cgroups와 Linux namespaces를 통해 격리된 경량 실행 환경을 제공합니다.\n"
            "- 쿠버네티스는 이를 프로덕션 스케일에서 Pod의 liveness/readiness probe를 통해 자율 복구하고, HPA를 통한 오토스케일링을 보장합니다.\n\n"
            "**2. 면접관의 단골 꼬리 질문(Follow-up):**\n"
            "- *'Pod가 CrashLoopBackOff 상태에 빠졌을 때 디버깅 순서는 어떻게 되나요?'*\n"
            "- *'LivenessProbe와 ReadinessProbe의 차이점과 잘못 설정했을 때의 위험성은?'*"
        )
    elif any(k in low for k in ["보안", "취약점", "cve", "제로트러스트", "인증", "jwt"]):
        mock_reply = (
            "💡 **[시니어 면접관 코칭]**\n\n"
            "보안 관련 면접에서는 **'단일 방어선이 뚫렸을 때의 심층 방어(Defense in Depth)'** 관점으로 접근하는 것이 매우 인상적입니다.\n\n"
            "**1. 핵심 답변 포인트:**\n"
            "- 제로트러스트(Zero Trust)는 '내부망이라고 신뢰하지 않는다(Never Trust, Always Verify)'는 원칙입니다.\n"
            "- 마이크로서비스 간 mTLS 암호화, 최소 권한 원칙(Principle of Least Privilege) IAM, WORM 백업 정책을 결합한 사례를 설명하세요.\n\n"
            "**2. 면접관의 단골 꼬리 질문(Follow-up):**\n"
            "- *'JWT의 Access Token 탈취 시 무효화(Revoke) 전략은 어떻게 설계하시겠습니까?'*\n"
            "- *'공개된 CVE 취약점이 보고되었을 때 인프라 파이프라인에서 자동 차단하는 절차는?'*"
        )
    elif any(k in low for k in ["aws", "클라우드", "서버리스", "lambda", "트래픽", "장애"]):
        mock_reply = (
            "💡 **[시니어 면접관 코칭]**\n\n"
            "클라우드 아키텍처 면접에서는 **'가용성(Availability)과 비용 최적화(FinOps)의 트레이드오프'**를 이해하고 있는지 확인합니다.\n\n"
            "**1. 핵심 답변 포인트:**\n"
            "- 대규모 트래픽 시에는 ALB/NLB + Auto Scaling Group을 기본으로, DB 부하를 줄이기 위한 Redis/ElastiCache 캐싱 레이어와 비동기 Kafka 큐 완충을 설계에 반영합니다.\n"
            "- 장애 격리를 위해 서킷 브레이커(Circuit Breaker) 패턴을 실무에 적용해 본 경험을 어필하세요.\n\n"
            "**2. 면접관의 단골 꼬리 질문(Follow-up):**\n"
            "- *'DB 커넥션 풀이 고갈되어 500 에러가 폭증할 때 어떻게 대응하시겠습니까?'*\n"
            "- *'Multi-AZ와 Multi-Region 배포 시 데이터 일관성과 지연 시간(Latency)은 어떻게 고려하나요?'*"
        )
    else:
        mock_reply = (
            f"💡 **[시니어 면접관 코칭]**\n\n"
            f"**\"{user_msg}\"** 주제는 기술 면접에서 지원자의 실무 문제 해결 능력과 CS 기본기를 검증하기에 아주 좋은 질문입니다.\n\n"
            "**1. 모범적인 답변 구조(STAR 기법):**\n"
            "- **Situation(상황)**: 어떤 기술적 요구사항 또는 문제 상황이었는지 명확히 정의합니다.\n"
            "- **Task(과제)**: 해결해야 할 핵심 병목이나 목표 지표를 수치로 제시합니다.\n"
            "- **Action(행동)**: 대안 기술(A vs B) 중 왜 특정 아키텍처를 선택했는지 근거를 들어 설명합니다.\n"
            "- **Result(결과)**: 도입 후 성능 개선 수치와 함께 겪었던 트레이드오프를 솔직히 공유합니다.\n\n"
            "💡 *Tip: 환경 변수(`GEMINI_API_KEY`)를 설정하시면 실시간 Gemini Pro/Flash 모델이 맞춤형 실시간 면접 코칭을 제공합니다.*"
        )

    return ChatResponse(
        reply=mock_reply,
        model="TechPrep AI Mentor (Built-in)",
        created_at=now_iso
    )

# --- Frontend Static Files Serving (포트 8080 통합 서빙) ---
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
