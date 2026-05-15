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

    async def add_message(self, user_id: str, role: str, content: str,
                          tool_call_id: str = None, in_context: bool = True):
        async with self._pool.acquire() as conn:
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

    async def get_all_history(self, user_id: str) -> list:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT role, content FROM llm_memory
                   WHERE user_id = $1 ORDER BY created_at ASC""",
                user_id
            )
        return [{'role': row['role'], 'content': row['content']} for row in rows]

    async def set_out_of_context(self, user_id: str):
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE llm_memory SET in_context = false WHERE user_id = $1",
                user_id
            )

    async def close(self):
        await self._pool.close()
