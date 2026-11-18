import asyncio
from datetime import datetime
import json
import os
import random
import re
import uuid
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Header
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
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash"]

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

# --- RAG (Retrieval-Augmented Generation) Helper ---
def retrieve_relevant_news(query: str, top_k: int = 3) -> List[Dict]:
    """
    내부 저장된 jobs_and_trends.json 또는 news.json에서 쿼리와 가장 연관성 높은 아티클을 검색
    """
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

    # 쿼리에서 유의미한 키워드 추출 (2글자 이상)
    query_tokens = [w.lower() for w in re.findall(r'[A-Za-z0-9가-힣]{2,}', query)]
    stopwords = {
        "어떻게", "알려줘", "알려주세요", "대해서", "질문", "면접", "관련", "설명해줘", "답변", "요령",
        "신입", "개발자", "면접관", "어필", "가장", "좋을까", "좋을까요", "준비", "포트폴리오", "취업", "진로",
        "서울", "날씨", "오늘", "내일", "기온", "어때", "어때요", "어떡", "어떻", "무엇", "어떤", "어떤걸",
        "모르겠", "방황", "불안", "시작", "공부", "방법", "구조", "전략", "방식", "설계", "대규모"
    }
    keywords = [k for k in query_tokens if k not in stopwords]

    # 키워드가 없거나, 질문 자체가 일상/날씨/단순 조언인 경우 RAG 기사 검색 스킵
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
        text = f"{title} {summary} {insight} {tags}".lower()

        score = 0
        matched_kws = 0
        for kw in keywords:
            kw_score = 0
            if kw in title.lower():
                kw_score += 6  # 제목 매칭 가중치
            if kw in tags.lower():
                kw_score += 4  # 태그 매칭 가중치
            if kw in insight.lower():
                kw_score += 3  # 실무 인사이트 매칭
            if kw in summary.lower():
                kw_score += 1
            if kw_score > 0:
                matched_kws += 1
                score += kw_score

        # 최소 임계값: 핵심 키워드가 제목이나 태그에 직접 부합하거나 고득점인 경우만 인정 (유사도 7점 이상)
        if score >= 7 and matched_kws >= 1:
            scored_articles.append((score, item))

    scored_articles.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored_articles[:top_k]]

# --- Anonymous Session & Chat History Store ---
# In-memory session store (session_id -> dict of rooms)
# session_store[session_id] = { room_id: { "title": str, "updated_at": str, "messages": list } }
session_store: Dict[str, Dict[str, Dict]] = {}

class ChatMessage(BaseModel):
    id: Optional[str] = None
    role: str  # user or model
    content: str
    model: Optional[str] = None
    created_at: Optional[str] = None
    referenced_articles: Optional[List[Dict]] = None

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

class RenameRoomRequest(BaseModel):
    title: str

@app.get("/api/chats")
async def list_chat_rooms(x_session_id: Optional[str] = Header(None)):
    sid = x_session_id or "default-session"
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
async def create_chat_room(req: CreateRoomRequest, x_session_id: Optional[str] = Header(None)):
    sid = x_session_id or "default-session"
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
async def get_room_messages(room_id: str, x_session_id: Optional[str] = Header(None)):
    sid = x_session_id or "default-session"
    rooms = session_store.get(sid, {})
    if room_id not in rooms:
        return []
    return rooms[room_id].get("messages", [])

@app.delete("/api/chats/{room_id}")
async def delete_chat_room(room_id: str, x_session_id: Optional[str] = Header(None)):
    sid = x_session_id or "default-session"
    if sid in session_store and room_id in session_store[sid]:
        del session_store[sid][room_id]
        return {"success": True, "message": "삭제되었습니다."}
    return {"success": False, "message": "방을 찾을 수 없습니다."}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_mentor(req: ChatRequest, x_session_id: Optional[str] = Header(None)):
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    sid = x_session_id or "default-session"
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
        # 첫 메시지인 경우 방 제목 업데이트
        if len(session_store[sid][room_id]["messages"]) == 0:
            session_store[sid][room_id]["title"] = user_msg[:18] + ("..." if len(user_msg) > 18 else "")

    # 1. RAG: 시스템에 수집된 최신 IT 이슈 및 인사이트 검색 (Retrieval)
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

    # 2. Gemini API 호출 또는 고품질 폴백 응답 생성 (Generation)
    reply_text = ""
    model_name = ""

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

            # 이전 대화 3개 포함
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
                        break
                except Exception as model_err:
                    print(f"Model {m} failed: {model_err}")

            if reply_text:
                model_name = f"Google Gemini ({used_model})" + (" + RAG" if rag_context_snippets else "")
        except Exception as e:
            print(f"Gemini API 호출 에러: {e}")

    if not reply_text:
        # 폴백 모드 (RAG 기사 정보 결합)
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
                "오늘 하루도 맑고 상쾌한 기운 받으셔서, 막히는 코드나 복잡한 알고리즘도 시원하게 술술 풀리길 응원할게요! 또 궁금하거나 이야기 나누고 싶은 게 생기면 언제든 편하게 말 걸어주세요."
            )
            model_name = "TechPrep AI Mentor (Daily Coach)"
        elif any(k in low for k in ["모르겠", "막막", "방황", "어떡", "어떻", "무엇을", "어떤걸", "불안"]):
            reply_text = (
                "☕ **[선배의 든든한 멘토링: 무엇을 해야 할지 막막할 때]**\n\n"
                "아이고, 많이 막막하고 답답하시죠. 😢 주니어 시절에는 누구나 '내가 지금 잘하고 있는 건가?', '도대체 어디서부터 시작해야 하지?' 같은 깊은 혼란을 겪습니다. 저 또한 신입 시절에 매일 밤 똑같은 고민을 했었답니다.\n\n"
                "이럴 때는 너무 거창한 목표를 세우기보다 **작고 확실한 3단계**로 호흡을 가다듬는 게 가장 효과적이에요:\n\n"
                "**1. 관심 도메인 하나 딱 정하기**\n"
                "- 백엔드, 프론트엔드, DevOps/인프라, 데이터 등 모든 것을 다 잘할 수는 없습니다. 마음이 조금이라도 더 끌리는 메인 트랙 하나를 정해보세요.\n\n"
                "**2. 작은 서비스 하나 끝까지 배포해 보기 (End-to-End)**\n"
                "- 강의만 계속 듣는 '인강 완강 러너'에서 벗어나, 로그인부터 DB 연동, 클라우드 무료 배포(Render/Vercel)까지 작은 기능을 내 손으로 끝장내 보는 경험이 자신감을 되찾아 줍니다.\n\n"
                "**3. 실패 노트(에러 로그) 작성하기**\n"
                "- '오늘 겪은 에러와 내가 시도한 해결책 3줄'을 기록하는 습관만 들여도 면접관이 가장 좋아하는 훌륭한 포트폴리오가 됩니다.\n\n"
                "지치지 말고 페이스 유지하세요! 구체적으로 어떤 기술이나 분야가 고민되는지 조금 더 편하게 털어놔 주시면 제가 함께 길을 찾아드릴게요. 💪"
            )
            model_name = "TechPrep AI Mentor (Career Coach)"
        elif any(k in low for k in ["떨려", "긴장", "불안", "무서", "걱정", "심장"]):
            reply_text = (
                "🌿 **[시니어 면접관의 따뜻한 멘탈 케어: 면접 긴장 극복법]**\n\n"
                "아이고, 면접이 코앞이라니 심장이 쿵쾅거리고 손에 땀이 나시죠! 그 마음, 정말 100% 이해합니다. 10년 차인 저도 중요한 기술 프레젠테이션이나 임원 미팅 전에는 여전히 긴장되거든요. 😊\n\n"
                "면접관의 입장에서 꼭 전해드리고 싶은 **마음 안정 팁 3가지**를 드릴게요:\n\n"
                "**1. 면접관은 '떨어뜨리려고' 앉아 있는 사람이 아닙니다**\n"
                "- 면접관은 '이 사람과 같이 일하면 얼마나 즐겁고 든든할까?'를 기대하며 지원자의 장점을 찾으려고 애쓰고 있습니다. 시험관이 아니라 미래의 동료를 만나러 가는 티타임이라고 생각하세요.\n\n"
                "**2. '모르겠습니다'는 감점 요인이 아닙니다**\n"
                "- 모르는 질문을 받았을 때 억지로 꾸며내려 하면 긴장감이 배가 됩니다. '그 부분은 아직 깊이 다뤄보지 못했지만, 제가 아는 A 원리에 비추어 보면 이렇게 유추해 볼 수 있습니다'라고 솔직하고 논리적으로 풀어내면 면접관은 오히려 감탄합니다.\n\n"
                "**3. 심호흡과 질문 곱씹기**\n"
                "- 질문을 받자마자 1초 만에 대답할 필요가 전혀 없습니다. '좋은 질문 감사드립니다. 잠시 생각할 시간을 3초만 가져도 될까요?'라고 여유를 가지면 긴장감이 확 내려갑니다.\n\n"
                "지금까지 치열하게 준비해 오신 것만으로도 이미 훌륭한 엔지니어입니다. 본인을 믿고 편안하게 이야기 나누고 오세요! 진심으로 합격을 응원합니다! 🍀"
            )
            model_name = "TechPrep AI Mentor (Mindset Coach)"
        elif any(k in low for k in ["신입", "어필", "취업", "비전공", "포트폴리오", "진로", "커리어"]):
            reply_text = (
                "🌱 **[시니어 면접관이 전하는 신입 개발자 핵심 어필 포인트]**\n\n"
                "정말 중요한 질문이에요! 많은 주니어분들이 면접관에게 '완벽한 아키텍처나 화려한 경력'을 보여줘야 한다고 오해하곤 합니다.\n\n"
                "하지만 10년 차 면접관의 시선에서 솔직히 말씀드리면, 신입에게는 **'현재의 완성도'보다 '팀에 합류했을 때의 성장 잠재력'**이 합격을 결정짓습니다. 다음 **4가지 핵심 포인트**를 어필해 보세요:\n\n"
                "**1. 탄탄한 CS 기본기와 원리에 대한 집요함**\n"
                "- 프레임워크나 라이브러리를 단순히 가져다 쓰는 데 그치지 않고, '이것이 네트워크나 메모리/OS 단에서 왜 이렇게 동작하는지' 파고들어 본 경험을 강조하세요.\n\n"
                "**2. 실패와 디버깅 스토리 (가장 강력한 무기)**\n"
                "- 'A 기능을 구현했습니다'보다 'A 개발 중 난해한 에러를 만났을 때, 가설을 세우고 로그를 분석하여 근본 원인을 해결한 과정'이 면접관을 가장 설레게 만듭니다.\n\n"
                "**3. 협업과 코드 품질에 대한 태도**\n"
                "- Git 커밋 컨벤션, PR 코드 리뷰, 단위 테스트 작성 등 '팀의 일원으로서 동료를 배려하며 일할 준비가 되어 있는가'를 프로젝트 결과물로 증명하세요.\n\n"
                "**4. 겸손하면서도 솔직한 학습 태도**\n"
                "- 모르는 질문이 나왔을 때 아는 척 얼버무리지 않고, 자신이 아는 부분까지 논리적으로 설명하고 배움에 열려 있는 태도를 보여주는 것이 훨씬 높은 점수를 받습니다.\n\n"
                "응원합니다! 자신감을 갖고 본인의 치열했던 문제 해결 과정을 보여주세요. 💪"
            )
            model_name = "TechPrep AI Mentor (Career Coach)"
        elif any(k in low for k in ["트래픽", "캐시", "캐싱", "분산", "대규모"]):
            reply_text = (
                "💡 **[시니어 면접관 코칭: 대규모 트래픽 분산 & 캐싱 전략]**\n\n"
                "대규모 트래픽과 캐싱 질문은 백엔드/인프라 면접에서 **시스템 안정성과 성능 최적화 역량**을 검증하는 단골 핵심 질문입니다.\n\n"
                "**1. 핵심 답변 포인트:**\n"
                "- **트래픽 분산 (L4/L7 계층)**: ALB를 통한 라운드로빈/최소 연결 분산과 Auto Scaling Group(HPA) 동적 증설을 설명합니다.\n"
                "- **캐싱 전략 (Cache Aside vs Write Through)**: 읽기 위주 트래픽에는 Redis를 활용한 Look-Aside 패턴을 적용하고, 데이터 정합성을 위한 TTL 및 캐시 무효화(Cache Invalidation) 전략을 명확히 제시합니다.\n"
                "- **장애 방어 (Cache Avalanche / Penetration)**: 캐시 만료 시각 지터링(Jitter) 분산, Bloom Filter 도입, 서킷 브레이커(Resilience4j)를 통한 DB 부하 격리를 강조하세요.\n\n"
                "**2. 면접관의 단골 꼬리 질문(Follow-up):**\n"
                "- *'Redis Cluster 다운 시 데이터 유실 방지와 대체 Failover 프로세스는 어떻게 설계하셨나요?'*\n"
                "- *'Hot Key(특정 데이터에 트래픽 집중) 문제로 단일 Redis 샤드에 병목이 생겼을 때의 해결책은?'*"
                + rag_note
            )
            model_name = "TechPrep AI Mentor (Built-in) + RAG" if rag_note else "TechPrep AI Mentor (Built-in)"
        elif any(k in low for k in ["안녕", "반가", "하이", "hello"]):
            reply_text = "안녕하세요! 반갑습니다. 😊 TechPrep-AI의 시니어 DevOps / 백엔드 면접관 멘토입니다. 어떤 기술 주제나 면접 고민이든 편하게 물어보세요!"
            model_name = "TechPrep AI Mentor (Built-in)"
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

    # 3. 세션 히스토리에 저장
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

# --- Frontend Static Files Serving (포트 8080 통합 서빙) ---
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
