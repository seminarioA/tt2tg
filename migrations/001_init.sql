CREATE TABLE IF NOT EXISTS accounts (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(100) UNIQUE NOT NULL,
    chat_id     BIGINT NOT NULL,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    last_checked TIMESTAMPTZ,
    is_active   BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS videos (
    id             SERIAL PRIMARY KEY,
    video_id       VARCHAR(100) UNIQUE NOT NULL,
    account_id     INT REFERENCES accounts(id) ON DELETE CASCADE,
    url            TEXT NOT NULL,
    metadata_path  TEXT,
    upload_date    DATE,
    description    TEXT,
    like_count     INT,
    repost_count   INT,
    discovered_at  TIMESTAMPTZ DEFAULT NOW(),
    sent_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_videos_account_id ON videos(account_id);
CREATE INDEX IF NOT EXISTS idx_videos_sent_at    ON videos(sent_at);
CREATE INDEX IF NOT EXISTS idx_accounts_active   ON accounts(is_active);
