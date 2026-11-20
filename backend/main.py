import asyncio
from datetime import datetime
import json
import os
import random
import re
import uuid
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Header, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.database import (
    init_db,
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_user_by_username,
    create_user,
    update_user_api_status,
    list_all_users,
    record_login_log,
    record_usage_log,
    get_login_logs,
    get_usage_logs,
    get_security_and_usage_stats,
    DB_PATH
)

app = FastAPI(title="TechPrep-AI & DevOps Copilot API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini API Client 초기화
GEMINI_CLIENT = None
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash"]
GEMINI_KEY_STATUS = "UNCONFIGURED"  # HEALTHY, INVALID, UNCONFIGURED

SYSTEM_INSTRUCTION = (
    "너는 IT 대기업의 10년 차 시니어 DevOps / 백엔드 엔지니어이자 다정하고 지혜로운 AI 커리어 & 기술 멘토야.\n"
    "1. [일상 대화, 스몰토크 & 감정 공감]:\n"
    "   - '오늘 날씨 어때?', '점심 뭐 먹을까?', '힘들다', '안녕' 같은 일상 대화나 스몰토크가 들어오면 유쾌하고 친근한 선배처럼 자연스럽게 대답해 줘.\n"
    "   - 날씨나 일상 질문에도 막힘없이 편안하게 답변하고, 따뜻한 응원을 덧붙여 줘.\n"
    "2. [진로 / 취업 / 고민 상담]:\n"
    "   - '어떤 걸 해야 할지 모르겠어요', '신입이라 어떤 걸 어필해야 할까?', '비전공자인데 취업할 수 있을까?', '포트폴리오는 어떻게 꾸밀까?' 같은 막막함이나 진로 고민이 들어오면, 선배의 시선에서 깊이 공감하고 현실적이며 구체적인 액션 플랜(공부 방향, 관심 분야 좁히기, 작은 프로젝트 시작 등)을 따뜻하게 조언해 줘.\n"
    "   - 신입 개발자에게는 완성된 화려함보다 '탄탄한 CS 기본기', '문제 해결 집요함(디버깅 스토리)', '코드 품질과 테스트에 대한 태도', '팀원과의 원활한 소통/협업 능력'이 핵심 어필 포인트임을 친절하게 짚어줘.\n"
    "3. [RAG 실시간 이슈 활용]:\n"
    "   - 질문이 실제 기술 트렌드나 IT 동향과 관련이 있고 컨텍스트(RAG Context)가 주어지면 적극적으로 인용하여 최신 업계 트렌드와 연결해 줘.\n"
    "   - 일상 대화나 순수 고민 상담, 날씨 질문 등 기사와 무관한 내용일 때는 절대 기사나 RAG 내용을 억지로 언급하지 말고 질문자의 대화에만 온전히 집중해 줘.\n"
    "4. [기술 면접 코칭]:\n"
    "   - 구체적인 기술 질문이 들어오면 주니어 눈높이에 맞춰 명쾌하게 원리를 설명하고, 실무 관점의 핵심 포인트 및 면접관이 던질 수 있는 꼬리 질문을 덧붙여 줘.\n"
    "5. 한국어로 정중하고 따뜻하며 생동감 있는 경어체로 대화해 줘."
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
        GEMINI_KEY_STATUS = "ACTIVE"
        print("✅ Gemini API Client Initialized successfully with v1beta.")
    else:
        GEMINI_KEY_STATUS = "UNCONFIGURED"
        print("ℹ️ GEMINI_API_KEY / GOOGLE_API_KEY not found. Fallback mock mentor engine activated.")
except Exception as e:
    GEMINI_KEY_STATUS = "ERROR"
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
                
                await asyncio.sleep(2)
                
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
    init_db()
    asyncio.create_task(autonomous_healing_worker())

# --- Auth Helper Dependencies ---
def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    payload = decode_access_token(token)
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None
    user = get_user_by_username(username)
    return user

def get_current_user_required(authorization: Optional[str] = Header(None)) -> dict:
    user = get_current_user_optional(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다. 유효한 인증 토큰을 전달해 주세요."
        )
    return user

def require_admin_user(current_user: dict = Depends(get_current_user_required)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 전용 기능입니다. 관리자 계정으로 로그인해 주세요."
        )
    return current_user

# --- Authentication Schemas & Endpoints ---
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class UserStatusUpdateRequest(BaseModel):
    username: str
    api_status: str  # pending, approved, blocked

@app.post("/api/auth/register")
async def register(req: RegisterRequest, request: Request):
    username = req.username.strip()
    password = req.password.strip()
    client_ip = get_client_ip(request)

    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="아이디는 최소 3자 이상이어야 합니다.")
    if not password or len(password) < 4:
        raise HTTPException(status_code=400, detail="비밀번호는 최소 4자 이상이어야 합니다.")

    existing = get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="이미 존재하는 아이디입니다.")

    pw_hash = hash_password(password)
    user = create_user(username=username, password_hash=pw_hash, role="user", api_status="pending")
    record_usage_log(username, client_ip, "REGISTER", "SUCCESS", details="New user registered with pending status")

    token = create_access_token({
        "sub": user["username"],
        "role": user["role"],
        "api_status": user["api_status"]
    })

    return {
        "message": "회원가입이 완료되었습니다. 관리자 승인 후 GEMINI AI 챗봇 기능을 사용할 수 있습니다.",
        "user": {
            "username": user["username"],
            "role": user["role"],
            "api_status": user["api_status"]
        },
        "token": token
    }

@app.post("/api/auth/login")
async def login(req: LoginRequest, request: Request):
    username = req.username.strip()
    password = req.password.strip()
    client_ip = get_client_ip(request)

    user = get_user_by_username(username)
    if not user:
        record_login_log(username, client_ip, "FAILED", "UserNotFound")
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    if not verify_password(password, user["password_hash"]):
        record_login_log(username, client_ip, "FAILED", "InvalidPassword")
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    # Record successful login
    record_login_log(username, client_ip, "SUCCESS")

    token = create_access_token({
        "sub": user["username"],
        "role": user["role"],
        "api_status": user["api_status"]
    })

    return {
        "message": "로그인 성공",
        "user": {
            "username": user["username"],
            "role": user["role"],
            "api_status": user["api_status"]
        },
        "token": token
    }

@app.get("/api/auth/me")
async def get_me(authorization: Optional[str] = Header(None)):
    user = get_current_user_optional(authorization)
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user": {
            "username": user["username"],
            "role": user["role"],
            "api_status": user["api_status"]
        }
    }

# --- Admin Dashboard Endpoints ---
@app.get("/api/admin/users")
async def admin_list_users(admin: dict = Depends(require_admin_user)):
    return list_all_users()

@app.post("/api/admin/users/status")
async def admin_update_user_status(req: UserStatusUpdateRequest, admin: dict = Depends(require_admin_user), request: Request = None):
    valid_statuses = ["pending", "approved", "blocked"]
    if req.api_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 상태입니다: {valid_statuses}")
    
    target_user = get_user_by_username(req.username)
    if not target_user:
        raise HTTPException(status_code=404, detail="해당 사용자를 찾을 수 없습니다.")

    if target_user["role"] == "admin" and req.api_status != "approved":
        raise HTTPException(status_code=400, detail="관리자 계정의 권한은 차단하거나 변경할 수 없습니다.")

    ok = update_user_api_status(req.username, req.api_status)
    if not ok:
        raise HTTPException(status_code=500, detail="상태 업데이트에 실패했습니다.")

    client_ip = get_client_ip(request) if request else "unknown"
    record_usage_log(admin["username"], client_ip, "UPDATE_USER_STATUS", "SUCCESS", details=f"Changed {req.username} to {req.api_status}")

    return {
        "success": True,
        "message": f"'{req.username}' 계정의 API 상태가 '{req.api_status}'(으)로 변경되었습니다.",
        "username": req.username,
        "api_status": req.api_status
    }

@app.get("/api/admin/stats")
async def admin_get_stats(admin: dict = Depends(require_admin_user), request: Request = None):
    client_ip = get_client_ip(request) if request else "unknown"
    record_usage_log(admin["username"], client_ip, "DASHBOARD_VIEW", "SUCCESS", details="Admin viewed admin dashboard")

    stats = get_security_and_usage_stats()

    # Gemini API 연동 상태 및 일일 무료 쿼터 추정치
    # Gemini 3.5 Flash / Flash Lite 무료 한도: 보통 하루 1,500 RPD (Requests Per Day) 및 1,000,000 TPM
    daily_call_limit = 1500
    daily_token_limit = 1000000

    total_calls = stats["token_usage"]["total_calls"]
    total_tokens = stats["token_usage"]["total_tokens"]
    remaining_calls = max(0, daily_call_limit - total_calls)
    remaining_tokens = max(0, daily_token_limit - total_tokens)

    stats["gemini_monitoring"] = {
        "api_key_status": GEMINI_KEY_STATUS,
        "primary_model": GEMINI_MODEL,
        "fallback_models": GEMINI_FALLBACK_MODELS,
        "client_initialized": GEMINI_CLIENT is not None,
        "daily_limit_calls": daily_call_limit,
        "remaining_calls_est": remaining_calls,
        "calls_usage_percent": round(min(100.0, (total_calls / daily_call_limit) * 100), 1),
        "daily_limit_tokens": daily_token_limit,
        "remaining_tokens_est": remaining_tokens,
        "tokens_usage_percent": round(min(100.0, (total_tokens / daily_token_limit) * 100), 1),
    }

    return stats

@app.get("/api/admin/logs/login")
async def admin_get_login_logs(limit: int = 50, admin: dict = Depends(require_admin_user)):
    return get_login_logs(limit=limit)

@app.get("/api/admin/logs/usage")
async def admin_get_usage_logs(limit: int = 50, admin: dict = Depends(require_admin_user)):
    return get_usage_logs(limit=limit)

# --- Standard DevOps & Server Endpoints ---
@app.get("/api/status")
async def get_server_status(authorization: Optional[str] = Header(None), request: Request = None):
    user = get_current_user_optional(authorization)
    client_ip = get_client_ip(request) if request else "unknown"
    username = user["username"] if user else "guest"
    record_usage_log(username, client_ip, "DASHBOARD_VIEW", "SUCCESS", details="Viewed infrastructure status")

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

# --- RAG (Retrieval-Augmented Generation) Helper ---
def retrieve_relevant_news(query: str, top_k: int = 3) -> List[Dict]:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_files = [
        os.path.join(base_dir, "jobs_and_trends.json"),
        os.path.join(base_dir, "data", "jobs_and_trends.json"),
        os.path.join(base_dir, "frontend", "jobs_and_trends.json"),
        os.path.join(base_dir, "news.json")
    ]
    articles = []
    for fp in target_files:
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    articles = data.get("articles", [])
                    if articles:
                        break
            except Exception:
                continue

    if not articles:
        return []

    query_tokens = [w.lower() for w in re.findall(r'[A-Za-z0-9가-힣]{2,}', query)]
    stopwords = {
        "어떻게", "알려줘", "알려주세요", "대해서", "질문", "면접", "관련", "설명해줘", "답변", "요령",
        "신입", "개발자", "면접관", "어필", "가장", "좋을까", "좋을까요", "준비", "포트폴리오", "취업", "진로",
        "서울", "날씨", "오늘", "내일", "기온", "어때", "어때요", "어떡", "어떻", "무엇", "어떤", "어떤걸",
        "모르겠", "방황", "불안", "시작", "공부", "방법", "구조", "전략", "방식", "설계", "대규모"
    }
    keywords = [k for k in query_tokens if k not in stopwords]

    daily_weather_patterns = ["날씨", "기온", "비오", "맑", "미세먼지", "안녕", "반가", "하이", "모르겠", "막막", "방황", "어떤걸"]
    if any(p in query.lower() for p in daily_weather_patterns):
        return []

    if not keywords:
        return []

    scored_articles = []
    for item in articles:
        title = item.get("title", "")
        summary = item.get("summary", "") or item.get("raw_snippet", "")
        insight = item.get("interview_insight", "")
        tags = " ".join(item.get("keywords", []))

        score = 0
        matched_kws = 0
        for kw in keywords:
            kw_score = 0
            if kw in title.lower():
                kw_score += 6
            if kw in tags.lower():
                kw_score += 4
            if kw in insight.lower():
                kw_score += 3
            if kw in summary.lower():
                kw_score += 1
            if kw_score > 0:
                matched_kws += 1
                score += kw_score

        if score >= 7 and matched_kws >= 1:
            scored_articles.append((score, item))

    scored_articles.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored_articles[:top_k]]

# --- Anonymous & Authenticated Session Store Helper ---
def get_effective_session_key(current_user: Optional[dict], x_session_id: Optional[str]) -> str:
    if current_user and current_user.get("username"):
        return f"user:{current_user['username']}"
    return x_session_id or "default-session"

# --- Anonymous & Authenticated Session Store ---
session_store: Dict[str, Dict[str, Dict]] = {}

class ChatRequest(BaseModel):
    message: str
    room_id: Optional[str] = None
    context_topic: Optional[str] = None

class ChatResponse(BaseModel):
    room_id: str
    reply: str
    model: str
    created_at: str
    referenced_articles: Optional[List[Dict]] = None

class CreateRoomRequest(BaseModel):
    title: Optional[str] = "새 대화"

@app.get("/api/chats")
async def list_chat_rooms(authorization: Optional[str] = Header(None), x_session_id: Optional[str] = Header(None)):
    current_user = get_current_user_optional(authorization)
    sid = get_effective_session_key(current_user, x_session_id)
    rooms = session_store.get(sid, {})
    result = []
    for rid, rdata in rooms.items():
        result.append({
            "room_id": rid,
            "title": rdata.get("title", "대화방"),
            "updated_at": rdata.get("updated_at", ""),
            "message_count": len(rdata.get("messages", []))
        })
    result.sort(key=lambda x: x["updated_at"], reverse=True)
    return result

@app.post("/api/chats")
async def create_chat_room(req: CreateRoomRequest, authorization: Optional[str] = Header(None), x_session_id: Optional[str] = Header(None)):
    current_user = get_current_user_optional(authorization)
    sid = get_effective_session_key(current_user, x_session_id)
    if sid not in session_store:
        session_store[sid] = {}
    
    room_id = f"room-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session_store[sid][room_id] = {
        "title": req.title or "새 대화",
        "updated_at": now_iso,
        "messages": []
    }
    return {"room_id": room_id, "title": req.title, "created_at": now_iso}

@app.get("/api/chats/{room_id}/messages")
async def get_room_messages(room_id: str, authorization: Optional[str] = Header(None), x_session_id: Optional[str] = Header(None)):
    current_user = get_current_user_optional(authorization)
    sid = get_effective_session_key(current_user, x_session_id)
    rooms = session_store.get(sid, {})
    if room_id not in rooms:
        return []
    return rooms[room_id].get("messages", [])

@app.delete("/api/chats/{room_id}")
async def delete_chat_room(room_id: str, authorization: Optional[str] = Header(None), x_session_id: Optional[str] = Header(None)):
    current_user = get_current_user_optional(authorization)
    sid = get_effective_session_key(current_user, x_session_id)
    if sid in session_store and room_id in session_store[sid]:
        del session_store[sid][room_id]
        return {"success": True, "message": "삭제되었습니다."}
    return {"success": False, "message": "방을 찾을 수 없습니다."}

# --- Core Chat API with GEMINI API KEY Authorization & Token Tracking ---
@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_mentor(
    req: ChatRequest, 
    request: Request,
    x_session_id: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    client_ip = get_client_ip(request)
    current_user = get_current_user_optional(authorization)
    username = current_user["username"] if current_user else "anonymous"

    # [권한 제어]: 오직 관리자(admin)이거나 승인된(approved) 계정만 백엔드의 GEMINI API KEY를 사용 가능
    is_authorized = False
    if current_user:
        if current_user.get("role") == "admin" or current_user.get("api_status") == "approved":
            is_authorized = True

    if not is_authorized:
        # 미승인, 차단, 또는 비로그인 상태
        status_reason = "로그인이 필요합니다."
        if current_user:
            user_status = current_user.get("api_status", "pending")
            if user_status == "pending":
                status_reason = "관리자의 API 사용 승인(pending) 대기 중입니다. 관리자 승인 후 사용 가능합니다."
            elif user_status == "blocked":
                status_reason = "관리자에 의해 API 접근이 차단(blocked)된 계정입니다."

        record_usage_log(
            username=username,
            ip=client_ip,
            action="CHAT_API",
            status="FORBIDDEN",
            details=f"Access denied: {status_reason}"
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"⚠️ GEMINI API 키 사용 권한이 없습니다. {status_reason}"
        )

    sid = get_effective_session_key(current_user, x_session_id)
    if sid not in session_store:
        session_store[sid] = {}

    room_id = req.room_id
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 방이 없으면 자동 생성
    if not room_id or room_id not in session_store[sid]:
        room_id = room_id or f"room-{uuid.uuid4().hex[:8]}"
        initial_title = user_msg[:18] + ("..." if len(user_msg) > 18 else "")
        session_store[sid][room_id] = {
            "title": initial_title,
            "updated_at": now_iso,
            "messages": []
        }
    else:
        if len(session_store[sid][room_id]["messages"]) == 0:
            session_store[sid][room_id]["title"] = user_msg[:18] + ("..." if len(user_msg) > 18 else "")

    # 1. RAG 기사 검색
    retrieved_articles = retrieve_relevant_news(user_msg, top_k=2)
    rag_context_snippets = []
    referenced_meta = []

    for art in retrieved_articles:
        title = art.get("title", "")
        insight = art.get("interview_insight", "")
        summary = art.get("summary", "")
        link = art.get("link", "")
        source = art.get("source", "")
        rag_context_snippets.append(
            f"- 기사 제목: {title} ({source})\n  요약: {summary}\n  실무 핵심 인사이트: {insight}"
        )
        referenced_meta.append({
            "title": title,
            "link": link,
            "source": source,
            "insight": insight
        })

    # 2. Gemini API 호출
    reply_text = ""
    model_name = ""
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    if GEMINI_CLIENT:
        try:
            from google.genai import types
            prompt_parts = []
            if req.context_topic:
                prompt_parts.append(f"[면접 주제/관련 기사]: {req.context_topic}")

            if rag_context_snippets:
                prompt_parts.append(
                    "[시스템 수집 최신 IT 실무 이슈 및 인사이트 (RAG Context)]:\n" +
                    "\n".join(rag_context_snippets) +
                    "\n(위 최신 업계 동향 및 실무 인사이트를 답변에 자연스럽게 녹여내어 신뢰성을 높여주세요.)"
                )

            prev_msgs = session_store[sid][room_id]["messages"][-4:]
            if prev_msgs:
                history_str = "\n".join([f"{'지원자' if m['role']=='user' else '면접관'}: {m['content']}" for m in prev_msgs])
                prompt_parts.append(f"[이전 대화 맥락]:\n{history_str}")

            prompt_parts.append(f"주니어 지원자: {user_msg}")
            full_prompt = "\n\n".join(prompt_parts)

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.7,
            )

            response = None
            used_model = None
            for m in [GEMINI_MODEL] + [mod for mod in GEMINI_FALLBACK_MODELS if mod != GEMINI_MODEL]:
                try:
                    response = GEMINI_CLIENT.models.generate_content(
                        model=m,
                        contents=full_prompt,
                        config=config
                    )
                    if response and response.text:
                        used_model = m
                        reply_text = response.text
                        
                        # Usage metadata 추출
                        if hasattr(response, 'usage_metadata') and response.usage_metadata:
                            prompt_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
                            completion_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
                            total_tokens = getattr(response.usage_metadata, 'total_token_count', 0) or (prompt_tokens + completion_tokens)
                        break
                except Exception as model_err:
                    print(f"Model {m} failed: {model_err}")

            if reply_text:
                model_name = f"Google Gemini ({used_model})" + (" + RAG" if rag_context_snippets else "")
        except Exception as e:
            print(f"Gemini API 호출 에러: {e}")

    if not reply_text:
        # 폴백 모드 (시니어 멘토 내장 엔진)
        low = user_msg.lower()
        rag_note = ""
        if referenced_meta:
            rag_note = f"\n\n📰 **관련 최신 이슈 참조:** [{referenced_meta[0]['title']}]({referenced_meta[0]['link']})\n> *{referenced_meta[0]['insight']}*"

        if any(k in low for k in ["k8s", "쿠버네티스", "pod", "파드", "docker", "도커", "컨테이너"]):
            reply_text = (
                "💡 **[시니어 면접관 코칭: 컨테이너 & 쿠버네티스]**\n\n"
                "컨테이너 질문에서는 **'가상화와의 격리 방식 차이', '장애 복구(Self-Healing)', '무중단 배포'**를 핵심으로 답변해야 합니다.\n\n"
                "**1. 핵심 답변 포인트:**\n"
                "- 도커는 Host 커널을 공유하며 Linux cgroups와 Namespaces를 통해 가볍게 격리합니다.\n"
                "- 쿠버네티스는 Pod의 liveness/readiness probe를 통해 자율 복구하고 HPA로 스케일링을 보장합니다.\n\n"
                "**2. 단골 꼬리 질문:**\n"
                "- *'Pod가 CrashLoopBackOff 상태에 빠졌을 때 kubectl describe와 logs 디버깅 순서는?'*"
                + rag_note
            )
            model_name = "TechPrep AI Mentor (Built-in) + RAG"
        elif any(k in low for k in ["보안", "취약점", "cve", "제로트러스트", "인증", "jwt"]):
            reply_text = (
                "💡 **[시니어 면접관 코칭: 보안 및 침해사고 대응]**\n\n"
                "보안 면접에서는 **'단일 방어선이 뚫렸을 때의 심층 방어(Defense in Depth)'** 관점으로 접근하는 것이 좋습니다.\n\n"
                "**1. 핵심 답변 포인트:**\n"
                "- 제로트러스트(Zero Trust)는 '내부망조차 신뢰하지 않는다(Never Trust, Always Verify)'는 원칙입니다.\n"
                "- mTLS 암호화, 최소 권한 원칙 IAM, 불변 WORM 백업 정책을 결합한 사례를 설명하세요.\n\n"
                "**2. 단골 꼬리 질문:**\n"
                "- *'JWT Access Token 탈취 시 강제 만료(Revoke) 전략은?'*"
                + rag_note
            )
            model_name = "TechPrep AI Mentor (Built-in) + RAG"
        elif any(k in low for k in ["날씨", "비오", "맑", "기온", "미세먼지"]):
            reply_text = (
                "☀️ **[선배의 일상 톡톡: 날씨 & 리프레시]**\n\n"
                "오늘 날씨가 궁금하셨군요! 바쁜 개발 공부와 취업 준비 중에도 가끔 창밖을 보며 가벼운 산책과 환기를 해주는 게 번아웃을 막는 최고의 비결이랍니다. 😊\n\n"
                "오늘 하루도 맑고 상쾌한 기운 받으셔서, 막히는 코드나 복잡한 알고리즘도 시원하게 술술 풀리길 응원할게요!"
            )
            model_name = "TechPrep AI Mentor (Daily Coach)"
        else:
            reply_text = (
                f"💡 **[시니어 면접관 코칭]**\n\n"
                f"**\"{user_msg}\"** 질문에 대해 면접관이 듣고 싶어하는 핵심 포인트를 안내해 드릴게요.\n\n"
                "**1. 모범적인 STAR 답변 구조:**\n"
                "- **Situation(상황)**: 어떤 기술적 요구사항 또는 문제였는지 명확히 정의합니다.\n"
                "- **Task(목표)**: 달성해야 할 지표(TPS, Latency 등)를 제시합니다.\n"
                "- **Action(행동)**: 대안 기술 중 왜 특정 기술을 선택했는지 근거를 밝힙니다.\n"
                "- **Result(결과)**: 도입 후 성과와 트레이드오프를 솔직히 설명합니다."
                + rag_note
            )
            model_name = "TechPrep AI Mentor (Built-in) + RAG"

    # 토큰 추정치 (API에서 토큰이 0으로 반환된 경우 글자 수 기반 추정 1token ≈ 3~4chars)
    if total_tokens == 0:
        prompt_tokens = max(1, len(user_msg) // 3)
        completion_tokens = max(1, len(reply_text) // 3)
        total_tokens = prompt_tokens + completion_tokens

    # 성공 감사 로그 및 토큰 사용량 기록
    record_usage_log(
        username=username,
        ip=client_ip,
        action="CHAT_API",
        status="SUCCESS",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=model_name,
        details=f"Chat response generated for room {room_id}"
    )

    # 히스토리 저장
    session_store[sid][room_id]["updated_at"] = now_iso
    session_store[sid][room_id]["messages"].append({
        "id": f"msg-{uuid.uuid4().hex[:6]}",
        "role": "user",
        "content": user_msg,
        "created_at": now_iso
    })
    session_store[sid][room_id]["messages"].append({
        "id": f"msg-{uuid.uuid4().hex[:6]}",
        "role": "model",
        "content": reply_text,
        "model": model_name,
        "created_at": now_iso,
        "referenced_articles": referenced_meta
    })

    return ChatResponse(
        room_id=room_id,
        reply=reply_text,
        model=model_name,
        created_at=now_iso,
        referenced_articles=referenced_meta
    )

# --- Frontend Static Files Serving ---
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
