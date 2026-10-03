-- app: the GC's projects and decisions. The only layer that can't be rebuilt from OSHA files, so it
-- lives in Postgres (transactional writes) and has NO foreign keys into the rebuildable warehouse:
-- establishment keys are stable hashes, and entity.key_remap repairs them if cleaning rules change.
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.project (
  project_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name           text NOT NULL,
  state          char(2),
  lookback_years smallint NOT NULL DEFAULT 5 CHECK (lookback_years IN (3, 5, 10)),
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.project_sub (
  sub_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      uuid NOT NULL REFERENCES app.project ON DELETE CASCADE,
  entered_name    text NOT NULL,
  entered_city    text,
  entered_state   char(2),
  trade           text,
  licence         text,
  position        integer NOT NULL DEFAULT 0,
  matched_build   text,          -- warehouse build the rules ran against
  adjudicated_at  timestamptz,   -- uncertain records resolved (by AI or rules-only fallback)
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS project_sub_project ON app.project_sub (project_id);

-- One row per (sub, establishment) the matcher considered. A GC override (method 'gc') always wins.
CREATE TABLE IF NOT EXISTS app.sub_match (
  sub_id             uuid NOT NULL REFERENCES app.project_sub ON DELETE CASCADE,
  establishment_key  text NOT NULL,
  bucket             text NOT NULL CHECK (bucket IN ('matched', 'possible', 'excluded')),
  method             text NOT NULL CHECK (method IN ('rule', 'llm', 'gc', 'llm_rejected')),
  rule_id            text,
  confidence         real,
  rationale          text,
  evidence           jsonb,
  needs_adjudication boolean NOT NULL DEFAULT false,
  decided_by         text NOT NULL,
  decided_at         timestamptz NOT NULL DEFAULT now(),
  build_id           text,
  PRIMARY KEY (sub_id, establishment_key)
);

-- Uncertain records that carry red flags become yes/no questions; not counted until answered.
CREATE TABLE IF NOT EXISTS app.match_question (
  question_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sub_id             uuid NOT NULL REFERENCES app.project_sub ON DELETE CASCADE,
  establishment_keys text[] NOT NULL,
  text               text NOT NULL,
  ai_suggestion      text,
  ai_rationale       text,
  answer             text CHECK (answer IN ('yes', 'no')),
  answered_at        timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now()
);

-- AI decisions cached by a hash of (model + evidence packet): reused across projects and rebuilds
CREATE TABLE IF NOT EXISTS app.adjudication_cache (
  packet_hash text PRIMARY KEY,
  model       text NOT NULL,
  response    jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.question_log (
  id             bigserial PRIMARY KEY,
  project_id     uuid,
  asked_at       timestamptz NOT NULL DEFAULT now(),
  question       text NOT NULL,
  status         text NOT NULL,
  answer         text,
  tools          jsonb,
  ungrounded     jsonb,
  model          text,
  input_tokens   integer,
  output_tokens  integer,
  latency_ms     integer
);

CREATE TABLE IF NOT EXISTS app.llm_usage_daily (
  day           date PRIMARY KEY,
  input_tokens  bigint NOT NULL DEFAULT 0,
  output_tokens bigint NOT NULL DEFAULT 0
);
