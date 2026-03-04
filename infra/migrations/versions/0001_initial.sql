-- AI Lab initial schema (v1)
-- Run manually if not using SQLAlchemy create_all:
-- psql postgresql://ailab:ailab@localhost:5432/ailab -f infra/migrations/versions/0001_initial.sql

CREATE TABLE IF NOT EXISTS events (
  id SERIAL PRIMARY KEY,
  event_id VARCHAR(36) UNIQUE NOT NULL,
  stream_id VARCHAR(36) NOT NULL,
  event_type VARCHAR(80) NOT NULL,
  schema_version INTEGER NOT NULL DEFAULT 1,
  occurred_at TIMESTAMPTZ NOT NULL,
  actor_type VARCHAR(20) NOT NULL,
  actor_id VARCHAR(120) NOT NULL,
  correlation_id VARCHAR(36),
  causation_id VARCHAR(36),
  idempotency_key VARCHAR(255) NOT NULL,
  payload JSONB NOT NULL,
  UNIQUE(stream_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_events_stream ON events(stream_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at);

CREATE TABLE IF NOT EXISTS goals (
  id VARCHAR(36) PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  description TEXT NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS research_runs (
  id VARCHAR(36) PRIMARY KEY,
  goal_id VARCHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL,
  config JSONB NOT NULL,
  budget JSONB NOT NULL,
  workspace_root VARCHAR(400) NOT NULL,
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ,
  failure_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
  id VARCHAR(36) PRIMARY KEY,
  research_run_id VARCHAR(36) NOT NULL,
  goal_reference VARCHAR(36) NOT NULL,
  hypothesis TEXT NOT NULL,
  method TEXT NOT NULL,
  tools_required JSONB NOT NULL,
  parameters JSONB NOT NULL,
  evaluation_method TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_runs (
  id VARCHAR(36) PRIMARY KEY,
  experiment_id VARCHAR(36) NOT NULL,
  research_run_id VARCHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL,
  parameters JSONB NOT NULL,
  logs JSONB NOT NULL,
  result_summary TEXT,
  metrics JSONB NOT NULL,
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS results (
  id VARCHAR(36) PRIMARY KEY,
  experiment_run_id VARCHAR(36) NOT NULL,
  experiment_id VARCHAR(36) NOT NULL,
  research_run_id VARCHAR(36) NOT NULL,
  metrics JSONB NOT NULL,
  artifacts JSONB NOT NULL,
  summary TEXT NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_traces (
  id VARCHAR(36) PRIMARY KEY,
  research_run_id VARCHAR(36) NOT NULL,
  agent_id VARCHAR(120) NOT NULL,
  reasoning_summary TEXT NOT NULL,
  action TEXT NOT NULL,
  tool_used VARCHAR(80),
  tokens_used INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluator_scores (
  id VARCHAR(36) PRIMARY KEY,
  research_run_id VARCHAR(36) NOT NULL,
  experiment_run_id VARCHAR(36) NOT NULL,
  goal_progress DOUBLE PRECISION NOT NULL,
  experiment_quality DOUBLE PRECISION NOT NULL,
  novelty DOUBLE PRECISION NOT NULL,
  confidence DOUBLE PRECISION NOT NULL,
  recommendation VARCHAR(16) NOT NULL,
  rationale TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts_index (
  id VARCHAR(36) PRIMARY KEY,
  experiment_run_id VARCHAR(36) NOT NULL,
  research_run_id VARCHAR(36) NOT NULL,
  artifact_type VARCHAR(80) NOT NULL,
  path VARCHAR(500) NOT NULL,
  checksum VARCHAR(120) NOT NULL,
  size_bytes INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS model_calls (
  id VARCHAR(36) PRIMARY KEY,
  research_run_id VARCHAR(36) NOT NULL,
  experiment_run_id VARCHAR(36),
  provider VARCHAR(64) NOT NULL,
  model VARCHAR(120) NOT NULL,
  request_payload JSONB NOT NULL,
  response_payload JSONB NOT NULL,
  token_usage JSONB NOT NULL,
  latency_ms INTEGER NOT NULL,
  provider_request_id VARCHAR(120),
  success BOOLEAN NOT NULL,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS world_state_snapshots (
  id SERIAL PRIMARY KEY,
  stream_id VARCHAR(36) NOT NULL,
  last_event_id VARCHAR(36) NOT NULL,
  snapshot_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
