-- =====================================================================
-- JisrVOC — Phase 2 Intelligence Layer Migration
-- Creates tables for clustering, themes, and product bets
-- Requires: PostgreSQL 16 + pgvector extension
-- =====================================================================

-- ---------- clustering_run ----------
-- Tracks each clustering execution for audit and reproducibility
CREATE TABLE IF NOT EXISTS clustering_run (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ,
    item_count     INT,
    status         TEXT,  -- 'running', 'completed', 'failed', 'skipped'
    CONSTRAINT ck_clustering_run_status CHECK (status IN ('running', 'completed', 'failed', 'skipped'))
);

CREATE INDEX idx_clustering_run_started ON clustering_run (started_at DESC);
CREATE INDEX idx_clustering_run_status ON clustering_run (status);

-- ---------- theme ----------
-- Discovered patterns from feedback clustering with stable identity
CREATE TABLE IF NOT EXISTS theme (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name_en        TEXT NOT NULL,
    description_en TEXT,
    trend          theme_trend NOT NULL DEFAULT 'new',
    centroid       vector(1536),  -- Embedding centroid for similarity matching
    item_count     INT NOT NULL DEFAULT 0,
    customer_count INT NOT NULL DEFAULT 0,
    vote_weight    INT NOT NULL DEFAULT 0,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_run_id    UUID REFERENCES clustering_run(id),
    is_active      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_theme_active ON theme (is_active);
CREATE INDEX idx_theme_vote_weight ON theme (vote_weight DESC);
CREATE INDEX idx_theme_trend ON theme (trend);
CREATE INDEX idx_theme_last_run ON theme (last_run_id);

-- Vector similarity index for theme matching
CREATE INDEX idx_theme_centroid ON theme USING ivfflat (centroid vector_cosine_ops)
    WITH (lists = 100);

-- ---------- theme_membership ----------
-- Links feedback items to themes for each clustering run
CREATE TABLE IF NOT EXISTS theme_membership (
    theme_id    UUID NOT NULL REFERENCES theme(id) ON DELETE CASCADE,
    feedback_id UUID NOT NULL REFERENCES feedback(id) ON DELETE CASCADE,
    run_id      UUID NOT NULL REFERENCES clustering_run(id),
    similarity  FLOAT,  -- Cosine similarity score to theme centroid
    PRIMARY KEY (theme_id, feedback_id, run_id)
);

CREATE INDEX idx_theme_membership_run ON theme_membership (run_id);
CREATE INDEX idx_theme_membership_feedback ON theme_membership (feedback_id);
CREATE INDEX idx_theme_membership_similarity ON theme_membership (similarity DESC);

-- ---------- product_bet ----------
-- AI-generated product opportunities derived from high-impact themes
CREATE TABLE IF NOT EXISTS product_bet (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    theme_id           UUID REFERENCES theme(id),
    title              TEXT NOT NULL,
    problem_statement  TEXT,
    affected_segments  segment[] NOT NULL DEFAULT '{}',  -- Array of impacted segments
    est_customer_count INT,
    why_now            TEXT,
    status             bet_status NOT NULL DEFAULT 'draft',
    owner_pm           TEXT,
    declined_reason    TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_product_bet_status ON product_bet (status);
CREATE INDEX idx_product_bet_theme ON product_bet (theme_id);
CREATE INDEX idx_product_bet_created ON product_bet (created_at DESC);

-- ---------- bet_evidence ----------
-- Links feedback items to bets as supporting evidence
CREATE TABLE IF NOT EXISTS bet_evidence (
    bet_id      UUID NOT NULL REFERENCES product_bet(id) ON DELETE CASCADE,
    feedback_id UUID NOT NULL REFERENCES feedback(id) ON DELETE CASCADE,
    PRIMARY KEY (bet_id, feedback_id)
);

CREATE INDEX idx_bet_evidence_feedback ON bet_evidence (feedback_id);

-- ---------- writeback_log ----------
-- Immutable audit trail of HubSpot updates made by PMs
CREATE TABLE IF NOT EXISTS writeback_log (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bet_id            UUID NOT NULL REFERENCES product_bet(id),
    hubspot_ticket_id TEXT NOT NULL,
    action            TEXT NOT NULL,  -- 'note' | 'property_update'
    pm_id             TEXT NOT NULL,
    result            TEXT NOT NULL,  -- 'success' | 'failed:<reason>'
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_writeback_action CHECK (action IN ('note', 'property_update'))
);

CREATE INDEX idx_writeback_log_bet ON writeback_log (bet_id);
CREATE INDEX idx_writeback_log_created ON writeback_log (created_at DESC);

-- ---------- Add slack_alerted column to feedback table ----------
-- Tracks whether feedback has been sent to Slack for urgent alerting
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'feedback' AND column_name = 'slack_alerted'
    ) THEN
        ALTER TABLE feedback ADD COLUMN slack_alerted BOOLEAN NOT NULL DEFAULT FALSE;
        CREATE INDEX idx_feedback_slack_alerted ON feedback (slack_alerted);
    END IF;
END$$;

-- =====================================================================
-- Migration complete
-- =====================================================================
