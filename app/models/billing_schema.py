"""Small, auditable SQLite tables for credits, membership orders and reminders."""
def create_tables(con):
    con.executescript('''
      CREATE TABLE IF NOT EXISTS credit_grants (
        grant_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, source TEXT NOT NULL,
        reference TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>=0),
        remaining INTEGER NOT NULL CHECK(remaining>=0 AND remaining<=amount),
        expires_at INTEGER, created_at INTEGER NOT NULL,
        UNIQUE(user_id,source,reference));
      CREATE INDEX IF NOT EXISTS idx_credit_grants_user ON credit_grants(user_id,expires_at);
      CREATE TABLE IF NOT EXISTS credit_holds (
        generation_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, grant_id TEXT NOT NULL,
        state TEXT NOT NULL, submitted INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS memberships (
        user_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, expires_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS membership_orders (
        order_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, request_key TEXT NOT NULL,
        plan_id TEXT NOT NULL, price_fen INTEGER NOT NULL, credits INTEGER NOT NULL,
        days INTEGER NOT NULL, months INTEGER NOT NULL, status TEXT NOT NULL,
        app_id TEXT NOT NULL, seller_id TEXT NOT NULL, created_at INTEGER NOT NULL,
        payment_deadline INTEGER NOT NULL, paid_at INTEGER, trade_no TEXT UNIQUE,
        membership_expires_at INTEGER, UNIQUE(user_id,request_key));
      CREATE INDEX IF NOT EXISTS idx_membership_orders_user ON membership_orders(user_id,created_at);
      CREATE TABLE IF NOT EXISTS membership_reminders (
        reminder_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at INTEGER NOT NULL,
        due_at INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0, last_attempt INTEGER, sent_at INTEGER,
        UNIQUE(user_id,expires_at));
      CREATE TABLE IF NOT EXISTS membership_email_attempts (
        attempt_id TEXT PRIMARY KEY, created_at INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS redemption_claims (
        code_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, credits INTEGER NOT NULL,
        months INTEGER NOT NULL DEFAULT 0, days INTEGER NOT NULL DEFAULT 0, claimed_at INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS idx_redemption_claims_user ON redemption_claims(user_id,claimed_at);
    ''')
