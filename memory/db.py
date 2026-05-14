import asyncpg
import json
from dotenv import load_dotenv
import os


class DB:
    def __init__(self):
        raise RuntimeError("Use await DB.create() to instantiate")

    @classmethod
    async def create(cls):
        load_dotenv()
        self = cls.__new__(cls)
        self._pool = await asyncpg.create_pool(dsn=os.getenv('DATABASE_URL'))
        return self

    def _vec(self, embedding: list) -> str:
        if not embedding:
            raise ValueError("embedding must have at least 1 dimension")
        return '[' + ','.join(map(str, embedding)) + ']'

    async def add_message(self, user_id: str, role: str, content: str,
                          embedding: list = None, tool_call_id: str = None,
                          in_context: bool = True):
        async with self._pool.acquire() as conn:
            if embedding:
                await conn.execute(
                    """INSERT INTO llm_memory (user_id, role, content, embedding, tool_call_id, in_context)
                       VALUES ($1, $2, $3, $4::vector, $5, $6)""",
                    user_id, role, content, self._vec(embedding), tool_call_id, in_context
                )
            else:
                await conn.execute(
                    """INSERT INTO llm_memory (user_id, role, content, tool_call_id, in_context)
                       VALUES ($1, $2, $3, $4, $5)""",
                    user_id, role, content, tool_call_id, in_context
                )

    async def get_recent_history(self, user_id: str, limit: int = 20) -> tuple:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, role, content, tool_call_id FROM llm_memory
                   WHERE user_id = $1 AND in_context = true
                   ORDER BY created_at DESC LIMIT $2""",
                user_id, limit
            )
        ids = [row['id'] for row in rows]
        messages = []
        for row in reversed(rows):
            msg = {'role': row['role'], 'content': row['content']}
            if row['tool_call_id']:
                msg['tool_call_id'] = row['tool_call_id']
            messages.append(msg)
        return messages, ids

    async def get_user_profile(self, user_id: str) -> dict:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT preferences FROM user_profiles WHERE user_id = $1",
                user_id
            )
        return json.loads(row['preferences']) if row else {}

    async def update_user_profile(self, user_id: str, preferences: dict):
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO user_profiles (user_id, preferences, updated_at)
                   VALUES ($1, $2, now()) ON CONFLICT (user_id)
                   DO UPDATE SET preferences = $2, updated_at = now()""",
                user_id, json.dumps(preferences)
            )

    async def delete_user_profile(self, user_id: str):
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM user_profiles WHERE user_id = $1",
                user_id
            )

    async def delete_user_history(self, user_id: str):
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM llm_memory WHERE user_id = $1",
                user_id
            )

    async def store_knowledge(self, user_id: str, source_type: str, source_ref: str,
                              content: str, embedding: list, chunk_index: int = 0):
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO knowledge_base (user_id, source_type, source_ref, chunk_index, content, embedding)
                   VALUES ($1, $2, $3, $4, $5, $6::vector)""",
                user_id, source_type, source_ref, chunk_index, content, self._vec(embedding)
            )

    async def search_knowledge(self, embedding: list, top_k: int = 5, user_id: str = None) -> list:
        vec = self._vec(embedding)
        async with self._pool.acquire() as conn:
            if user_id:
                rows = await conn.fetch(
                    """SELECT source_type, source_ref, content FROM knowledge_base
                       WHERE user_id = $1 AND embedding IS NOT NULL
                       ORDER BY embedding <=> $2::vector LIMIT $3""",
                    user_id, vec, top_k
                )
            else:
                rows = await conn.fetch(
                    """SELECT source_type, source_ref, content FROM knowledge_base
                       WHERE embedding IS NOT NULL
                       ORDER BY embedding <=> $1::vector LIMIT $2""",
                    vec, top_k
                )
        return [{'source_type': r['source_type'], 'source_ref': r['source_ref'], 'content': r['content']}
                for r in rows]

    async def get_all_history(self, user_id: str) -> list:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT role, content FROM llm_memory
                   WHERE user_id = $1 ORDER BY created_at ASC""",
                user_id
            )
        return [{'role': row['role'], 'content': row['content']} for row in rows]

    async def get_context_window(self, user_id: str) -> int | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT context_window FROM user_profiles WHERE user_id = $1",
                user_id
            )
        return row['context_window'] if row else None

    _SETTING_COLUMNS = {
        'model', 'compact_model', 'planner_model', 'evaluator_model', 'profile_model',
    }

    async def get_user_settings(self, user_id: str) -> dict:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT model, compact_model, planner_model, evaluator_model, profile_model
                   FROM user_profiles WHERE user_id = $1""",
                user_id
            )
        if not row:
            return {}
        return {k: v for k, v in dict(row).items() if v is not None}

    async def set_user_setting(self, user_id: str, key: str, value: str | None):
        if key not in self._SETTING_COLUMNS:
            raise ValueError(f"Unknown setting: {key}")
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO user_profiles (user_id, {key}, updated_at)
                    VALUES ($1, $2, now())
                    ON CONFLICT (user_id) DO UPDATE SET {key} = $2, updated_at = now()""",
                user_id, value
            )

    async def set_context_window(self, user_id: str, value: int | None):
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO user_profiles (user_id, context_window, updated_at)
                   VALUES ($1, $2, now())
                   ON CONFLICT (user_id) DO UPDATE SET context_window = $2, updated_at = now()""",
                user_id, value
            )

    async def set_out_of_context(self, user_id: str):
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE llm_memory SET in_context = false WHERE user_id = $1",
                user_id
            )

    async def close(self):
        await self._pool.close()
