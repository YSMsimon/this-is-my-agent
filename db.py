import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv
import os


class DB:
    def __init__(self):
        load_dotenv()
        self.conn = psycopg2.connect(os.getenv('DATABASE_URL'))

    def _vec(self, embedding: list) -> str:
        return '[' + ','.join(map(str, embedding)) + ']'

    def _cursor(self):
        return self.conn.cursor()

    def add_message(self, user_id: str, role: str, content: str,
                    embedding: list = None, tool_call_id: str = None):
        with self._cursor() as cur:
            if embedding:
                cur.execute(
                    """INSERT INTO llm_memory (user_id, role, content, embedding, tool_call_id)
                       VALUES (%s, %s, %s, %s::vector, %s)""",
                    (user_id, role, content, self._vec(embedding), tool_call_id)
                )
            else:
                cur.execute(
                    """INSERT INTO llm_memory (user_id, role, content, tool_call_id)
                       VALUES (%s, %s, %s, %s)""",
                    (user_id, role, content, tool_call_id)
                )
        self.conn.commit()

    def get_recent_history(self, user_id: str, limit: int = 20) -> tuple:
        with self._cursor() as cur:
            cur.execute(
                """SELECT id, role, content, tool_call_id FROM llm_memory
                   WHERE user_id = %s ORDER BY created_at DESC LIMIT %s""",
                (user_id, limit)
            )
            rows = cur.fetchall()
        ids = [row[0] for row in rows]
        messages = []
        for row in reversed(rows):
            msg = {'role': row[1], 'content': row[2]}
            if row[3]:
                msg['tool_call_id'] = row[3]
            messages.append(msg)
        return messages, ids

    def get_user_profile(self, user_id: str) -> dict:
        with self._cursor() as cur:
            cur.execute(
                "SELECT preferences FROM user_profiles WHERE user_id = %s",
                (user_id,)
            )
            result = cur.fetchone()
        return result[0] if result else {}

    def update_user_profile(self, user_id: str, preferences: dict):
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO user_profiles (user_id, preferences, updated_at)
                   VALUES (%s, %s, now()) ON CONFLICT (user_id)
                   DO UPDATE SET preferences = %s, updated_at = now()""",
                (user_id, Json(preferences), Json(preferences))
            )
        self.conn.commit()

    def delete_user_profile(self, user_id: str):
        with self._cursor() as cur:
            cur.execute(
                "DELETE FROM user_profiles WHERE user_id = %s",
                (user_id,)
            )
        self.conn.commit()

    def delete_user_history(self, user_id: str):
        with self._cursor() as cur:
            cur.execute(
                "DELETE FROM llm_memory WHERE user_id = %s",
                (user_id,)
            )
        self.conn.commit()

    def store_knowledge(self, user_id: str, source_type: str, source_ref: str,
                        content: str, embedding: list, chunk_index: int = 0):
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO knowledge_base (user_id, source_type, source_ref, chunk_index, content, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s::vector)""",
                (user_id, source_type, source_ref, chunk_index, content, self._vec(embedding))
            )
        self.conn.commit()

    def search_knowledge(self, embedding: list, top_k: int = 5, user_id: str = None) -> list:
        vec = self._vec(embedding)
        with self._cursor() as cur:
            if user_id:
                cur.execute(
                    """SELECT source_type, source_ref, content FROM knowledge_base
                       WHERE user_id = %s AND embedding IS NOT NULL
                       ORDER BY embedding <=> %s::vector LIMIT %s""",
                    (user_id, vec, top_k)
                )
            else:
                cur.execute(
                    """SELECT source_type, source_ref, content FROM knowledge_base
                       WHERE embedding IS NOT NULL
                       ORDER BY embedding <=> %s::vector LIMIT %s""",
                    (vec, top_k)
                )
            return [{'source_type': r[0], 'source_ref': r[1], 'content': r[2]}
                    for r in cur.fetchall()]

    def close(self):
        self.conn.close()
