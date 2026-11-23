import os
import json
import sqlite3
import datetime
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

# bcrypt 및 jwt 지연/안전 import (기사 수집 등 경량 환경에서 누락 시에도 안전)
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    bcrypt = None
    BCRYPT_AVAILABLE = False

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    jwt = None
    JWT_AVAILABLE = False

# PostgreSQL 연결 지원 및 커넥션 풀링
try:
    import psycopg2
    from psycopg2 import pool
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

# PostgreSQL 전역 커넥션 풀
_PG_POOL: Optional[Any] = None

def is_postgres() -> bool:
    return bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))

def get_normalized_db_url() -> str:
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def init_pg_pool():
    global _PG_POOL
    if is_postgres() and PSYCOPG2_AVAILABLE and _PG_POOL is None:
        try:
            url = get_normalized_db_url()
            # ThreadedConnectionPool: min 2, max 10
            _PG_POOL = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                dsn=url
            )
            print("🚀 PostgreSQL Connection Pool initialized successfully (min=2, max=10).")
        except Exception as e:
            print(f"⚠️ Failed to init PostgreSQL connection pool: {e}. Will fallback to direct connections.")
            _PG_POOL = None

@contextmanager
def get_db_cursor():
    """
    고성능 컨텍스트 매니저:
    - PostgreSQL: 전역 풀에서 커넥션을 대여 후 자동 반납 (재연결 오버헤드 0)
    - SQLite: 동일 스레드 연결 및 자동 닫힘
    """
    if is_postgres():
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError("psycopg2 is required for PostgreSQL. Please install psycopg2-binary.")
        
        conn = None
        using_pool = False
        if _PG_POOL:
            try:
                conn = _PG_POOL.getconn()
                using_pool = True
            except Exception as e:
                print(f"Pool getconn failed: {e}, using direct connection.")
                conn = None

        if conn is None:
            conn = psycopg2.connect(get_normalized_db_url())

        try:
            # ping / liveness test (pool_pre_ping)
            if conn.closed:
                conn = psycopg2.connect(get_normalized_db_url())
                using_pool = False
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            yield cursor
            conn.commit()
        except Exception as err:
            try:
                conn.rollback()
            except Exception:
                pass
            raise err
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            if using_pool and _PG_POOL:
                _PG_POOL.putconn(conn)
            elif not using_pool:
                try:
                    conn.close()
                except Exception:
                    pass
    else:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception as err:
            conn.rollback()
            raise err
        finally:
            conn.close()

def hash_password(password: str) -> str:
    if not BCRYPT_AVAILABLE or bcrypt is None:
        raise RuntimeError("bcrypt is required for password hashing but is not installed.")
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not BCRYPT_AVAILABLE or bcrypt is None:
        return False
    try:
        pwd_bytes = plain_password.encode('utf-8')[:72]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(data: dict) -> str:
    if not JWT_AVAILABLE or jwt is None:
        raise RuntimeError("jwt is required for token generation but is not installed.")
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    if not JWT_AVAILABLE or jwt is None:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None

def init_db():
    """서버 시작 시 1회만 호출되어 테이블을 보장하고 관리자를 시딩합니다."""
    use_pg = is_postgres()
    if use_pg:
        init_pg_pool()

    # 1. Base Table Creation
    with get_db_cursor() as cursor:
        if use_pg:
            print("🔌 Connected to External PostgreSQL database (Persistent across restarts).")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                api_status TEXT NOT NULL DEFAULT 'pending',
                failed_login_attempts INTEGER DEFAULT 0,
                block_reason TEXT,
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

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                article_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                link TEXT UNIQUE NOT NULL,
                source TEXT,
                published TEXT,
                category TEXT,
                summary TEXT,
                keywords TEXT,
                interview_insight TEXT,
                target_role TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                article_id TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT,
                category TEXT,
                source TEXT,
                summary TEXT,
                interview_insight TEXT,
                created_at TEXT NOT NULL,
                CONSTRAINT uq_user_article UNIQUE (user_id, article_id)
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_ai_reports (
                id SERIAL PRIMARY KEY,
                report_date TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                summary_meta TEXT,
                generated_by TEXT NOT NULL,
                model TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
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
                failed_login_attempts INTEGER DEFAULT 0,
                block_reason TEXT,
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

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                link TEXT UNIQUE NOT NULL,
                source TEXT,
                published TEXT,
                category TEXT,
                summary TEXT,
                keywords TEXT,
                interview_insight TEXT,
                target_role TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                article_id TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT,
                category TEXT,
                source TEXT,
                summary TEXT,
                interview_insight TEXT,
                created_at TEXT NOT NULL,
                UNIQUE (user_id, article_id)
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_ai_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                summary_meta TEXT,
                generated_by TEXT NOT NULL,
                model TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

    # 2. Schema Migrations (Independent safe transaction with pre-checks)
    # 기존 users 테이블에 failed_login_attempts 및 block_reason 컬럼이 누락되어 있을 경우에만 안전하게 추가
    existing_cols = []
    try:
        with get_db_cursor() as cursor:
            if use_pg:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users'
                """)
                rows = cursor.fetchall()
                existing_cols = [r["column_name"].lower() for r in rows]
            else:
                cursor.execute("PRAGMA table_info(users)")
                rows = cursor.fetchall()
                existing_cols = [r[1].lower() for r in rows]
    except Exception as e:
        print(f"⚠️ Failed to inspect existing users columns: {e}")

    if "failed_login_attempts" not in existing_cols:
        try:
            with get_db_cursor() as cursor:
                cursor.execute("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
                print("✅ Added column 'failed_login_attempts' to users table.")
        except Exception as e:
            print(f"⚠️ Note: ALTER TABLE users ADD COLUMN failed_login_attempts failed or already exists: {e}")

    if "block_reason" not in existing_cols:
        try:
            with get_db_cursor() as cursor:
                cursor.execute("ALTER TABLE users ADD COLUMN block_reason TEXT")
                print("✅ Added column 'block_reason' to users table.")
        except Exception as e:
            print(f"⚠️ Note: ALTER TABLE users ADD COLUMN block_reason failed or already exists: {e}")

    # 3. Seed Admin User in a fresh, isolated transaction
    admin_user = os.environ.get("ADMIN_USERNAME", "admin").strip()
    admin_pass = os.environ.get("ADMIN_PASSWORD", "admin1234").strip()
    ph = "%s" if use_pg else "?"
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        with get_db_cursor() as cursor:
            cursor.execute(f"SELECT id, role, api_status FROM users WHERE username = {ph}", (admin_user,))
            row = cursor.fetchone()

            if not row:
                pw_hash = hash_password(admin_pass)
                cursor.execute(
                    f"INSERT INTO users (username, password_hash, role, api_status, created_at, updated_at) VALUES ({ph}, {ph}, 'admin', 'approved', {ph}, {ph})",
                    (admin_user, pw_hash, now_iso, now_iso)
                )
                print(f"✅ Initial Admin user '{admin_user}' seeded successfully with role='admin' & api_status='approved'.")
            else:
                if row["role"] != "admin" or row["api_status"] != "approved":
                    cursor.execute(
                        f"UPDATE users SET role = 'admin', api_status = 'approved', updated_at = {ph} WHERE username = {ph}",
                        (now_iso, admin_user)
                    )
                    print(f"✅ Existing admin '{admin_user}' role and status confirmed.")
    except Exception as e:
        print(f"❌ Failed to seed or verify admin user '{admin_user}': {e}")
        raise e

# DB Query Helpers
def get_user_by_username(username: str) -> Optional[dict]:
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    with get_db_cursor() as cursor:
        cursor.execute(f"SELECT * FROM users WHERE username = {ph}", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None

def create_user(username: str, password_hash: str, role: str = "user", api_status: str = "pending") -> dict:
    use_pg = is_postgres()
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    ph = "%s" if use_pg else "?"
    
    with get_db_cursor() as cursor:
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
    
    return {
        "id": user_id,
        "username": username,
        "role": role,
        "api_status": api_status,
        "created_at": now_iso,
        "updated_at": now_iso
    }

def update_user_api_status(username: str, new_status: str, block_reason: Optional[str] = None) -> bool:
    use_pg = is_postgres()
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    ph = "%s" if use_pg else "?"
    with get_db_cursor() as cursor:
        if new_status == "approved":
            cursor.execute(
                f"UPDATE users SET api_status = {ph}, failed_login_attempts = 0, block_reason = NULL, updated_at = {ph} WHERE username = {ph}",
                (new_status, now_iso, username)
            )
        elif new_status == "blocked":
            cursor.execute(
                f"UPDATE users SET api_status = {ph}, block_reason = {ph}, updated_at = {ph} WHERE username = {ph}",
                (new_status, block_reason, now_iso, username)
            )
        else:
            cursor.execute(
                f"UPDATE users SET api_status = {ph}, updated_at = {ph} WHERE username = {ph}",
                (new_status, now_iso, username)
            )
        affected = cursor.rowcount
        return affected > 0

def increment_failed_login(username: str) -> int:
    """Increments failed_login_attempts for user and returns the new count."""
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    with get_db_cursor() as cursor:
        cursor.execute(
            f"UPDATE users SET failed_login_attempts = COALESCE(failed_login_attempts, 0) + 1 WHERE username = {ph}",
            (username,)
        )
        cursor.execute(f"SELECT failed_login_attempts FROM users WHERE username = {ph}", (username,))
        row = cursor.fetchone()
        return int(row["failed_login_attempts"] if row and row["failed_login_attempts"] is not None else 0)

def reset_failed_login(username: str):
    """Resets failed_login_attempts to 0 upon successful login."""
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    with get_db_cursor() as cursor:
        cursor.execute(
            f"UPDATE users SET failed_login_attempts = 0 WHERE username = {ph}",
            (username,)
        )

def bulk_approve_users(usernames: Optional[List[str]] = None) -> int:
    """Approves multiple users. If usernames is None or empty, approves all pending users."""
    use_pg = is_postgres()
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    ph = "%s" if use_pg else "?"
    with get_db_cursor() as cursor:
        if usernames and len(usernames) > 0:
            placeholders = ", ".join([ph] * len(usernames))
            params = ["approved", 0, now_iso] + list(usernames)
            cursor.execute(
                f"UPDATE users SET api_status = {ph}, failed_login_attempts = {ph}, block_reason = NULL, updated_at = {ph} WHERE username IN ({placeholders}) AND role != 'admin'",
                tuple(params)
            )
        else:
            cursor.execute(
                f"UPDATE users SET api_status = {ph}, failed_login_attempts = 0, block_reason = NULL, updated_at = {ph} WHERE api_status = 'pending' AND role != 'admin'",
                ("approved", now_iso)
            )
        return cursor.rowcount

def list_all_users() -> List[dict]:
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, username, role, api_status, failed_login_attempts, block_reason, created_at, updated_at 
            FROM users 
            ORDER BY CASE WHEN role = 'admin' OR username = 'admin' THEN 0 ELSE 1 END, id ASC
        """)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def record_login_log(username: str, ip: str, status: str, failure_reason: Optional[str] = None):
    try:
        use_pg = is_postgres()
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ph = "%s" if use_pg else "?"
        with get_db_cursor() as cursor:
            cursor.execute(
                f"INSERT INTO login_logs (username, ip_address, status, failure_reason, timestamp) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                (username, ip, status, failure_reason, now_iso)
            )
    except Exception as e:
        print(f"Failed to record login log: {e}")

def record_usage_log(username: Optional[str], ip: str, action: str, status: str, 
                     prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0, 
                     model: Optional[str] = None, details: Optional[str] = None):
    try:
        use_pg = is_postgres()
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ph = "%s" if use_pg else "?"
        with get_db_cursor() as cursor:
            cursor.execute(
                f"""INSERT INTO usage_logs 
                   (username, ip_address, action, status, prompt_tokens, completion_tokens, total_tokens, model, details, timestamp) 
                   VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                (username or "anonymous", ip, action, status, prompt_tokens, completion_tokens, total_tokens, model, details, now_iso)
            )
    except Exception as e:
        print(f"Failed to record usage log: {e}")

# 날짜 유틸리티 import (호환성을 위해 collector.date_utils에서 가져와 재노출)
from collector.date_utils import parse_article_datetime

# ==================== Bookmarks Management Engine ====================
def toggle_user_bookmark(user_id: int, article_data: dict) -> dict:
    """
    기사 북마크를 토글(저장 ↔ 해제)합니다.
    이미 존재하면 삭제(해제), 없으면 추가(저장)하여 중복 저장을 원천 차단합니다.
    """
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    article_id = article_data.get("article_id") or ""
    title = article_data.get("title") or "기사 제목 없음"
    link = article_data.get("link") or ""
    category = article_data.get("category") or "기타"
    source = article_data.get("source") or ""
    summary = article_data.get("summary") or ""
    insight = article_data.get("interview_insight") or ""
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with get_db_cursor() as cursor:
        cursor.execute(
            f"SELECT id FROM bookmarks WHERE user_id = {ph} AND article_id = {ph}",
            (user_id, article_id)
        )
        row = cursor.fetchone()

        if row:
            # 이미 존재하므로 북마크 해제 (DELETE)
            cursor.execute(
                f"DELETE FROM bookmarks WHERE user_id = {ph} AND article_id = {ph}",
                (user_id, article_id)
            )
            return {
                "bookmarked": False,
                "article_id": article_id,
                "action": "removed",
                "message": "북마크가 해제되었습니다."
            }
        else:
            # 신규 북마크 추가 (INSERT)
            cursor.execute(
                f"""INSERT INTO bookmarks 
                   (user_id, article_id, title, link, category, source, summary, interview_insight, created_at) 
                   VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                (user_id, article_id, title, link, category, source, summary, insight, now_iso)
            )
            return {
                "bookmarked": True,
                "article_id": article_id,
                "action": "added",
                "message": "북마크에 저장되었습니다."
            }

def get_user_bookmarks(user_id: int) -> List[dict]:
    """특정 사용자가 저장한 북마크 목록을 최신순으로 반환합니다."""
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    with get_db_cursor() as cursor:
        cursor.execute(
            f"SELECT id, article_id, title, link, category, source, summary, interview_insight, created_at FROM bookmarks WHERE user_id = {ph} ORDER BY id DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        return [format_row_dict(r) for r in rows]

def get_user_bookmarked_article_ids(user_id: int) -> List[str]:
    """특정 사용자가 북마크한 기사 article_id 목록만 빠르게 조회합니다."""
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    with get_db_cursor() as cursor:
        cursor.execute(
            f"SELECT article_id FROM bookmarks WHERE user_id = {ph}",
            (user_id,)
        )
        rows = cursor.fetchall()
        return [dict(r)["article_id"] for r in rows]

def get_all_protected_bookmarked_keys() -> set:
    """30일 경과 기사 자동 삭제 시 보호할 모든 북마크 기사의 ID 및 Link 집합을 반환합니다."""
    use_pg = is_postgres()
    protected = set()
    try:
        with get_db_cursor() as cursor:
            # bookmarks 테이블 존재 확인
            if use_pg:
                cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'bookmarks'")
            else:
                cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='bookmarks'")
            if not cursor.fetchone():
                return protected

            cursor.execute("SELECT article_id, link, title FROM bookmarks")
            rows = cursor.fetchall()
            for r in rows:
                d = dict(r)
                if d.get("article_id"):
                    protected.add(d["article_id"])
                if d.get("link"):
                    protected.add(d["link"])
                if d.get("title"):
                    protected.add(d["title"])
    except Exception as ex:
        print(f"⚠️ get_all_protected_bookmarked_keys error: {ex}")
    return protected

def delete_old_articles_from_db(retention_days: int = 30) -> int:
    """PostgreSQL 및 SQLite DB의 articles 테이블에서 retention_days 초과 기사를 일괄 DELETE합니다."""
    use_pg = is_postgres()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    cutoff_dt = now_utc - datetime.timedelta(days=retention_days)
    cutoff_iso = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
    ph = "%s" if use_pg else "?"

    deleted_count = 0
    try:
        with get_db_cursor() as cursor:
            # articles 테이블 존재 여부 확인
            if use_pg:
                cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'articles'")
            else:
                cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles'")
            
            if not cursor.fetchone():
                return 0

            # 북마크로 보호 중인 기사 ID/키 목록 확인
            protected_keys = get_all_protected_bookmarked_keys()

            # 1. ISO 포맷 문자열 비교를 통한 1차 대상 추출 (북마크 보호 필터링)
            cursor.execute("SELECT id, article_id, link, title, published, created_at FROM articles")
            rows = cursor.fetchall()
            ids_to_delete = []
            for r in rows:
                row_dict = dict(r)
                art_id = row_dict.get("article_id")
                art_link = row_dict.get("link")
                art_title = row_dict.get("title")
                # 북마크 보호 기사는 제외
                if (
                    (art_id and art_id in protected_keys) or
                    (art_link and art_link in protected_keys) or
                    (art_title and art_title in protected_keys)
                ):
                    continue

                p_str = row_dict.get("published") or row_dict.get("created_at")
                if not p_str:
                    continue
                dt = parse_article_datetime(p_str)
                if dt is not None and dt < cutoff_dt:
                    ids_to_delete.append(row_dict["id"])

            if ids_to_delete:
                placeholders = ", ".join([ph] * len(ids_to_delete))
                cursor.execute(f"DELETE FROM articles WHERE id IN ({placeholders})", tuple(ids_to_delete))
                deleted_count += len(ids_to_delete)

    except Exception as e:
        print(f"⚠️ DB delete_old_articles_from_db warning: {e}")

    return deleted_count

def format_row_dict(row: Any) -> dict:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, (datetime.datetime, datetime.date)):
            d[k] = v.strftime("%Y-%m-%d %H:%M:%S")
    return d

def get_login_logs(limit: int = 100, username: Optional[str] = None) -> List[dict]:
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    with get_db_cursor() as cursor:
        if username and username.strip():
            cursor.execute(f"SELECT * FROM login_logs WHERE username = {ph} ORDER BY id DESC LIMIT {ph}", (username.strip(), limit))
        else:
            cursor.execute(f"SELECT * FROM login_logs ORDER BY id DESC LIMIT {ph}", (limit,))
        rows = cursor.fetchall()
        return [format_row_dict(r) for r in rows]

def get_usage_logs(limit: int = 100, username: Optional[str] = None) -> List[dict]:
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    with get_db_cursor() as cursor:
        if username and username.strip():
            cursor.execute(f"SELECT * FROM usage_logs WHERE username = {ph} ORDER BY id DESC LIMIT {ph}", (username.strip(), limit))
        else:
            cursor.execute(f"SELECT * FROM usage_logs ORDER BY id DESC LIMIT {ph}", (limit,))
        rows = cursor.fetchall()
        return [format_row_dict(r) for r in rows]

# ==================== Daily AI Reports Engine ====================
def save_or_update_daily_ai_report(report_date: str, content: str, summary_meta: dict, generated_by: str, model: str) -> dict:
    """
    날짜(YYYY-MM-DD)별 AI 리포트를 저장하거나 업데이트(UPSERT)합니다.
    동일 날짜 재생성 시 중복 레코드가 생기지 않고 최신 리포트로 갱신됩니다.
    """
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    meta_json = json.dumps(summary_meta or {}, ensure_ascii=False)

    with get_db_cursor() as cursor:
        cursor.execute(f"SELECT id FROM daily_ai_reports WHERE report_date = {ph}", (report_date,))
        row = cursor.fetchone()

        if row:
            cursor.execute(
                f"""UPDATE daily_ai_reports 
                   SET content = {ph}, summary_meta = {ph}, generated_by = {ph}, model = {ph}, updated_at = {ph} 
                   WHERE report_date = {ph}""",
                (content, meta_json, generated_by, model, now_iso, report_date)
            )
            return {
                "action": "updated",
                "report_date": report_date,
                "message": f"'{report_date}' AI 리포트가 성공적으로 갱신되었습니다."
            }
        else:
            cursor.execute(
                f"""INSERT INTO daily_ai_reports 
                   (report_date, content, summary_meta, generated_by, model, created_at, updated_at) 
                   VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                (report_date, content, meta_json, generated_by, model, now_iso, now_iso)
            )
            return {
                "action": "created",
                "report_date": report_date,
                "message": f"'{report_date}' AI 리포트가 성공적으로 저장되었습니다."
            }

def get_daily_ai_report(report_date: str) -> Optional[dict]:
    """지정된 날짜의 AI 리포트를 조회합니다."""
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    with get_db_cursor() as cursor:
        cursor.execute(
            f"SELECT id, report_date, content, summary_meta, generated_by, model, created_at, updated_at FROM daily_ai_reports WHERE report_date = {ph}",
            (report_date,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        d = format_row_dict(row)
        if d.get("summary_meta"):
            try:
                d["summary_meta"] = json.loads(d["summary_meta"])
            except Exception:
                pass
        return d

def list_daily_ai_report_dates(limit: int = 30) -> List[dict]:
    """저장된 AI 리포트 날짜 목록(최신순)을 조회합니다."""
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    with get_db_cursor() as cursor:
        cursor.execute(
            f"SELECT id, report_date, generated_by, model, updated_at FROM daily_ai_reports ORDER BY report_date DESC LIMIT {ph}",
            (limit,)
        )
        rows = cursor.fetchall()
        return [format_row_dict(r) for r in rows]

def get_logs_for_date(target_date: str) -> dict:
    """
    특정 날짜(YYYY-MM-DD)에 발생한 감사 로그, 로그인 기록 및 통계를 집계합니다.
    """
    use_pg = is_postgres()
    ph = "%s" if use_pg else "?"
    date_prefix = f"{target_date}%"

    with get_db_cursor() as cursor:
        # 1. 대상 날짜 usage_logs
        cursor.execute(
            f"""SELECT id, username, ip_address, action, prompt_tokens, completion_tokens, total_tokens, model, status, details, timestamp 
               FROM usage_logs 
               WHERE timestamp LIKE {ph} 
               ORDER BY id DESC LIMIT 200""",
            (date_prefix,)
        )
        usage_rows = [format_row_dict(r) for r in cursor.fetchall()]

        # 2. 대상 날짜 login_logs
        cursor.execute(
            f"""SELECT id, username, ip_address, status, failure_reason, timestamp 
               FROM login_logs 
               WHERE timestamp LIKE {ph} 
               ORDER BY id DESC LIMIT 100""",
            (date_prefix,)
        )
        login_rows = [format_row_dict(r) for r in cursor.fetchall()]

        # 3. 토큰 합계
        total_tokens = sum(r.get("total_tokens") or 0 for r in usage_rows)
        chat_calls = sum(1 for r in usage_rows if r.get("action") == "CHAT_API")
        frontend_errors = [r for r in usage_rows if r.get("action") == "FRONTEND_ERROR"]
        cleanup_events = [r for r in usage_rows if "CLEANUP" in (r.get("action") or "")]
        blocked_events = [r for r in usage_rows if r.get("status") in ("FORBIDDEN", "BLOCKED") or "BLOCK" in (r.get("action") or "")]
        login_failed = [r for r in login_rows if r.get("status") == "FAILED"]

        return {
            "target_date": target_date,
            "total_usage_logs": len(usage_rows),
            "total_login_logs": len(login_rows),
            "chat_calls": chat_calls,
            "total_tokens": total_tokens,
            "frontend_error_count": len(frontend_errors),
            "cleanup_event_count": len(cleanup_events),
            "blocked_event_count": len(blocked_events),
            "login_failed_count": len(login_failed),
            "sample_usage_logs": usage_rows[:50],
            "sample_login_logs": login_rows[:30]
        }

def get_security_and_usage_stats() -> dict:
    with get_db_cursor() as cursor:
        # User activity summary
        cursor.execute("""
            SELECT 
                u.username,
                u.role,
                u.api_status,
                u.failed_login_attempts,
                u.block_reason,
                COALESCE(SUM(CASE WHEN l.status = 'SUCCESS' THEN 1 ELSE 0 END), 0) AS login_success_count,
                COALESCE(SUM(CASE WHEN l.status = 'FAILED' THEN 1 ELSE 0 END), 0) AS login_failed_count,
                MAX(l.timestamp) AS last_login_at
            FROM users u
            LEFT JOIN login_logs l ON u.username = l.username
            GROUP BY u.username, u.role, u.api_status, u.failed_login_attempts, u.block_reason
            ORDER BY CASE WHEN u.role = 'admin' OR u.username = 'admin' THEN 0 ELSE 1 END, u.username ASC
        """)
        user_stats = [format_row_dict(r) for r in cursor.fetchall()]

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
            u["failed_login_attempts"] = int(u.get("failed_login_attempts", 0) or 0)
            u["block_reason"] = u.get("block_reason") or ""

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

        # RAG vs Normal Chat Stats from usage_logs
        cursor.execute("""
            SELECT 
                COUNT(*) AS total_chat_calls,
                COALESCE(SUM(CASE WHEN details LIKE '%rag=True%' THEN 1 ELSE 0 END), 0) AS rag_chat_calls,
                COALESCE(SUM(CASE WHEN details NOT LIKE '%rag=True%' OR details IS NULL THEN 1 ELSE 0 END), 0) AS normal_chat_calls
            FROM usage_logs
            WHERE action = 'CHAT_API' AND status = 'SUCCESS'
        """)
        rag_row = dict(cursor.fetchone() or {})
        total_chat_calls = int(rag_row.get("total_chat_calls", 0))
        rag_chat_calls = int(rag_row.get("rag_chat_calls", 0))
        normal_chat_calls = int(rag_row.get("normal_chat_calls", 0))
        rag_ratio_percent = round((rag_chat_calls / total_chat_calls) * 100, 1) if total_chat_calls > 0 else 0.0

        # Calculate token share % per user
        overall_total_tokens = int(token_row.get("total_tokens", 0))
        for u in user_stats:
            user_tokens = u["total_tokens_used"]
            if overall_total_tokens > 0:
                u["token_share_percent"] = round((user_tokens / overall_total_tokens) * 100, 1)
            else:
                u["token_share_percent"] = 0.0

        # Overall totals
        cursor.execute("SELECT COUNT(*) AS total_users FROM users")
        total_users = cursor.fetchone()["total_users"]

        cursor.execute("SELECT COUNT(*) AS total_logins FROM login_logs WHERE status = 'SUCCESS'")
        total_logins = cursor.fetchone()["total_logins"]

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
        "rag_stats": {
            "total_chat_calls": total_chat_calls,
            "rag_chat_calls": rag_chat_calls,
            "normal_chat_calls": normal_chat_calls,
            "rag_ratio_percent": rag_ratio_percent
        },
        "overview": {
            "total_users": int(total_users),
            "total_logins": int(total_logins)
        }
    }
