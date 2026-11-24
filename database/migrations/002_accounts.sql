-- GenBench M2: user accounts, revocable sessions, and job ownership.
-- Apply after 001_image_jobs.sql to a dedicated GenBench database.
-- If generation_jobs already has rows, assign them to an owner before this migration.

BEGIN;

CREATE TABLE IF NOT EXISTS genbench.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL CHECK (char_length(email) BETWEEN 3 AND 254 AND email = lower(btrim(email))),
    password_hash text NOT NULL CHECK (char_length(password_hash) > 0),
    display_name text NOT NULL CHECK (char_length(btrim(display_name)) BETWEEN 1 AND 100),
    created_at timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz,
    disabled_at timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_idx
    ON genbench.users (lower(email));

CREATE TABLE IF NOT EXISTS genbench.sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES genbench.users(id) ON DELETE CASCADE,
    token_hash char(64) NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    last_seen_at timestamptz,
    revoked_at timestamptz,
    CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS sessions_user_active_idx
    ON genbench.sessions (user_id, expires_at)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS genbench.login_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid REFERENCES genbench.users(id) ON DELETE SET NULL,
    outcome text NOT NULL CHECK (outcome IN ('succeeded', 'failed', 'logged_out')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS login_events_user_time_idx
    ON genbench.login_events (user_id, created_at DESC);

ALTER TABLE genbench.generation_jobs
    ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES genbench.users(id);

-- This project has not applied 001 yet, so the job table should be empty.
-- Fail explicitly rather than silently assigning existing jobs to the wrong user.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM genbench.generation_jobs WHERE user_id IS NULL) THEN
        RAISE EXCEPTION 'Backfill generation_jobs.user_id before applying 002_accounts.sql';
    END IF;
END $$;

ALTER TABLE genbench.generation_jobs
    ALTER COLUMN user_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS generation_jobs_user_history_idx
    ON genbench.generation_jobs (user_id, created_at DESC, id DESC);

COMMIT;
