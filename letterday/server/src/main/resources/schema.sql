CREATE TABLE IF NOT EXISTS app_user (id VARCHAR(36) PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE, password_hash VARCHAR(100) NOT NULL, created_at VARCHAR(40) NOT NULL);
CREATE TABLE IF NOT EXISTS login_session (token_hash VARCHAR(64) PRIMARY KEY, user_id VARCHAR(36) NOT NULL REFERENCES app_user(id) ON DELETE CASCADE, expires_at VARCHAR(40) NOT NULL);
CREATE TABLE IF NOT EXISTS journal_entry (id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL REFERENCES app_user(id) ON DELETE CASCADE, entry_date VARCHAR(10) NOT NULL, title VARCHAR(90) NOT NULL, body TEXT NOT NULL, mood VARCHAR(20) NOT NULL, visibility VARCHAR(10) NOT NULL, photo TEXT, drawing TEXT, created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL);
CREATE INDEX IF NOT EXISTS idx_journal_owner ON journal_entry (user_id,entry_date);
CREATE INDEX IF NOT EXISTS idx_journal_visibility ON journal_entry (visibility,created_at);
