CREATE EXTENSION IF NOT EXISTS vector;

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

CREATE TABLE IF NOT EXISTS knowledge_base (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref  TEXT,
    chunk_index INT DEFAULT 0,
    content     TEXT NOT NULL,
    embedding   vector(768),
    created_at  TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
    ON knowledge_base USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;
