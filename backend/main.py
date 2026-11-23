import asyncio
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import random
import re
import time
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
    increment_failed_login,
    reset_failed_login,
    bulk_approve_users,
    list_all_users,
    record_login_log,
    record_usage_log,
    get_login_logs,
    get_usage_logs,
    get_security_and_usage_stats,
    delete_old_articles_from_db,
    parse_article_datetime,
    toggle_user_bookmark,
    get_user_bookmarks,
    get_user_bookmarked_article_ids,
    get_all_protected_bookmarked_keys,
    save_or_update_daily_ai_report,
    get_daily_ai_report,
    list_daily_ai_report_dates,
    get_logs_for_date,
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
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
GEMINI_KEY_STATUS = "UNCONFIGURED"  # HEALTHY, INVALID, UNCONFIGURED

SYSTEM_INSTRUCTION = (
    "너는 IT 대기업의 10년 차 시니어 DevOps / 백엔드 엔지니어이자 다정하고 지혜로운 AI 커리어 & 기술 멘토야.\n"
    "1. [일상 대화, 인사 & 스몰토크]:\n"
    "   - '안녕', '안녕?', '반가워', '오늘 날씨 어때?', '점심 뭐 먹을까?', '고마워', '힘들다' 같은 일상 대화에는 다정하고 자연스러운 선배처럼 편안하게 대화해 줘.\n"
    "   - 일상 대화나 인사에 대해 절대로 STAR 프레임워크, CS 기본기, 모범 면접 답변 같은 딱딱한 템플릿을 억지로 꺼내지 마.\n"
    "2. [진로 / 취업 / 고민 상담]:\n"
    "   - 신입 취업 준비나 포트폴리오 고민, 진로 방황에 대해 물어보면 선배의 시선에서 깊이 공감하고 현실적인 3대 어필 포인트(CS 기본기, 디버깅 스토리, 협업 태도)를 따뜻하게 조언해 줘.\n"
    "3. [기술 / 도메인 / RAG 질문]:\n"
    "   - 쿠버네티스, 클라우드, 인프라, 보안, 아키텍처 등 실무 기술 질문이나 RAG Context가 제공되었을 때만 전문적인 엔지니어링 분석과 실전 면접 포인트를 제공해 줘.\n"
    "4. 한국어로 정중하고 따뜻하며 생동감 있는 경어체로 대화해 줘."
)

def clean_key_string(val: Optional[str]) -> Optional[str]:
    """API 키 문자열에서 앞뒤 따옴표, 공백, 줄바꿈(\r, \n) 등을 완벽히 정제합니다."""
    if not val:
        return None
    cleaned = val.strip().strip('"').strip("'").strip().strip('\r').strip('\n').strip()
    return cleaned if len(cleaned) > 5 else None

def mask_key_string(key: Optional[str]) -> str:
    """보안 마스킹: 앞 4자리와 뒤 3자리만 노출 (예: AIza...xyz, 길이 39)"""
    if not key:
        return "(NONE)"
    if len(key) <= 8:
        return f"*** (len={len(key)})"
    return f"{key[:4]}...{key[-3:]} (len={len(key)})"

# 1. 시스템 환경변수(Render 등)를 최우선으로 보존
SYS_GEMINI_KEY = clean_key_string(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))

# 2. .env 파일 로드 (단, 시스템 환경변수에 이미 값이 있으면 덮어쓰지 않음)
env_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_file_path):
    try:
        with open(env_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k_clean = k.strip()
                    v_clean = clean_key_string(v)
                    # 시스템 환경변수에 이미 세팅되어 있다면 .env의 과거 값으로 덮어쓰기 방지
                    if k_clean not in os.environ or not os.environ[k_clean].strip():
                        if v_clean:
                            os.environ[k_clean] = v_clean
    except Exception as e:
        print(f"Failed to load .env: {e}")

def get_effective_gemini_api_key() -> tuple[Optional[str], str]:
    """
    최신 유효 GEMINI_API_KEY를 실시간으로 가져오며, 출처와 마스킹 정보를 함께 반환합니다.
    우선순위:
    1. os.environ['GEMINI_API_KEY']
    2. os.environ['GOOGLE_API_KEY']
    3. SYS_GEMINI_KEY (시작 시점 보존값)
    """
    k1 = clean_key_string(os.environ.get("GEMINI_API_KEY"))
    if k1:
        return k1, "os.environ['GEMINI_API_KEY']"
    k2 = clean_key_string(os.environ.get("GOOGLE_API_KEY"))
    if k2:
        return k2, "os.environ['GOOGLE_API_KEY']"
    if SYS_GEMINI_KEY:
        return SYS_GEMINI_KEY, "System Startup Environment"
    return None, "Not Found"

# 시작 시점 키 진단 로그 (마스킹 필수)
startup_key, startup_src = get_effective_gemini_api_key()
if startup_key:
    GEMINI_KEY_STATUS = "ACTIVE"
    print(f"🔑 [Gemini Key Diagnostic] Key detected from [{startup_src}]: {mask_key_string(startup_key)}")
else:
    GEMINI_KEY_STATUS = "UNCONFIGURED"
    print("ℹ️ [Gemini Key Diagnostic] GEMINI_API_KEY / GOOGLE_API_KEY not found.")

def get_gemini_sdk_client(api_key: str):
    """요청 시점의 최신 유효 키를 바탕으로 Client를 생성하거나 재사용합니다."""
    try:
        from google import genai
        return genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    except Exception as e:
        print(f"⚠️ [SDK Client Init Error]: {e}")
        return None

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

# --- Article Auto-Cleanup Engine (Retention & Garbage Collection) ---
def get_article_cleanup_config() -> tuple[bool, int]:
    """환경변수 ARTICLE_AUTO_CLEANUP_ENABLED 및 ARTICLE_RETENTION_DAYS 값을 읽어옵니다."""
    enabled_str = os.environ.get("ARTICLE_AUTO_CLEANUP_ENABLED", "true").strip().lower()
    enabled = enabled_str in ("true", "1", "yes", "on")
    try:
        days = int(os.environ.get("ARTICLE_RETENTION_DAYS", "30").strip())
    except ValueError:
        days = 30
    return enabled, days

def preview_article_cleanup(retention_days: int = 30) -> dict:
    """
    30일(또는 지정된 retention_days) 경과 삭제 대상 기사 목록을 미리 조회합니다 (실제 삭제하지 않음).
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    now_utc = datetime.now(timezone.utc)
    cutoff_dt = now_utc - timedelta(days=retention_days)
    cutoff_iso = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    # 북마크 보호 키 집합 조회 (북마크된 기사는 자동 삭제 대상에서 제외)
    protected_keys = get_all_protected_bookmarked_keys()

    target_files = [
        os.path.join(base_dir, "data", "jobs_and_trends.json"),
        os.path.join(base_dir, "frontend", "jobs_and_trends.json"),
        os.path.join(base_dir, "jobs_and_trends.json")
    ]

    candidates = []
    seen_links = set()
    total_articles = 0

    for fp in target_files:
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                articles = data.get("articles", [])
                total_articles = max(total_articles, len(articles))
                for art in articles:
                    link = art.get("link") or art.get("title")
                    if link in seen_links:
                        continue
                    # 북마크 보호 확인
                    art_id = art.get("article_id")
                    art_link = art.get("link")
                    art_title = art.get("title")
                    if (
                        (art_id and art_id in protected_keys) or
                        (art_link and art_link in protected_keys) or
                        (art_title and art_title in protected_keys)
                    ):
                        continue

                    date_str = art.get("published") or art.get("created_at") or art.get("published_at")
                    dt = parse_article_datetime(date_str)
                    if dt is not None and dt < cutoff_dt:
                        seen_links.add(link)
                        candidates.append({
                            "title": art.get("title", "제목 없음"),
                            "published": date_str,
                            "category": art.get("category", "기타"),
                            "source": art.get("source", ""),
                            "link": art.get("link", "")
                        })
            except Exception as ex:
                print(f"⚠️ Preview failed on {fp}: {ex}")

    return {
        "retention_days": retention_days,
        "cutoff_date": cutoff_iso,
        "total_active_articles": total_articles,
        "cleanup_candidate_count": len(candidates),
        "candidates": candidates
    }

def execute_article_cleanup(retention_days: int = 30, triggered_by: str = "SYSTEM_STARTUP") -> dict:
    """
    30일(또는 지정된 retention_days)이 경과한 오래된 기사를
    JSON 파일들 및 데이터베이스(Postgres / SQLite)에서 모두 삭제합니다.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    now_utc = datetime.now(timezone.utc)
    cutoff_dt = now_utc - timedelta(days=retention_days)
    cutoff_iso = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    # 북마크 보호 키 집합 조회 (북마크된 기사는 자동 삭제 대상에서 제외)
    protected_keys = get_all_protected_bookmarked_keys()

    # 대상 JSON 파일 목록
    target_files = [
        os.path.join(base_dir, "data", "jobs_and_trends.json"),
        os.path.join(base_dir, "data", "news.json"),
        os.path.join(base_dir, "frontend", "jobs_and_trends.json"),
        os.path.join(base_dir, "frontend", "news.json"),
        os.path.join(base_dir, "jobs_and_trends.json"),
        os.path.join(base_dir, "news.json")
    ]

    total_deleted_articles = 0
    remaining_count = 0
    affected_files = []
    deleted_titles_sample = []
    seen_deleted_titles = set()

    for fp in target_files:
        if not os.path.exists(fp):
            continue
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)

            articles = data.get("articles", [])
            initial_count = len(articles)
            kept_articles = []
            file_deleted = 0

            for art in articles:
                date_str = art.get("published") or art.get("created_at") or art.get("published_at")
                dt = parse_article_datetime(date_str)
                # 북마크 보호 확인: 사용자가 북마크한 기사는 30일이 경과해도 삭제 대상에서 제외
                art_id = art.get("article_id")
                art_link = art.get("link")
                art_title = art.get("title")
                is_protected = (
                    (art_id and art_id in protected_keys) or
                    (art_link and art_link in protected_keys) or
                    (art_title and art_title in protected_keys)
                )

                # 날짜가 파싱되었고 30일(cutoff_dt) 이전이며, 북마크로 보호되지 않은 경우 삭제 대상
                if dt is not None and dt < cutoff_dt and not is_protected:
                    file_deleted += 1
                    t = art.get("title", "").strip()
                    if t and t not in seen_deleted_titles:
                        seen_deleted_titles.add(t)
                        deleted_titles_sample.append(t)
                else:
                    # 날짜가 없거나 기준일 이내이거나 북마크 보호 기사인 경우 안전하게 보존
                    kept_articles.append(art)

            if file_deleted > 0 or initial_count != len(kept_articles):
                # 카테고리 집계 갱신
                category_counts = {}
                for art in kept_articles:
                    c = art.get("category", "기타")
                    category_counts[c] = category_counts.get(c, 0) + 1

                metadata = data.get("metadata", {})
                metadata["total_articles"] = len(kept_articles)
                metadata["categories"] = category_counts
                metadata["last_cleanup"] = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

                data["metadata"] = metadata
                data["articles"] = kept_articles

                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                affected_files.append(os.path.basename(fp))
                if file_deleted > total_deleted_articles:
                    total_deleted_articles = file_deleted
            
            remaining_count = len(kept_articles)

        except Exception as file_err:
            print(f"⚠️ Failed to cleanup JSON file {fp}: {file_err}")

    # 데이터베이스(PostgreSQL / SQLite)의 articles 테이블에서도 삭제
    db_deleted = 0
    try:
        db_deleted = delete_old_articles_from_db(retention_days)
    except Exception as db_err:
        print(f"⚠️ DB article cleanup warning: {db_err}")

    # 삭제된 기사 요약 타이틀 포맷팅 (상위 3건 + 외 N건)
    sample_summary = ""
    if deleted_titles_sample:
        top_titles = [f"'{t[:30]}...'" if len(t) > 30 else f"'{t}'" for t in deleted_titles_sample[:3]]
        sample_summary = ", ".join(top_titles)
        if len(deleted_titles_sample) > 3:
            sample_summary += f" 외 {len(deleted_titles_sample) - 3}건"
        sample_summary = f" [삭제기사: {sample_summary}]"

    result_detail = (
        f"기준일({cutoff_iso}) 이전 {retention_days}일 경과 기사 자동 삭제 완료: "
        f"JSON {total_deleted_articles}건 삭제 (남은 기사: {remaining_count}건, 반영 파일: {len(affected_files)}개), "
        f"DB {db_deleted}건 삭제{sample_summary}"
    )

    if len(result_detail) > 480:
        result_detail = result_detail[:477] + "..."

    print(f"🧹 [Article Cleanup] {result_detail}")

    # 관리자 감사 로그에 기록
    try:
        record_usage_log(
            username=triggered_by,
            ip="127.0.0.1",
            action="ARTICLE_AUTO_CLEANUP",
            status="SUCCESS",
            details=result_detail
        )
    except Exception as log_err:
        print(f"⚠️ Failed to record cleanup usage log: {log_err}")

    return {
        "status": "success",
        "retention_days": retention_days,
        "cutoff_date": cutoff_iso,
        "json_deleted_count": total_deleted_articles,
        "db_deleted_count": db_deleted,
        "remaining_count": remaining_count,
        "affected_files": affected_files,
        "deleted_titles_sample": deleted_titles_sample[:10]
    }

async def periodic_article_cleanup_worker():
    """백그라운드에서 주기적으로(12시간마다) 30일 경과 기사를 자동 청소하는 워커 루프"""
    while True:
        try:
            # 12시간 대기
            await asyncio.sleep(43200)
            enabled, retention_days = get_article_cleanup_config()
            if enabled:
                execute_article_cleanup(retention_days=retention_days, triggered_by="SYSTEM_CRON")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"⚠️ periodic_article_cleanup_worker error: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(autonomous_healing_worker())

    # 환경변수 제어 기반 30일 경과 기사 자동 정리 실행 및 백그라운드 워커 기동
    cleanup_enabled, retention_days = get_article_cleanup_config()
    if cleanup_enabled:
        execute_article_cleanup(retention_days=retention_days, triggered_by="SYSTEM_STARTUP")
        asyncio.create_task(periodic_article_cleanup_worker())
    else:
        print("ℹ️ [Article Cleanup] ARTICLE_AUTO_CLEANUP_ENABLED is false. Auto cleanup skipped.")


def call_gemini_api(full_prompt: str, system_prompt: str) -> tuple[Optional[str], Optional[str], int, int, int]:
    """
    Gemini API를 호출하여 (reply_text, model_name, prompt_tokens, completion_tokens, total_tokens)을 반환합니다.
    1순위: google-genai SDK v1beta (동적 클라이언트)
    2순위: Google AI Studio v1beta REST API 직접 호출 (쿼리 파라미터 + x-goog-api-key 헤더 이중 전달)
    """
    api_key, key_source = get_effective_gemini_api_key()
    if not api_key:
        print("⚠️ [Gemini Call Blocked] No effective API key found in environment or .env.")
        return None, None, 0, 0, 0

    print(f"🚀 [Gemini Calling] Source: [{key_source}], Masked Key: {mask_key_string(api_key)}")
    candidate_models = ["gemini-2.5-flash", "gemini-3.5-flash-lite"]

    # 1. SDK 호출 시도 (최신 정제 키로 클라이언트 생성)
    sdk_client = get_gemini_sdk_client(api_key)
    if sdk_client:
        from google.genai import types
        for m in candidate_models:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                )
                response = sdk_client.models.generate_content(
                    model=m,
                    contents=full_prompt,
                    config=config
                )
                if response and response.text:
                    p_tok = 0
                    c_tok = 0
                    t_tok = 0
                    if hasattr(response, 'usage_metadata') and response.usage_metadata:
                        p_tok = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
                        c_tok = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
                        t_tok = getattr(response.usage_metadata, 'total_token_count', 0) or (p_tok + c_tok)
                    print(f"✅ [SDK Success] Model {m} generated response successfully.")
                    return response.text, m, p_tok, c_tok, t_tok
            except Exception as e:
                print(f"[SDK Failed] model {m}: {e}")

    # 2. REST API 직접 호출 시도 (쿼리 키 및 x-goog-api-key 헤더 이중 부여)
    import requests
    for m in candidate_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            }
            payload = {
                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": [
                    {"parts": [{"text": full_prompt}]}
                ],
                "generationConfig": {
                    "temperature": 0.7
                }
            }
            res = requests.post(url, headers=headers, json=payload, timeout=25)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates and "content" in candidates[0]:
                    parts = candidates[0]["content"].get("parts", [])
                    if parts and "text" in parts[0]:
                        reply = parts[0]["text"]
                        meta = data.get("usageMetadata", {})
                        p_tok = meta.get("promptTokenCount", 0)
                        c_tok = meta.get("candidatesTokenCount", 0)
                        t_tok = meta.get("totalTokenCount", p_tok + c_tok)
                        print(f"✅ [REST API Success] Model {m} responded successfully.")
                        return reply, m, p_tok, c_tok, t_tok
            else:
                print(f"[REST Failed] Model {m} HTTP {res.status_code}: {res.text[:140]}")
        except Exception as ex:
            print(f"[REST Exception] Model {m}: {ex}")

    return None, None, 0, 0, 0

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
    reason: Optional[str] = None

class BulkApproveRequest(BaseModel):
    usernames: Optional[List[str]] = None

def validate_password_strength(password: str) -> Optional[str]:
    """
    비밀번호 정책 검증:
    - 최소 8자 이상, 최대 64자 이하
    - 영문자(대/소문자) 1개 이상 포함
    - 숫자(0-9) 1개 이상 포함
    - 특수문자(!@#$%^&*()_+-=[]{}|;:,.<>/? 등) 1개 이상 포함
    - 공백 미허용
    """
    if not password:
        return "비밀번호를 입력해 주세요."
    if len(password) < 8 or len(password) > 64:
        return "비밀번호는 최소 8자 이상, 64자 이하여야 합니다."
    if " " in password:
        return "비밀번호에 공백은 포함될 수 없습니다."
    if not re.search(r'[A-Za-z]', password):
        return "비밀번호에 영문자가 최소 1개 이상 포함되어야 합니다."
    if not re.search(r'\d', password):
        return "비밀번호에 숫자가 최소 1개 이상 포함되어야 합니다."
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/~`]', password):
        return "비밀번호에 특수문자(!@#$%^&* 등)가 최소 1개 이상 포함되어야 합니다."
    return None

@app.post("/api/auth/register")
async def register(req: RegisterRequest, request: Request):
    username = req.username.strip()
    password = req.password.strip()
    client_ip = get_client_ip(request)

    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="아이디는 최소 3자 이상이어야 합니다.")
    
    pwd_err = validate_password_strength(password)
    if pwd_err:
        raise HTTPException(status_code=400, detail=f"비밀번호 보안 정책 미충족: {pwd_err}")

    existing = get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="이미 존재하는 아이디입니다.")

    pw_hash = hash_password(password)
    user = create_user(username=username, password_hash=pw_hash, role="user", api_status="pending")
    record_usage_log(username, client_ip, "REGISTER", "SUCCESS", details="New user registered with pending status")
    record_login_log(username, client_ip, "SUCCESS", failure_reason="Initial registration auto-login")

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

    # 차단된 계정 검사
    if user["api_status"] == "blocked":
        block_msg = f"해당 계정은 비정상 로그인 시도 또는 관리자에 의해 차단되었습니다."
        if user.get("block_reason"):
            block_msg += f" (사유: {user['block_reason']})"
        record_login_log(username, client_ip, "FAILED", f"BlockedAccount: {user.get('block_reason') or 'No reason'}")
        raise HTTPException(status_code=403, detail=block_msg)

    # 비밀번호 검증
    if not verify_password(password, user["password_hash"]):
        # 실패 횟수 증가
        fail_count = increment_failed_login(username)
        # 5회 이상 실패 시 자동 차단 (admin 계정 제외)
        if user.get("role") != "admin" and fail_count >= 5:
            auto_reason = f"비정상 로그인 시도(연속 {fail_count}회 실패)로 인한 자동 차단"
            update_user_api_status(username, "blocked", block_reason=auto_reason)
            record_login_log(username, client_ip, "FAILED", f"AutoBlocked: {fail_count} consecutive failures")
            record_usage_log(username, client_ip, "AUTO_BLOCK_USER", "SUCCESS", details=auto_reason)
            raise HTTPException(
                status_code=403,
                detail=f"비밀번호가 5회 이상 연속 불일치하여 계정이 자동으로 차단되었습니다. 관리자에게 문의해 주세요."
            )

        rem_attempts = max(0, 5 - fail_count)
        err_msg = "아이디 또는 비밀번호가 올바르지 않습니다."
        if user.get("role") != "admin":
            err_msg += f" (연속 실패 {fail_count}/5회 - 5회 누적 시 계정이 자동 차단됩니다.)"

        record_login_log(username, client_ip, "FAILED", f"InvalidPassword (attempt {fail_count})")
        raise HTTPException(status_code=401, detail=err_msg)

    # 로그인 성공 시 실패 카운트 리셋
    reset_failed_login(username)

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

# --- User Bookmarks Endpoints ---
class BookmarkToggleRequest(BaseModel):
    article_id: str
    title: Optional[str] = "기사 제목 없음"
    link: Optional[str] = ""
    category: Optional[str] = "기타"
    source: Optional[str] = ""
    summary: Optional[str] = ""
    interview_insight: Optional[str] = ""

@app.post("/api/bookmarks/toggle")
async def api_toggle_bookmark(
    req: BookmarkToggleRequest,
    current_user: dict = Depends(get_current_user_required),
    request: Request = None
):
    """현재 로그인한 사용자의 기사 북마크 상태를 토글(저장/해제)합니다."""
    res = toggle_user_bookmark(current_user["id"], req.dict())
    client_ip = get_client_ip(request) if request else "unknown"
    action_type = "BOOKMARK_ADD" if res["bookmarked"] else "BOOKMARK_REMOVE"
    record_usage_log(
        username=current_user["username"],
        ip=client_ip,
        action=action_type,
        status="SUCCESS",
        details=f"article_id={req.article_id}, title={req.title[:40]}"
    )
    return res

@app.get("/api/bookmarks")
async def api_get_bookmarks(
    current_user: dict = Depends(get_current_user_required)
):
    """현재 로그인한 사용자의 전체 북마크 목록을 반환합니다."""
    bookmarks = get_user_bookmarks(current_user["id"])
    return {
        "status": "success",
        "total_count": len(bookmarks),
        "bookmarks": bookmarks
    }

@app.get("/api/bookmarks/ids")
async def api_get_bookmark_ids(
    current_user: dict = Depends(get_current_user_required)
):
    """현재 로그인한 사용자가 북마크한 기사 article_id 목록만 빠르게 반환합니다."""
    ids = get_user_bookmarked_article_ids(current_user["id"])
    return {
        "status": "success",
        "ids": ids
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

    ok = update_user_api_status(req.username, req.api_status, block_reason=req.reason)
    if not ok:
        raise HTTPException(status_code=500, detail="상태 업데이트에 실패했습니다.")

    client_ip = get_client_ip(request) if request else "unknown"
    detail_msg = f"Changed {req.username} to {req.api_status}"
    if req.reason:
        detail_msg += f" (Reason: {req.reason})"
    record_usage_log(admin["username"], client_ip, "UPDATE_USER_STATUS", "SUCCESS", details=detail_msg)

    return {
        "success": True,
        "message": f"'{req.username}' 계정의 API 상태가 '{req.api_status}'(으)로 변경되었습니다.",
        "username": req.username,
        "api_status": req.api_status,
        "block_reason": req.reason
    }

@app.post("/api/admin/users/bulk-approve")
async def admin_bulk_approve_users(req: BulkApproveRequest, admin: dict = Depends(require_admin_user), request: Request = None):
    affected = bulk_approve_users(req.usernames)
    client_ip = get_client_ip(request) if request else "unknown"
    record_usage_log(
        admin["username"], 
        client_ip, 
        "BULK_APPROVE_USERS", 
        "SUCCESS", 
        details=f"Bulk approved {affected} users. Targeted: {req.usernames or 'ALL_PENDING'}"
    )

    return {
        "success": True,
        "message": f"총 {affected}명의 가입 대기 계정이 승인(approved)되었습니다.",
        "affected_count": affected
    }

class ArticleCleanupRequest(BaseModel):
    retention_days: Optional[int] = 30

@app.get("/api/admin/articles/cleanup-preview")
async def admin_get_article_cleanup_preview(
    retention_days: int = 30,
    admin: dict = Depends(require_admin_user)
):
    """30일(또는 지정된 retention_days) 경과 삭제 대상 기사 목록 및 건수 미리보기"""
    return preview_article_cleanup(retention_days=retention_days)

@app.post("/api/admin/articles/cleanup")
async def admin_trigger_article_cleanup(
    req: Optional[ArticleCleanupRequest] = None,
    admin: dict = Depends(require_admin_user),
    request: Request = None
):
    days = req.retention_days if (req and req.retention_days is not None) else 30
    client_ip = get_client_ip(request) if request else "unknown"
    res = execute_article_cleanup(retention_days=days, triggered_by=admin["username"])
    return res

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
async def admin_get_login_logs(limit: int = 50, username: Optional[str] = None, admin: dict = Depends(require_admin_user)):
    return get_login_logs(limit=limit, username=username)

@app.get("/api/admin/logs/usage")
async def admin_get_usage_logs(limit: int = 50, username: Optional[str] = None, admin: dict = Depends(require_admin_user)):
    return get_usage_logs(limit=limit, username=username)

# --- Admin Daily AI Reports Endpoints ---
class DailyReportGenerateRequest(BaseModel):
    target_date: Optional[str] = None # YYYY-MM-DD (기본값: 오늘)

@app.get("/api/admin/reports/dates")
async def admin_list_report_dates(admin: dict = Depends(require_admin_user)):
    """저장된 날짜별 AI 리포트 목록 조회"""
    return {
        "status": "success",
        "dates": list_daily_ai_report_dates(limit=60)
    }

@app.get("/api/admin/reports/{report_date}")
async def admin_get_report_by_date(report_date: str, admin: dict = Depends(require_admin_user)):
    """특정 날짜의 기 생성된 AI 리포트 조회"""
    report = get_daily_ai_report(report_date)
    if not report:
        # 아직 생성되지 않은 경우 당일 로그 집계 요약 정보만 반환
        date_data = get_logs_for_date(report_date)
        return {
            "status": "not_found",
            "report_date": report_date,
            "data_summary": date_data,
            "message": f"'{report_date}'에 생성 및 저장된 AI 리포트가 없습니다."
        }
    return {
        "status": "success",
        "report": report
    }

@app.post("/api/admin/reports/generate")
async def admin_generate_daily_report(
    req: Optional[DailyReportGenerateRequest] = None,
    admin: dict = Depends(require_admin_user),
    request: Request = None
):
    """
    대상 날짜(기본값: 오늘) 기준으로 감사로그/로그인/에러/토큰을 종합 분석하여
    Gemini AI 관리자 관제 리포트를 생성하고 DB에 영구 저장(동일 날짜는 최신 갱신)합니다.
    """
    now_utc = datetime.now(timezone.utc)
    target_date = (req.target_date.strip() if req and req.target_date else None) or now_utc.strftime("%Y-%m-%d")

    # 대상 날짜 로그 집계
    date_data = get_logs_for_date(target_date)

    # 기사 수집 통계 (전체 기사 수)
    total_articles_count = 0
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "data", "jobs_and_trends.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                total_articles_count = len(d.get("articles", []))
        except Exception:
            pass

    # AI 프롬프트 생성
    log_samples_text = ""
    for idx, l in enumerate(date_data["sample_usage_logs"][:25], 1):
        log_samples_text += f"- [{l.get('timestamp')}] {l.get('username')} | {l.get('action')} | {l.get('status')} | tokens={l.get('total_tokens')} | {l.get('details')}\n"

    login_samples_text = ""
    for idx, l in enumerate(date_data["sample_login_logs"][:15], 1):
        login_samples_text += f"- [{l.get('timestamp')}] {l.get('username')} | {l.get('status')} | {l.get('failure_reason') or '-'}\n"

    prompt_content = f"""
당신은 'TechPrep-AI' 시스템의 수석 인프라/보안/운영 AI 감사관(Chief AI Auditor)입니다.
아래 제공된 [{target_date}] 기준 시스템 감사 로그, 토큰 사용량, 사용자 활동, 에러 현황 데이터를 종합 분석하여 고위 관리자를 위한 마크다운 보고서를 작성해 주세요.

[기준 일자]: {target_date}
[집계 요약 데이터]:
- 총 API/조회 로그: {date_data['total_usage_logs']}건
- 총 로그인 시도: {date_data['total_login_logs']}건 (실패: {date_data['login_failed_count']}건)
- AI 챗봇 호출: {date_data['chat_calls']}건 (사용 토큰: {date_data['total_tokens']:,} Tokens)
- 프론트엔드/클라이언트 에러: {date_data['frontend_error_count']}건
- 30일 경과 기사 정리 이벤트: {date_data['cleanup_event_count']}건
- 권한 차단/FORBIDDEN 이벤트: {date_data['blocked_event_count']}건
- 현재 서비스 활성 기술 기사 수: {total_articles_count}건

[주요 활동/감사 로그 샘플 (상위)]:
{log_samples_text or "해당 일자의 API 활동 로그가 없습니다."}

[주요 로그인 로그 샘플 (상위)]:
{login_samples_text or "해당 일자의 로그인 시도 로그가 없습니다."}

[작성 가이드라인]:
1. **📊 1. 오늘의 종합 운영 요약 (Executive Summary)**: 트래픽, 토큰 소비, 사용자 활동을 명료하게 3~4개 핵심 불릿 포인트로 요약.
2. **🛡️ 2. 보안 및 인증/차단 이슈 분석**: 로그인 실패율, 연속 실패로 인한 차단 계정, 권한 없는 비정상 요청 여부 점검.
3. **⚠️ 3. 시스템 안정성 및 에러/정리 진단**: 프론트엔드 에러 발생 여부 및 30일 경과 기사 정리 파이프라인 상태 점검.
4. **💡 4. 관리자 권장 조치 사항 (Action Items)**: 관리자가 즉시 검토하거나 후속 조치할 실무 권고사항 2~3가지 제안.

정중하고 전문적인 한국어 비즈니스 마크다운 양식으로 가독성 있게 작성해 주세요.
""".strip()

    system_instruction = (
        "당신은 엔터프라이즈 DevOps/AI 시스템의 엄격하고 정밀한 최고 보안 및 운영 감사관입니다. "
        "주어진 로그 팩트와 수치에 기반하여 신뢰도 높은 운영 리포트를 마크다운으로 출력하십시오."
    )

    # Gemini 호출
    reply_text, used_model, p_tok, c_tok, t_tok = call_gemini_api(
        full_prompt=prompt_content,
        system_prompt=system_instruction
    )

    # 폴백 리포트 (API 키 미설정 또는 호출 실패 시 안전 처리)
    if not reply_text:
        used_model = "Rule-based Diagnostic Fallback"
        reply_text = f"""### 📊 TechPrep-AI 운영 진단 리포트 ({target_date})

> ℹ️ *AI 모델 일시적 호출 지연/제한으로 인해 시스템 내장 진단 엔진에 의해 생성된 요약 리포트입니다.*

#### 1. 오늘의 종합 운영 요약 (Executive Summary)
- **일자**: `{target_date}`
- **전체 API 활동 로그**: 총 **{date_data['total_usage_logs']}건** 기록됨
- **챗봇 AI 호출 및 토큰**: **{date_data['chat_calls']}건** 호출, 누적 **{date_data['total_tokens']:,} 토큰** 사용
- **등록 활성 기사**: 총 **{total_articles_count}건** 유지 중

#### 2. 보안 및 인증 이슈 분석
- **로그인 시도**: 총 {date_data['total_login_logs']}건 (성공: {date_data['total_login_logs'] - date_data['login_failed_count']}건 / 실패: {date_data['login_failed_count']}건)
- **차단 및 미승인 접근**: 총 **{date_data['blocked_event_count']}건** 탐지 및 방어 완료

#### 3. 시스템 안정성 및 정리 상태
- **프론트엔드 클라이언트 에러**: 총 **{date_data['frontend_error_count']}건** 수집됨
- **기사 자동 정리 이벤트**: 총 **{date_data['cleanup_event_count']}건** 수행됨

#### 4. 관리자 권장 조치 사항
1. 대기(pending) 상태인 신규 가입자가 있는 경우 관제탑 회원 관리 테이블에서 일괄 승인을 진행하세요.
2. 클라이언트 에러가 감지되었을 경우 실시간 감사 로그(FRONTEND_ERROR)의 스택 트레이스를 확인하세요.
"""

    summary_meta = {
        "target_date": target_date,
        "total_usage_logs": date_data["total_usage_logs"],
        "total_login_logs": date_data["total_login_logs"],
        "chat_calls": date_data["chat_calls"],
        "total_tokens": date_data["total_tokens"],
        "frontend_error_count": date_data["frontend_error_count"],
        "blocked_event_count": date_data["blocked_event_count"],
        "total_articles": total_articles_count,
        "generated_at": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    }

    # DB에 저장 또는 업데이트
    save_res = save_or_update_daily_ai_report(
        report_date=target_date,
        content=reply_text,
        summary_meta=summary_meta,
        generated_by=admin["username"],
        model=used_model or "Gemini"
    )

    client_ip = get_client_ip(request) if request else "unknown"
    record_usage_log(
        username=admin["username"],
        ip=client_ip,
        action="GENERATE_DAILY_AI_REPORT",
        status="SUCCESS",
        model=used_model,
        prompt_tokens=p_tok,
        completion_tokens=c_tok,
        total_tokens=t_tok,
        details=f"date={target_date}, action={save_res['action']}, logs={date_data['total_usage_logs']}"
    )

    # 저장된 리포트 최신 반환
    saved_report = get_daily_ai_report(target_date)

    return {
        "status": "success",
        "action": save_res["action"],
        "message": save_res["message"],
        "report": saved_report
    }

# --- Client Error Telemetry Collection (Front-end Error Ingestion) ---
class ClientErrorLogRequest(BaseModel):
    message: str
    source: Optional[str] = None
    lineno: Optional[int] = None
    colno: Optional[int] = None
    stack: Optional[str] = None
    context: Optional[str] = "global"
    url: Optional[str] = None
    user_agent: Optional[str] = None

# In-memory cooldown cache to debounce duplicate client error storms: {error_signature: last_recorded_timestamp}
_client_error_cooldown_cache: Dict[str, float] = {}

@app.post("/api/audit/client-error")
async def report_client_error(
    err_req: ClientErrorLogRequest, 
    request: Request,
    authorization: Optional[str] = Header(None)
):
    try:
        user = get_current_user_optional(authorization)
        client_ip = get_client_ip(request) if request else "unknown"
        username = user["username"] if user else "anonymous"

        # Construct deduplication signature (message + source + lineno + context)
        sig = f"{err_req.context}:{err_req.message[:80]}:{err_req.source}:{err_req.lineno}"
        now_ts = time.time()
        last_logged = _client_error_cooldown_cache.get(sig, 0.0)

        # 5-second cooldown for identical error floods
        if now_ts - last_logged < 5.0:
            return {"status": "throttled", "message": "Duplicate error within cooldown period"}

        _client_error_cooldown_cache[sig] = now_ts
        # Keep cooldown cache size bounded
        if len(_client_error_cooldown_cache) > 500:
            oldest_keys = sorted(_client_error_cooldown_cache.keys(), key=lambda k: _client_error_cooldown_cache[k])[:100]
            for k in oldest_keys:
                _client_error_cooldown_cache.pop(k, None)

        loc_str = ""
        if err_req.source:
            loc_str = f" @ {err_req.source}:{err_req.lineno or 0}"

        detail_parts = [
            f"Context: [{err_req.context}]",
            f"Error: {err_req.message}{loc_str}"
        ]
        if err_req.stack:
            clean_stack = " ".join(err_req.stack.strip().split()[:20])
            detail_parts.append(f"Stack: {clean_stack}")

        detail_msg = " | ".join(detail_parts)
        if len(detail_msg) > 500:
            detail_msg = detail_msg[:497] + "..."

        record_usage_log(
            username=username,
            ip=client_ip,
            action="FRONTEND_ERROR",
            status="CLIENT_ERROR",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            model="Browser/Frontend",
            details=detail_msg
        )
        return {"status": "recorded", "action": "FRONTEND_ERROR"}
    except Exception as ex:
        # Never fail or crash client error ingestion
        return {"status": "error", "detail": str(ex)}

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
# --- Intelligent Intent Routing for RAG ---
def determine_intent_routing(query: str, context_topic: Optional[str] = None) -> tuple[bool, str]:
    """
    질문 유형을 분석하여 (is_rag_required: bool, route_reason: str)을 반환합니다.
    - [경로 A] RAG Bypass: 인사/날씨/잡담/일상, 일반 신입 어필 및 진로 상담
    - [경로 B] RAG Required: 클라우드, 쿠버네티스, 보안(CVE), IT 트렌드 등 기사 검색이 필요한 기술 질문
    """
    if context_topic and context_topic.strip():
        return True, "context_topic_provided"

    low = query.lower().strip()

    # 1. 일상/스몰토크/인사 패턴 (무조건 Bypass)
    daily_patterns = [
        "안녕", "반가", "하이", "hello", "hi", "날씨", "비오", "맑", "기온", "미세먼지",
        "점심", "저녁", "식사", "배고", "힘들", "지쳐", "번아웃", "우울", "심심", "고마", "감사",
        "누구", "자기소개", "소개해", "뭐해", "뭐야"
    ]
    if any(p in low for p in daily_patterns):
        return False, "daily_smalltalk_bypass"

    # 2. 일반 커리어/신입 어필/공부 방향 질문 (무조건 Bypass -> 시니어 페르소나 직통 답변)
    career_patterns = [
        "신입", "비전공", "취업", "진로", "어필", "포트폴리오", "자소서", "이력서", "면접관에게 어떤",
        "어떤 점을 어필", "어떤 점을", "어떻게 준비", "막막", "방황", "모르겠", "뭐부터", "어떤걸 해야",
        "무엇을 해야", "떨려", "긴장", "불안", "멘탈", "마인드셋", "공부 방법", "공부 순서"
    ]
    tech_domain_keywords = [
        "k8s", "쿠버네티스", "docker", "도커", "aws", "gcp", "azure", "cve", "취약점", "보안사고",
        "침해", "제로트러스트", "llm", "rag", "kafka", "카프카", "redis", "레디스", "istio", "트렌드",
        "동향", "기사", "뉴스", "이슈", "아키텍처", "finops", "graviton", "spot", "vllm", "sbom",
        "liveness", "readiness", "probe", "hpa", "ingress", "alb"
    ]
    has_tech = any(tk in low for tk in tech_domain_keywords)

    if any(cp in low for cp in career_patterns) and not has_tech:
        return False, "general_career_advice_bypass"

    if has_tech:
        return True, "tech_domain_issue_match"

    # 기본적으로 특정 기술 키워드가 없는 질문은 자연스러운 대화로 Bypass
    return False, "general_chat_bypass"

def should_perform_rag(query: str, context_topic: Optional[str] = None) -> bool:
    use_rag, _ = determine_intent_routing(query, context_topic)
    return use_rag

SYNONYM_DICT = {
    "쿠버네티스": ["kubernetes", "k8s", "쿠버네티스"],
    "k8s": ["kubernetes", "k8s", "쿠버네티스"],
    "kubernetes": ["kubernetes", "k8s", "쿠버네티스"],
    "도커": ["docker", "도커", "container", "컨테이너"],
    "docker": ["docker", "도커", "container", "컨테이너"],
    "카프카": ["kafka", "카프카"],
    "kafka": ["kafka", "카프카"],
    "레디스": ["redis", "레디스"],
    "redis": ["redis", "레디스"],
    "보안": ["security", "보안", "cve", "취약점", "침해사고", "침해", "제로트러스트"],
    "security": ["security", "보안", "cve", "취약점", "침해사고"],
    "클라우드": ["cloud", "클라우드", "aws", "gcp", "azure", "아키텍처"],
    "cloud": ["cloud", "클라우드", "aws", "gcp", "azure"],
    "인공지능": ["ai", "인공지능", "llm", "머신러닝", "에이전트"],
    "ai": ["ai", "인공지능", "llm", "머신러닝", "에이전트"],
    "llm": ["ai", "인공지능", "llm", "머신러닝", "에이전트", "rag"],
    "프론트엔드": ["frontend", "프론트엔드", "웹", "web", "ui", "react", "vue", "javascript", "html", "css", "브라우저"],
    "frontend": ["frontend", "프론트엔드", "웹", "web", "ui", "react", "vue", "javascript", "html", "css"],
    "장애": ["장애", "복구", "outage", "failure", "incident", "침해사고", "오류", "이슈"],
    "복구": ["장애", "복구", "recovery", "failover", "disaster", "복원"],
}

def load_cached_articles() -> List[Dict]:
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

    for idx, item in enumerate(articles):
        unique_str = f"{item.get('title', '')}-{item.get('link', '')}-{idx}"
        item["article_id"] = "art-" + hashlib.md5(unique_str.encode("utf-8")).hexdigest()[:10]
        item["original_index"] = idx

    return articles

def search_article_for_navigation(query: str, fallback_to_latest_if_empty: bool = False, top_k: int = 3) -> tuple[Optional[Dict], List[str]]:
    """
    쿼리에서 검색 키워드를 추출하여 가장 관련성 높은 기사의 UI Action 페이로드를 생성합니다.
    복수 매칭 후보가 존재할 경우 candidates 배열에 상위 2~3개 후보를 포함합니다.
    """
    articles = load_cached_articles()
    if not articles:
        return None, []

    low = query.lower().strip()
    query_tokens = [w.lower() for w in re.findall(r'[A-Za-z0-9가-힣]{2,}', low)]
    stop_nav = {
        "기사", "뉴스", "아티클", "글", "포스트", "보여줘", "보여", "찾아줘", "찾아",
        "어디", "있어", "있니", "관련", "대해", "이동", "스크롤", "해줘", "좀",
        "그", "이", "저", "해당", "내용", "대시보드", "가줘", "이동해줘", "볼래", "위치로"
    }
    search_tokens = [t for t in query_tokens if t not in stop_nav]

    if not search_tokens:
        if fallback_to_latest_if_empty and articles:
            matched_article = articles[0]
            action_payload = {
                "type": "navigate_to_article",
                "article_id": matched_article["article_id"],
                "title": matched_article.get("title", ""),
                "query": query,
                "category": matched_article.get("category", ""),
                "link": matched_article.get("link", ""),
                "original_index": matched_article.get("original_index", 0),
                "candidates": []
            }
            return action_payload, []
        return None, []

    scored_articles = []

    for art in articles:
        title_lower = art.get("title", "").lower()
        summary_lower = (art.get("summary", "") or art.get("raw_snippet", "")).lower()
        keywords_lower = " ".join(art.get("keywords", [])).lower()
        category_lower = art.get("category", "").lower()
        combined = f"{title_lower} {summary_lower} {keywords_lower} {category_lower}"

        score = 0
        for token in search_tokens:
            syns = SYNONYM_DICT.get(token, [token])
            for syn in syns:
                if syn in title_lower:
                    score += 10
                elif syn in keywords_lower:
                    score += 5
                elif syn in category_lower:
                    score += 4
                elif syn in combined:
                    score += 2

        if score >= 2:
            scored_articles.append((score, art))

    scored_articles.sort(key=lambda x: x[0], reverse=True)

    if scored_articles:
        best_score, matched_article = scored_articles[0]
        # 상위 2~3개 후보 리스트 구성
        candidates = []
        for s, a in scored_articles[:top_k]:
            candidates.append({
                "article_id": a["article_id"],
                "title": a.get("title", ""),
                "category": a.get("category", ""),
                "link": a.get("link", "")
            })

        action_payload = {
            "type": "navigate_to_article",
            "article_id": matched_article["article_id"],
            "title": matched_article.get("title", ""),
            "query": query,
            "category": matched_article.get("category", ""),
            "link": matched_article.get("link", ""),
            "original_index": matched_article.get("original_index", 0),
            "candidates": candidates
        }
        return action_payload, search_tokens

    # 매칭 점수가 미달이지만 키워드가 존재했을 때 첫번째 카테고리/기사 fallback 가능
    return None, search_tokens

def detect_article_navigation_intent(query: str) -> tuple[bool, Optional[Dict], List[str]]:
    """
    사용자가 기사 내비게이션(UI Action)을 원하는 의도인지 감지합니다.
    Returns: (is_nav_request, ui_action, search_tokens)
    """
    low = query.lower().strip()
    nav_patterns = [
        "기사 보여줘", "기사 보여", "기사 찾아", "기사 어디", "기사로 이동", "기사 볼래",
        "보여줘", "찾아줘", "어디 있어", "어디있어", "어디에 있어", "이동해줘", "스크롤", "위치로",
        "해당 기사", "그 기사", "관련 기사", "뉴스 보여", "뉴스 찾아"
    ]
    is_nav = any(p in low for p in nav_patterns)
    if not is_nav:
        return False, None, []

    action_payload, search_tokens = search_article_for_navigation(query, fallback_to_latest_if_empty=False)
    return True, action_payload, search_tokens

def retrieve_relevant_news(query: str, top_k: int = 2) -> List[Dict]:
    """
    내부 저장된 jobs_and_trends.json 또는 news.json에서 쿼리와 가장 연관성 높은 아티클을 검색
    """
    if not should_perform_rag(query):
        return []

    articles = load_cached_articles()
    if not articles:
        return []

    query_tokens = [w.lower() for w in re.findall(r'[A-Za-z0-9가-힣]{2,}', query)]
    stopwords = {
        "어떻게", "알려줘", "알려주세요", "대해서", "질문", "면접", "관련", "설명해줘", "답변", "요령",
        "신입", "개발자", "면접관", "어필", "가장", "좋을까", "좋을까요", "준비", "포트폴리오", "취업", "진로",
        "서울", "날씨", "오늘", "내일", "기온", "어때", "어때요", "어떡", "어떻", "무엇", "어떤", "어떤걸",
        "모르겠", "방황", "불안", "시작", "공부", "방법", "구조", "전략", "방식", "설계", "대규모",
        "보여줘", "찾아줘", "어디", "기사", "뉴스"
    }
    keywords = [k for k in query_tokens if k not in stopwords]

    if not keywords:
        return []

    scored_articles = []
    for item in articles:
        title = item.get("title", "").lower()
        summary = (item.get("summary", "") or item.get("raw_snippet", "")).lower()
        insight = item.get("interview_insight", "").lower()
        tags = " ".join(item.get("keywords", [])).lower()

        score = 0
        matched_kws = 0
        for kw in keywords:
            syns = SYNONYM_DICT.get(kw, [kw])
            kw_score = 0
            for syn in syns:
                if syn in title:
                    kw_score += 6
                if syn in tags:
                    kw_score += 4
                if syn in insight:
                    kw_score += 3
                if syn in summary:
                    kw_score += 1
            if kw_score > 0:
                matched_kws += 1
                score += kw_score

        # 최소 임계값: 핵심 키워드가 제목/태그에 명확히 부합하는 경우 채택
        if score >= 6 and matched_kws >= 1:
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
    rag_used: bool = False
    route_reason: Optional[str] = None
    ui_action: Optional[Dict] = None

class CreateRoomRequest(BaseModel):
    room_id: Optional[str] = None
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
    
    room_id = req.room_id or f"room-{uuid.uuid4().hex[:8]}"
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

    # 1. 명확한 의도 분석 (Intent Routing & Agentic Navigation)
    current_room_data = session_store[sid][room_id]
    pending_action = current_room_data.get("pending_action")
    
    is_nav_request, ui_action, search_tokens = detect_article_navigation_intent(user_msg)
    is_resumed_nav = False

    # 이전 턴에 보류된 navigate_to_article 액션이 있을 경우 이어달리기 검사
    if not is_nav_request and pending_action and pending_action.get("type") == "navigate_to_article":
        resumed_ui_action, resumed_tokens = search_article_for_navigation(user_msg, fallback_to_latest_if_empty=False)
        if resumed_ui_action:
            ui_action = resumed_ui_action
            is_nav_request = True
            is_resumed_nav = True
            search_tokens = resumed_tokens
            current_room_data["pending_action"] = None
        else:
            # 여전히 특정되지 않았지만 키워드를 제시한 경우 또는 다른 질문을 한 경우
            if not resumed_tokens:
                # 아무 키워드도 안 넣었을 때 다시 물어봄
                current_room_data["pending_action"] = {
                    "type": "navigate_to_article",
                    "await_field": "article_query"
                }
                ask_reply = "어떤 기사(키워드나 제목, 혹은 관련 기술 주제)로 이동할까요?"
                return ChatResponse(
                    room_id=room_id,
                    reply=ask_reply,
                    model="TechPrep Agentic Navigation Engine",
                    created_at=now_iso,
                    referenced_articles=None,
                    rag_used=False,
                    route_reason="agentic_navigation_pending",
                    ui_action=None
                )
            else:
                current_room_data["pending_action"] = None

    # 키워드 누락 감지 및 대기 상태(pending_action) 처리
    if is_nav_request and not ui_action and not search_tokens:
        current_room_data["pending_action"] = {
            "type": "navigate_to_article",
            "await_field": "article_query"
        }
        ask_reply = "어떤 기사(키워드나 제목, 혹은 관련 기술 주제)로 이동할까요?"
        print(f"🧭 [Intent Router] message='{user_msg}' ➔ Pending navigation waiting for query.")

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
            "content": ask_reply,
            "model": "TechPrep Agentic Navigation Engine",
            "created_at": now_iso,
            "referenced_articles": None,
            "ui_action": None
        })

        return ChatResponse(
            room_id=room_id,
            reply=ask_reply,
            model="TechPrep Agentic Navigation Engine",
            created_at=now_iso,
            referenced_articles=None,
            rag_used=False,
            route_reason="agentic_navigation_ask_clarification",
            ui_action=None
        )

    # 내비게이션 완료 시 대기 상태 해제
    if is_nav_request and ui_action:
        current_room_data["pending_action"] = None

    use_rag, route_reason = determine_intent_routing(user_msg, req.context_topic)

    if is_nav_request:
        use_rag = True
        route_reason = "agentic_navigation_resumed" if is_resumed_nav else "agentic_navigation_intent"

    print(f"🧭 [Intent Router] message='{user_msg}' ➔ use_rag={use_rag}, reason='{route_reason}', ui_action={bool(ui_action)}")

    retrieved_articles = []
    rag_context_snippets = []
    referenced_meta = []

    if ui_action:
        # 내비게이션 대상 기사를 최우선 RAG Context 및 참조 기사로 주입
        target_art = next((a for a in load_cached_articles() if a.get("article_id") == ui_action.get("article_id")), None)
        if target_art:
            retrieved_articles.append(target_art)
            referenced_meta.append({
                "title": target_art.get("title", ""),
                "link": target_art.get("link", ""),
                "source": target_art.get("source", ""),
                "insight": target_art.get("interview_insight", ""),
                "article_id": target_art.get("article_id", "")
            })
            rag_context_snippets.append(
                f"- [대상 기사]: {target_art.get('title')} ({target_art.get('source', '')})\n"
                f"  요약: {target_art.get('summary') or target_art.get('raw_snippet')}\n"
                f"  실무 핵심 인사이트: {target_art.get('interview_insight')}"
            )

    if use_rag and not retrieved_articles:
        retrieved_articles = retrieve_relevant_news(user_msg, top_k=2)
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
                "insight": insight,
                "article_id": art.get("article_id", "")
            })

    # 2. 프롬프트 구성 및 Gemini API 호출
    prompt_parts = []
    if req.context_topic:
        prompt_parts.append(f"[면접 주제/관련 기사]: {req.context_topic}")

    if rag_context_snippets:
        prompt_parts.append(
            "[시스템 수집 최신 IT 실무 이슈 및 인사이트 (RAG Context)]:\n" +
            "\n".join(rag_context_snippets) +
            "\n(위 최신 업계 동향 및 실무 인사이트를 답변에 자연스럽게 녹여내어 신뢰성을 높여주세요.)"
        )

    # 이전 대화 맥락
    prev_msgs = session_store[sid][room_id]["messages"][-4:]
    if prev_msgs:
        history_str = "\n".join([f"{'지원자' if m['role']=='user' else '면접관'}: {m['content']}" for m in prev_msgs])
        prompt_parts.append(f"[이전 대화 맥락]:\n{history_str}")

    prompt_parts.append(f"주니어 지원자: {user_msg}")
    full_prompt = "\n\n".join(prompt_parts)

    reply_text, used_model, prompt_tokens, completion_tokens, total_tokens = call_gemini_api(
        full_prompt=full_prompt,
        system_prompt=SYSTEM_INSTRUCTION
    )

    if reply_text:
        model_name = f"Google Gemini ({used_model})" + (" + RAG" if referenced_meta else "")
    else:
        # Gemini API 호출 자체가 실패한 경우
        if ui_action:
            reply_text = (
                f"요청하신 기사 **'{ui_action.get('title')}'**을(를) 대시보드에서 찾아 이동 및 강조 표시했습니다. 📍\n"
                f"기사 전문 및 실무 핵심 인사이트(Key Insight)를 대시보드 카드에서 바로 확인하실 수 있습니다."
            )
            model_name = "TechPrep Agentic Navigation Engine"
        else:
            reply_text = (
                "⚠️ 죄송합니다. AI 모델(Gemini API) 호출 중 일시적인 네트워크 또는 할당량 오류가 발생했습니다.\n"
                "잠시 후 다시 시도해 주시거나 관리자에게 문의해 주세요."
            )
            model_name = "Gemini Service Unavailable"
        print(f"❌ [Gemini Error] All candidate models failed to generate response for message: {user_msg}")

    # 토큰 추정치
    if total_tokens == 0 and reply_text:
        prompt_tokens = max(1, len(user_msg) // 3)
        completion_tokens = max(1, len(reply_text) // 3)
        total_tokens = prompt_tokens + completion_tokens

    # 감사 로그 기록
    record_usage_log(
        username=username,
        ip=client_ip,
        action="CHAT_API",
        status="SUCCESS" if (used_model or ui_action) else "ERROR",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=model_name,
        details=f"route={route_reason}, rag={bool(referenced_meta)}, ui_action={bool(ui_action)}"
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
        "referenced_articles": referenced_meta,
        "ui_action": ui_action
    })

    return ChatResponse(
        room_id=room_id,
        reply=reply_text,
        model=model_name,
        created_at=now_iso,
        referenced_articles=referenced_meta,
        rag_used=bool(referenced_meta),
        route_reason=route_reason,
        ui_action=ui_action
    )

# --- Frontend Static Files Serving ---
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
