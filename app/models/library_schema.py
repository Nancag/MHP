"""Additive migration only; executed by the normal application initialization."""


def create_library_tables(con):
    columns = {r[1] for r in con.execute('PRAGMA table_info(assets)')}
    for name in ('folder_id', 'source_url'):
        if name not in columns:
            con.execute(f'ALTER TABLE assets ADD COLUMN {name} TEXT')
    con.executescript('''
    CREATE TABLE IF NOT EXISTS reference_folders (
        folder_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
        source_url TEXT, created_at TEXT NOT NULL,
        UNIQUE(user_id, source_url));
    CREATE INDEX IF NOT EXISTS idx_assets_folder ON assets(user_id, folder_id, deleted_at);
    CREATE TABLE IF NOT EXISTS product_imports (
        import_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, source_url TEXT NOT NULL,
        folder_id TEXT, status TEXT NOT NULL, result_json TEXT NOT NULL DEFAULT '{}',
        error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_imports_owner ON product_imports(user_id, created_at);
    CREATE TABLE IF NOT EXISTS product_drafts (
        draft_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, import_id TEXT NOT NULL,
        request_id TEXT NOT NULL, payload_hash TEXT NOT NULL, model TEXT NOT NULL,
        language TEXT NOT NULL, requirements TEXT NOT NULL, status TEXT NOT NULL,
        content_json TEXT NOT NULL DEFAULT '{}', usage_json TEXT NOT NULL DEFAULT '{}',
        error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(user_id,request_id));
    CREATE INDEX IF NOT EXISTS idx_drafts_owner ON product_drafts(user_id,import_id,created_at);
    ''')
