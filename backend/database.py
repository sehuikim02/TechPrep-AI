import os
import sqlite3
import datetime
import bcrypt
import jwt
from typing import Optional, Dict, Any, List

# PostgreSQL (Supabase, Neon, Render Postgres 등) 연결 지원
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# SQLite 로컬 파일 경로 (DATABASE_URL 미지정 시 기본 사용)
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "app.db")
DB_PATH = os.environ.get("SQLITE_DB_PATH", DEFAULT_DB_PATH).strip()

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "techprep-ai-super-secret-jwt-key-2026-secure-32bytes")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 72

def is_postgres() -> bool:
    return bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))

def get_db_connection():
    if is_postgres():
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError("psycopg2 is required for PostgreSQL. Please install psycopg2-binary.")
        # Render/Supabase sslmode 지원
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
        conn.autocommit = True
        return conn
    else:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode('utf-8')[:72]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None

def init_db():
    use_pg = is_postgres()
    conn = get_db_connection()
    cursor = conn.cursor()

    if use_pg:
        print("🔌 Connected to External PostgreSQL database (Persistent across restarts).")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            api_status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_logs (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            ip_address TEXT,
            status TEXT NOT NULL,
            failure_reason TEXT,
            timestamp TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_logs (
            id SERIAL PRIMARY KEY,
            username TEXT,
            ip_address TEXT,
            action TEXT NOT NULL,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            model TEXT,
            status TEXT NOT NULL,
            details TEXT,
            timestamp TEXT NOT NULL
        )
        """)
    else:
        print(f"📁 Connected to SQLite database at: {DB_PATH}")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            api_status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ip_address TEXT,
            status TEXT NOT NULL,
            failure_reason TEXT,
            timestamp TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            ip_address TEXT,
            action TEXT NOT NULL,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            model TEXT,
            status TEXT NOT NULL,
            details TEXT,
            timestamp TEXT NOT NULL
        )
        """)
        conn.commit()

    # Seed Admin User if not exists
    admin_user = os.environ.get("ADMIN_USERNAME", "admin").strip()
    admin_pass = os.environ.get("ADMIN_PASSWORD", "admin1234").strip()

    placeholder = "%s" if use_pg else "?"
    cursor.execute(f"SELECT id, role, api_status FROM users WHERE username = {placeholder}", (admin_user,))
    row = cursor.fetchone()
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    if not row:
        pw_hash = hash_password(admin_pass)
        cursor.execute(
            f"INSERT INTO users (username, password_hash, role, api_status, created_at, updated_at) VALUES ({placeholder}, {placeholder}, 'admin', 'approved', {placeholder}, {placeholder})",
            (admin_user, pw_hash, now_iso, now_iso)
        )
        if not use_pg:
            conn.commit()
        print(f"✅ Initial Admin user '{admin_user}' seeded successfully with role='admin' & api_status='approved'.")
    else:
        if row["role"] != "admin" or row["api_status"] != "approved":
            cursor.execute(f"UPDATE users SET role = 'admin', api_status = 'approved', updated_at = {placeholder} WHERE username = {placeholder}", (now_iso, admin_user))
            if not use_pg:
                conn.commit()

    conn.close()

# DB Query Helpers
def get_user_by_username(username: str) -> Optional[dict]:
    use_pg = is_postgres()
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if use_pg else "?"
    cursor.execute(f"SELECT * FROM users WHERE username = {ph}", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(username: str, password_hash: str, role: str = "user", api_status: str = "pending") -> dict:
    use_pg = is_postgres()
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    ph = "%s" if use_pg else "?"
    
    if use_pg:
        cursor.execute(
            f"INSERT INTO users (username, password_hash, role, api_status, created_at, updated_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}) RETURNING id",
            (username, password_hash, role, api_status, now_iso, now_iso)
        )
        user_id = cursor.fetchone()["id"]
    else:
        cursor.execute(
            f"INSERT INTO users (username, password_hash, role, api_status, created_at, updated_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (username, password_hash, role, api_status, now_iso, now_iso)
        )
        user_id = cursor.lastrowid
        conn.commit()
    
    conn.close()
    return {
        "id": user_id,
        "username": username,
        "role": role,
        "api_status": api_status,
        "created_at": now_iso,
        "updated_at": now_iso
    }

def update_user_api_status(username: str, new_status: str) -> bool:
    use_pg = is_postgres()
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    ph = "%s" if use_pg else "?"
    cursor.execute(f"UPDATE users SET api_status = {ph}, updated_at = {ph} WHERE username = {ph}", (new_status, now_iso, username))
    affected = cursor.rowcount
    if not use_pg:
        conn.commit()
    conn.close()
    return affected > 0

def list_all_users() -> List[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, api_status, created_at, updated_at FROM users ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def record_login_log(username: str, ip: str, status: str, failure_reason: Optional[str] = None):
    try:
        use_pg = is_postgres()
        conn = get_db_connection()
        cursor = conn.cursor()
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ph = "%s" if use_pg else "?"
        cursor.execute(
            f"INSERT INTO login_logs (username, ip_address, status, failure_reason, timestamp) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
            (username, ip, status, failure_reason, now_iso)
        )
        if not use_pg:
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to record login log: {e}")

def record_usage_log(username: Optional[str], ip: str, action: str, status: str, 
                     prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0, 
                     model: Optional[str] = None, details: Optional[str] = None):
    try:
        use_pg = is_postgres()
        conn = get_db_connection()
        cursor = conn.cursor()
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ph = "%s" if use_pg else "?"
        cursor.execute(
            f"""INSERT INTO usage_logs 
               (username, ip_address, action, status, prompt_tokens, completion_tokens, total_tokens, model, details, timestamp) 
               VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
            (username or "anonymous", ip, action, status, prompt_tokens, completion_tokens, total_tokens, model, details, now_iso)
        )
        if not use_pg:
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to record usage log: {e}")

def get_login_logs(limit: int = 100) -> List[dict]:
    use_pg = is_postgres()
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if use_pg else "?"
    cursor.execute(f"SELECT * FROM login_logs ORDER BY id DESC LIMIT {ph}", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_usage_logs(limit: int = 100) -> List[dict]:
    use_pg = is_postgres()
    conn = get_db_connection()
    cursor = conn.cursor()
    ph = "%s" if use_pg else "?"
    cursor.execute(f"SELECT * FROM usage_logs ORDER BY id DESC LIMIT {ph}", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_security_and_usage_stats() -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()

    # User activity summary
    cursor.execute("""
        SELECT 
            u.username,
            u.role,
            u.api_status,
            COALESCE(SUM(CASE WHEN l.status = 'SUCCESS' THEN 1 ELSE 0 END), 0) AS login_success_count,
            COALESCE(SUM(CASE WHEN l.status = 'FAILED' THEN 1 ELSE 0 END), 0) AS login_failed_count,
            MAX(l.timestamp) AS last_login_at
        FROM users u
        LEFT JOIN login_logs l ON u.username = l.username
        GROUP BY u.username, u.role, u.api_status
    """)
    user_stats = [dict(r) for r in cursor.fetchall()]

    # Usage summary by user
    cursor.execute("""
        SELECT 
            username,
            COALESCE(SUM(CASE WHEN action = 'DASHBOARD_VIEW' THEN 1 ELSE 0 END), 0) AS dashboard_views,
            COALESCE(SUM(CASE WHEN action = 'CHAT_API' AND status = 'SUCCESS' THEN 1 ELSE 0 END), 0) AS chat_calls,
            COALESCE(SUM(CASE WHEN status = 'FORBIDDEN' THEN 1 ELSE 0 END), 0) AS forbidden_calls,
            COALESCE(SUM(total_tokens), 0) AS total_tokens_used
        FROM usage_logs
        GROUP BY username
    """)
    usage_by_user = {r["username"]: dict(r) for r in cursor.fetchall()}

    # Merge user stats
    for u in user_stats:
        uname = u["username"]
        u_usage = usage_by_user.get(uname, {})
        u["dashboard_views"] = int(u_usage.get("dashboard_views", 0))
        u["chat_calls"] = int(u_usage.get("chat_calls", 0))
        u["forbidden_calls"] = int(u_usage.get("forbidden_calls", 0))
        u["total_tokens_used"] = int(u_usage.get("total_tokens_used", 0))
        u["login_success_count"] = int(u.get("login_success_count", 0))
        u["login_failed_count"] = int(u.get("login_failed_count", 0))

    # Global token usage & call count
    cursor.execute("""
        SELECT 
            COUNT(*) AS total_api_calls,
            COALESCE(SUM(prompt_tokens), 0) AS total_prompt_tokens,
            COALESCE(SUM(completion_tokens), 0) AS total_completion_tokens,
            COALESCE(SUM(total_tokens), 0) AS total_tokens
        FROM usage_logs
        WHERE action = 'CHAT_API' AND status = 'SUCCESS'
    """)
    token_row = dict(cursor.fetchone() or {})

    # Overall totals
    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()["total_users"]

    cursor.execute("SELECT COUNT(*) AS total_logins FROM login_logs WHERE status = 'SUCCESS'")
    total_logins = cursor.fetchone()["total_logins"]

    conn.close()

    db_type = "PostgreSQL" if is_postgres() else "SQLite"

    return {
        "db_type": db_type,
        "user_stats": user_stats,
        "token_usage": {
            "total_calls": int(token_row.get("total_api_calls", 0)),
            "prompt_tokens": int(token_row.get("total_prompt_tokens", 0)),
            "completion_tokens": int(token_row.get("total_completion_tokens", 0)),
            "total_tokens": int(token_row.get("total_tokens", 0))
        },
        "overview": {
            "total_users": int(total_users),
            "total_logins": int(total_logins)
        }
    }
