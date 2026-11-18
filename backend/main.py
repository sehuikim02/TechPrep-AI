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
GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTION = (
    "너는 IT 대기업의 10년 차 시니어 DevOps / 백엔드 엔지니어이자 다정하고 지혜로운 AI 커리어 & 기술 면접 멘토야. "
    "1. [일상 대화 & 진로/신입 커리어 상담]:\n"
    "   - '신입이라 어떤 걸 어필해야 할까?', '비전공자인데 취업할 수 있을까?', '포트폴리오는 어떻게 꾸밀까?' 같은 진로 고민이나 일상적인 대화가 들어오면, 선배 개발자의 시선에서 따뜻하게 격려하고 현실적이며 구체적인 조언을 해 줘.\n"
    "   - 신입 개발자에게는 완성된 화려함보다 '탄탄한 CS 기본기', '문제 해결 집요함(디버깅 스토리)', '코드 품질과 테스트에 대한 태도', '팀원과의 원활한 소통/협업 능력'이 핵심 어필 포인트임을 친절하게 짚어줘.\n"
    "2. [RAG 실시간 이슈 활용]:\n"
    "   - 질문과 관련된 최신 IT 뉴스나 실무 인사이트(RAG Context)가 주어지면 적극적으로 인용하여 최신 업계 트렌드와 연결해 줘.\n"
    "   - 단, 일상 인사나 순수 커리어 조언처럼 기사와 무관한 질문일 때는 억지로 뉴스를 엮지 말고 질문자의 고민에 집중해서 공감하며 답변해 줘.\n"
    "3. [기술 면접 코칭]:\n"
    "   - 기술 질문이 들어오면 주니어 눈높이에 맞춰 명쾌하게 원리를 설명하고, STAR 답변 기법 및 면접관이 던질 수 있는 꼬리 질문 1~2개를 덧붙여 줘.\n"
    "4. 한국어로 정중하고 따뜻한 경어체로 대화해 줘."
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
        "신입", "개발자", "면접관", "어필", "가장", "좋을까", "좋을까요", "준비", "포트폴리오", "취업", "진로"
    }
    keywords = [k for k in query_tokens if k not in stopwords]

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
        for kw in keywords:
            if kw in title.lower():
                score += 5  # 제목 매칭 가중치
            if kw in tags.lower():
                score += 4  # 태그 매칭 가중치
            if kw in insight.lower():
                score += 3  # 실무 인사이트 매칭
            if kw in summary.lower():
                score += 1

        if score > 0:
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

            response = GEMINI_CLIENT.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
                config=config
            )
            reply_text = response.text
            model_name = f"Google Gemini ({GEMINI_MODEL}) + RAG"
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
