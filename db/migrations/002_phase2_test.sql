-- Phase 2 test migration (without pgvector dependency)
-- For testing clustering logic locally

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ENUMs (if not already exist)
DO $$ BEGIN
    CREATE TYPE theme_trend AS ENUM ('new', 'rising', 'stable', 'declining');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE bet_status AS ENUM ('draft', 'in_backlog', 'in_discovery', 'in_build', 'shipped', 'declined');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE segment AS ENUM ('enterprise', 'smb', 'individual', 'all');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- clustering_run table
CREATE TABLE IF NOT EXISTS clustering_run (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ,
    item_count     INT,
    status         TEXT
);

-- theme table (using JSONB for centroid instead of vector type)
CREATE TABLE IF NOT EXISTS theme (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name_en        TEXT NOT NULL,
    description_en TEXT,
    trend          theme_trend NOT NULL DEFAULT 'new',
    centroid       JSONB,  -- Store as JSONB array for testing
    item_count     INT NOT NULL DEFAULT 0,
    customer_count INT NOT NULL DEFAULT 0,
    vote_weight    INT NOT NULL DEFAULT 0,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_run_id    UUID REFERENCES clustering_run(id),
    is_active      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_theme_vote_weight ON theme (vote_weight DESC);
CREATE INDEX IF NOT EXISTS idx_theme_active ON theme (is_active);

-- theme_membership table
CREATE TABLE IF NOT EXISTS theme_membership (
    theme_id    UUID NOT NULL REFERENCES theme(id) ON DELETE CASCADE,
    feedback_id UUID NOT NULL,  -- Will reference feedback table when it exists
    run_id      UUID NOT NULL REFERENCES clustering_run(id),
    similarity  FLOAT,
    PRIMARY KEY (theme_id, feedback_id, run_id)
);

-- product_bet table
CREATE TABLE IF NOT EXISTS product_bet (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    theme_id           UUID REFERENCES theme(id),
    title              TEXT NOT NULL,
    problem_statement  TEXT,
    affected_segments  TEXT[] NOT NULL DEFAULT '{}',  -- Using TEXT[] instead of segment[]
    est_customer_count INT,
    why_now            TEXT,
    status             bet_status NOT NULL DEFAULT 'draft',
    owner_pm           TEXT,
    declined_reason    TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_bet_status ON product_bet (status);

-- bet_evidence table
CREATE TABLE IF NOT EXISTS bet_evidence (
    bet_id      UUID NOT NULL REFERENCES product_bet(id) ON DELETE CASCADE,
    feedback_id UUID NOT NULL,  -- Will reference feedback table when it exists
    PRIMARY KEY (bet_id, feedback_id)
);

-- writeback_log table
CREATE TABLE IF NOT EXISTS writeback_log (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bet_id            UUID NOT NULL REFERENCES product_bet(id),
    hubspot_ticket_id TEXT NOT NULL,
    action            TEXT NOT NULL,
    pm_id             TEXT NOT NULL,
    result            TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
