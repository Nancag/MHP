import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "mhp.db"


def get_connection():
    """打开数据库连接。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """创建现有功能所需表；旧抠图历史表不删除，也不再新建。"""
    connection = get_connection()

    try:
        connection.execute('''CREATE TABLE IF NOT EXISTS requests (
            kind TEXT NOT NULL, user_id TEXT NOT NULL, request_key TEXT NOT NULL,
            payload_hash TEXT NOT NULL, created_at INTEGER NOT NULL, response TEXT,
            PRIMARY KEY(kind, user_id, request_key))''')
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL UNIQUE,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                format TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS generations (
                generation_id  TEXT PRIMARY KEY,
                asset_id       TEXT,
                cutout_id      TEXT,
                prompt         TEXT NOT NULL,
                full_prompt    TEXT,
                model          TEXT NOT NULL,
                size           TEXT NOT NULL,
                quality        TEXT,
                filename       TEXT,
                width          INTEGER,
                height         INTEGER,
                size_bytes     INTEGER,
                status         TEXT NOT NULL,
                error          TEXT,
                cost_usd       REAL,
                created_at     TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_generations_asset
            ON generations (asset_id)
            """
        )
        try:
            connection.execute(
                "ALTER TABLE generations ADD COLUMN task_id TEXT"
            )
        except sqlite3.OperationalError:
            pass
        for col_def in [
            "ALTER TABLE generations ADD COLUMN user TEXT DEFAULT 'anonymous'",
            "ALTER TABLE generations ADD COLUMN ratio TEXT",
            "ALTER TABLE generations ADD COLUMN resolution TEXT",
            "ALTER TABLE generations ADD COLUMN language TEXT",
            "ALTER TABLE generations ADD COLUMN platform TEXT",
            "ALTER TABLE generations ADD COLUMN scene TEXT",
            "ALTER TABLE generations ADD COLUMN style TEXT",
            "ALTER TABLE generations ADD COLUMN type TEXT DEFAULT 'ai_generation'",
            "ALTER TABLE generations ADD COLUMN design_json TEXT",
            "ALTER TABLE generations ADD COLUMN workflow_json TEXT",
            "ALTER TABLE generations ADD COLUMN batch_id TEXT",
            "ALTER TABLE generations ADD COLUMN page_index INTEGER",
            "ALTER TABLE generations ADD COLUMN review_status TEXT",
        ]:
            try:
                connection.execute(col_def)
            except sqlite3.OperationalError:
                pass
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS product_sets (
                batch_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, request_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL, spec_json TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(user_id, request_id));
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL CHECK(length(username) BETWEEN 1 AND 20),
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auth_codes (
                challenge_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                consumed INTEGER NOT NULL DEFAULT 0,
                client_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_auth_codes_email ON auth_codes(email, created_at);
            CREATE INDEX IF NOT EXISTS idx_auth_codes_client ON auth_codes(client_hash, created_at);
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(user_id),
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                remember INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at);
        """)
        for table in ("assets",):
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if "user_id" not in columns:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")
            connection.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_user ON {table}(user_id)")
        if 'role' not in {row[1] for row in connection.execute('PRAGMA table_info(assets)')}:
            connection.execute("ALTER TABLE assets ADD COLUMN role TEXT NOT NULL DEFAULT 'product'")
        from app.models.billing_schema import create_tables
        create_tables(connection)
        from app.models.workspace_schema import create_workspace_tables
        create_workspace_tables(connection)
        from app.models.library_schema import create_library_tables
        create_library_tables(connection)
        from app.models.product_plan_schema import create_plan_tables
        create_plan_tables(connection)
        connection.commit()
    finally:
        connection.close()
