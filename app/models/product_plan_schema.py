"""Additive schema; applied only during normal startup or isolated tests."""


def create_plan_tables(con):
    con.executescript('''
        CREATE TABLE IF NOT EXISTS product_plans (
            plan_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, request_id TEXT NOT NULL,
            payload_hash TEXT NOT NULL, request_json TEXT NOT NULL,
            status TEXT NOT NULL, submitted INTEGER NOT NULL DEFAULT 0, content_json TEXT NOT NULL DEFAULT '{}',
            usage_json TEXT NOT NULL DEFAULT '{}', error TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(user_id, request_id));
        CREATE INDEX IF NOT EXISTS idx_plans_owner ON product_plans(user_id, created_at);
    ''')
