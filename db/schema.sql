-- =====================================================================
-- JisrVOC — PostgreSQL schema (v1)
-- Target: PostgreSQL 16 + pgvector
-- Maps to PRD §5 (data sources) and the blueprint §5 (data model).
-- Run as the first migration. Embedding dimension defaults to 1024
-- (multilingual-e5-large); change to match your embedding model.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------- enums ----------
CREATE TYPE source_type      AS ENUM ('hubspot', 'zendesk', 'canny', 'jira');
CREATE TYPE feedback_category AS ENUM ('pain_point', 'feature_request', 'bug_report', 'how_to_question', 'praise');
CREATE TYPE product_area      AS ENUM ('core_hr', 'payroll', 'jisrpay', 'onboarding', 'offboarding', 'contracts', 'mobile', 'integrations', 'other');
CREATE TYPE sentiment         AS ENUM ('positive', 'neutral', 'negative', 'mixed');
CREATE TYPE urgency           AS ENUM ('low', 'medium', 'high');
CREATE TYPE lang              AS ENUM ('ar', 'en', 'mixed');
CREATE TYPE segment           AS ENUM ('smb', 'mid_market', 'enterprise', 'government');
CREATE TYPE theme_trend       AS ENUM ('new', 'rising', 'stable', 'declining');
CREATE TYPE bet_status        AS ENUM ('draft', 'in_backlog', 'in_discovery', 'in_build', 'shipped', 'declined');
CREATE TYPE connector_status  AS ENUM ('connected', 'degraded', 'disconnected');
CREATE TYPE app_role          AS ENUM ('pm', 'director', 'cs_sales', 'admin');

-- ---------- customers (projection of HubSpot identity; never authoritative) ----------
CREATE TABLE customer (
    id              TEXT PRIMARY KEY,                 -- HubSpot company id
    name            TEXT NOT NULL,
    domain          TEXT,
    segment         segment,
    lifecycle_stage TEXT,
    industry        TEXT,
    account_size    INT,
    is_prospect     BOOLEAN NOT NULL DEFAULT FALSE,   -- pre-close (PRD open Q7)
    refreshed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_customer_domain  ON customer (domain);
CREATE INDEX idx_customer_segment ON customer (segment);

-- ---------- source connectors / config (Admin view) ----------
CREATE TABLE source_connector (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type           source_type NOT NULL,
    display_name   TEXT NOT NULL,
    status         connector_status NOT NULL DEFAULT 'disconnected',
    credentials_ref TEXT,                             -- secrets-manager reference ONLY
    field_mapping  JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_sync_at   TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- raw tickets (immutable original source records; parent of cards) ----------
CREATE TABLE raw_ticket (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id     UUID NOT NULL REFERENCES source_connector(id),
    source_type   source_type NOT NULL,
    external_id   TEXT NOT NULL,                      -- id in the source system
    subject       TEXT,
    body          TEXT,
    raw_payload   JSONB,
    language_raw  lang,
    customer_id   TEXT REFERENCES customer(id),
    occurred_at   TIMESTAMPTZ,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_type, external_id)                 -- idempotent ingestion key
);
CREATE INDEX idx_raw_ticket_customer ON raw_ticket (customer_id);

-- ---------- feedback items (decomposed, enriched unit) ----------
CREATE TABLE feedback_item (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_ticket_id UUID NOT NULL REFERENCES raw_ticket(id),
    is_split        BOOLEAN NOT NULL DEFAULT FALSE,   -- produced by multi-point decomposition
    summary_en      TEXT,                             -- AI, always English
    category        feedback_category,
    area            product_area,
    sentiment       sentiment,
    urgency         urgency,
    language        lang,
    segment         segment,                          -- denormalized from customer at enrich time
    customer_id     TEXT REFERENCES customer(id),
    occurred_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_fi_parent    ON feedback_item (parent_ticket_id);
CREATE INDEX idx_fi_customer  ON feedback_item (customer_id);
CREATE INDEX idx_fi_area      ON feedback_item (area);
CREATE INDEX idx_fi_category  ON feedback_item (category);
CREATE INDEX idx_fi_urgency   ON feedback_item (urgency);
CREATE INDEX idx_fi_occurred  ON feedback_item (occurred_at DESC);
-- full-text search over the English summary for the Feed search box
CREATE INDEX idx_fi_summary_fts ON feedback_item USING GIN (to_tsvector('english', coalesce(summary_en, '')));

-- ---------- enrichment audit (AI output + human corrections) ----------
CREATE TABLE enrichment (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    feedback_item_id UUID NOT NULL REFERENCES feedback_item(id) ON DELETE CASCADE,
    model            TEXT NOT NULL,
    model_version    TEXT NOT NULL,
    raw_output       JSONB NOT NULL,
    confidence       REAL,
    pm_corrected     BOOLEAN NOT NULL DEFAULT FALSE,
    corrected_by     TEXT,                            -- app_user.id
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_enrich_item ON enrichment (feedback_item_id);

-- ---------- embeddings (multilingual; for cross-language clustering) ----------
CREATE TABLE embedding (
    feedback_item_id UUID PRIMARY KEY REFERENCES feedback_item(id) ON DELETE CASCADE,
    vector           vector(1024) NOT NULL,
    model            TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_embedding_hnsw ON embedding USING hnsw (vector vector_cosine_ops);

-- ---------- votes (Canny/Jira upvotes; weight themes) ----------
CREATE TABLE vote (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    feedback_item_id UUID NOT NULL REFERENCES feedback_item(id) ON DELETE CASCADE,
    source           source_type NOT NULL,
    vote_count       INT NOT NULL DEFAULT 0,
    captured_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vote_item ON vote (feedback_item_id);

-- ---------- themes (persistent identity across weekly runs) ----------
CREATE TABLE theme (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name_en       TEXT NOT NULL,
    description_en TEXT,
    trend         theme_trend NOT NULL DEFAULT 'new',
    centroid      vector(1024),
    item_count    INT NOT NULL DEFAULT 0,
    customer_count INT NOT NULL DEFAULT 0,
    vote_weight   INT NOT NULL DEFAULT 0,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_run_id   UUID,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

-- ---------- theme membership (per clustering run) ----------
CREATE TABLE clustering_run (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    item_count  INT,
    status      TEXT
);
CREATE TABLE theme_membership (
    theme_id         UUID NOT NULL REFERENCES theme(id) ON DELETE CASCADE,
    feedback_item_id UUID NOT NULL REFERENCES feedback_item(id) ON DELETE CASCADE,
    run_id           UUID NOT NULL REFERENCES clustering_run(id),
    similarity       REAL,
    PRIMARY KEY (theme_id, feedback_item_id, run_id)
);

-- ---------- product bets ----------
CREATE TABLE product_bet (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    theme_id          UUID REFERENCES theme(id),
    title             TEXT NOT NULL,
    problem_statement TEXT,
    affected_segments segment[] NOT NULL DEFAULT '{}',
    est_customer_count INT,
    why_now           TEXT,
    status            bet_status NOT NULL DEFAULT 'draft',
    declined_reason   TEXT,
    owner_pm          TEXT,                            -- app_user.id
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_bet_status ON product_bet (status);
CREATE INDEX idx_bet_theme  ON product_bet (theme_id);

-- ---------- bet evidence graph (drives loop-closure targets) ----------
CREATE TABLE bet_evidence (
    bet_id           UUID NOT NULL REFERENCES product_bet(id) ON DELETE CASCADE,
    feedback_item_id UUID NOT NULL REFERENCES feedback_item(id) ON DELETE CASCADE,
    PRIMARY KEY (bet_id, feedback_item_id)
);

-- ---------- loop-closure write-back log (immutable, attributable; PRD §9) ----------
CREATE TABLE writeback_log (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bet_id           UUID NOT NULL REFERENCES product_bet(id),
    hubspot_ticket_id TEXT NOT NULL,
    action           TEXT NOT NULL,                   -- 'note' | 'property_update'
    status_value     bet_status NOT NULL,
    pm_id            TEXT NOT NULL,
    performed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    result           TEXT NOT NULL                    -- 'success' | 'failed:<reason>'
);
CREATE INDEX idx_writeback_bet ON writeback_log (bet_id);

-- ---------- PM routing rules (urgency alerts + ownership) ----------
CREATE TABLE pm_routing_rule (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    area        product_area NOT NULL UNIQUE,
    pm_user_id  TEXT NOT NULL
);

-- ---------- sync runs (Admin sync-health) ----------
CREATE TABLE sync_run (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connector_id  UUID NOT NULL REFERENCES source_connector(id),
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    items_ingested INT,
    status        TEXT,
    error         TEXT
);

-- ---------- app users / roles (mapped from SSO) ----------
CREATE TABLE app_user (
    id          TEXT PRIMARY KEY,                     -- internal id
    email       TEXT NOT NULL UNIQUE,
    name        TEXT,
    role        app_role NOT NULL DEFAULT 'pm',
    sso_subject TEXT UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
