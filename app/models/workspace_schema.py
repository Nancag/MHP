def create_workspace_tables(con):
    if 'deleted_at' not in {r[1] for r in con.execute('PRAGMA table_info(assets)')}:
        con.execute('ALTER TABLE assets ADD COLUMN deleted_at INTEGER')
    con.executescript('''
    CREATE TABLE IF NOT EXISTS password_credentials(user_id TEXT PRIMARY KEY,salt TEXT NOT NULL,password_hash TEXT NOT NULL,updated_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS password_attempts(attempt_key TEXT NOT NULL,created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS preferences(user_id TEXT PRIMARY KEY, value_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS templates(template_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,name TEXT NOT NULL,
        description TEXT NOT NULL,payload_json TEXT NOT NULL,updated_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS research(project_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,title TEXT NOT NULL,
        payload_json TEXT NOT NULL,updated_at INTEGER NOT NULL);
    ''')
