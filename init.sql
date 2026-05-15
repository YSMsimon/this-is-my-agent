CREATE TABLE IF NOT EXISTS llm_memory (
    id            SERIAL PRIMARY KEY,
    user_id       TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content       TEXT NOT NULL,
    tool_call_id  TEXT,
    in_context    BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_memory_user_time
    ON llm_memory (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id     TEXT PRIMARY KEY,
    preferences JSONB DEFAULT '{}',
    updated_at  TIMESTAMP DEFAULT now()
);

-- Idempotent migrations: drop removed columns from older installs
ALTER TABLE user_profiles DROP COLUMN IF EXISTS context_window;
ALTER TABLE user_profiles DROP COLUMN IF EXISTS model;
ALTER TABLE user_profiles DROP COLUMN IF EXISTS compact_model;
ALTER TABLE user_profiles DROP COLUMN IF EXISTS planner_model;
ALTER TABLE user_profiles DROP COLUMN IF EXISTS evaluator_model;
ALTER TABLE user_profiles DROP COLUMN IF EXISTS profile_model;
ALTER TABLE user_profiles DROP COLUMN IF EXISTS deepseek_api_key;
ALTER TABLE user_profiles DROP COLUMN IF EXISTS ollama_api_key;
