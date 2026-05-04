import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv
import os


class DB:
    def __init__(self):
        load_dotenv()
        self.conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        self.cursor = self.conn.cursor()

    def _vec(self, embedding: list) -> str:
        return '[' + ','.join(map(str, embedding)) + ']'
    
    def add_message(self, user_id: str, role: str, content: str,
                    embedding: list = None, tool_call_id: str = None):
        if embedding:
            self.cursor.execute(
                """INSERT INTO llm_memory (user_id, role, content, embedding, tool_call_id)
                   VALUES (%s, %s, %s, %s::vector, %s)""",
                (user_id, role, content, self._vec(embedding), tool_call_id)
            )
        else:
            self.cursor.execute(
                """INSERT INTO llm_memory (user_id, role, content, tool_call_id)
                   VALUES (%s, %s, %s, %s)""",
                (user_id, role, content, tool_call_id)
            )
        self.conn.commit()

    def get_recent_history(self, user_id: str, limit: int = 20) -> tuple:
        """Returns (messages, ids). Messages are in chronological order and
        include all roles; tool messages carry tool_call_id."""
        self.cursor.execute(
            """SELECT id, role, content, tool_call_id FROM llm_memory
               WHERE user_id = %s ORDER BY created_at DESC LIMIT %s""",
            (user_id, limit)
        )
        rows = self.cursor.fetchall()
        ids = [row[0] for row in rows]
        messages = []
        for row in reversed(rows):
            msg = {'role': row[1], 'content': row[2]}
            if row[3]:  # tool_call_id
                msg['tool_call_id'] = row[3]
            messages.append(msg)
        return messages, ids
    
    def semantic_search(self, embedding: list, top_k: int = 5,
                        user_id: str = None, exclude_ids: list = None) -> list:
        """Returns list of {'role', 'content'} dicts ordered by relevance."""
        exclude_ids = exclude_ids or []
        vec = self._vec(embedding)

        if user_id and exclude_ids:
            self.cursor.execute(
                """SELECT role, content FROM llm_memory
                   WHERE user_id = %s
                     AND role IN ('user', 'assistant')
                     AND embedding IS NOT NULL
                     AND id <> ALL(%s::int[])
                   ORDER BY embedding <=> %s::vector
                   LIMIT %s""",
                (user_id, exclude_ids, vec, top_k)
            )
        elif user_id:
            self.cursor.execute(
                """SELECT role, content FROM llm_memory
                   WHERE user_id = %s
                     AND role IN ('user', 'assistant')
                     AND embedding IS NOT NULL
                   ORDER BY embedding <=> %s::vector
                   LIMIT %s""",
                (user_id, vec, top_k)
            )
        else:
            self.cursor.execute(
                """SELECT role, content FROM llm_memory
                   WHERE role IN ('user', 'assistant') AND embedding IS NOT NULL
                   ORDER BY embedding <=> %s::vector LIMIT %s""",
                (vec, top_k)
            )
        return [{'role': row[0], 'content': row[1]} for row in self.cursor.fetchall()]

    def get_user_profile(self, user_id: str) -> dict:
        self.cursor.execute(
            "SELECT preferences FROM user_profiles WHERE user_id = %s",
            (user_id,)
        )
        result = self.cursor.fetchone()
        return result[0] if result else {}

    def update_user_profile(self, user_id: str, preferences: dict):
        self.cursor.execute(
            """INSERT INTO user_profiles (user_id, preferences, updated_at)
               VALUES (%s, %s, now()) ON CONFLICT (user_id)
               DO UPDATE SET preferences = %s, updated_at = now()""",
            (user_id, Json(preferences), Json(preferences))
        )
        self.conn.commit()

    def store_knowledge(self, user_id: str, source_type: str, source_ref: str,
                        content: str, embedding: list, chunk_index: int = 0):
        self.cursor.execute(
            """INSERT INTO knowledge_base (user_id, source_type, source_ref, chunk_index, content, embedding)
               VALUES (%s, %s, %s, %s, %s, %s::vector)""",
            (user_id, source_type, source_ref, chunk_index, content, self._vec(embedding))
        )
        self.conn.commit()

    def search_knowledge(self, embedding: list, top_k: int = 5, user_id: str = None) -> list:
        vec = self._vec(embedding)
        if user_id:
            self.cursor.execute(
                """SELECT source_type, source_ref, content FROM knowledge_base
                   WHERE user_id = %s AND embedding IS NOT NULL
                   ORDER BY embedding <=> %s::vector LIMIT %s""",
                (user_id, vec, top_k)
            )
        else:
            self.cursor.execute(
                """SELECT source_type, source_ref, content FROM knowledge_base
                   WHERE embedding IS NOT NULL
                   ORDER BY embedding <=> %s::vector LIMIT %s""",
                (vec, top_k)
            )
        return [{'source_type': r[0], 'source_ref': r[1], 'content': r[2]}
                for r in self.cursor.fetchall()]

    def close(self):
        self.cursor.close()
        self.conn.close()
