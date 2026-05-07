from ollama import Client
from common.config import config


class Compactor:
    def __init__(self, db, user_id: str, cfg: config):
        self.db = db
        self.user_id = user_id
        self.client = Client(host=cfg.base_url)
        self.cfg = cfg

    def compact(self, extra_prompt: str = None) -> str:
        history = self.db.get_all_history(self.user_id)
        if not history:
            return "No history to compact."

        conversation = "\n".join(
            f"[{m['role'].upper()}]: {m['content']}" for m in history
        )

        prompt = self.cfg.compact_prompt
        if extra_prompt:
            prompt += f"\n\nAdditional instructions: {extra_prompt}"
        prompt += f"\n\nCONVERSATION:\n{conversation}\n\nSUMMARY:"

        resp = self.client.chat(
            model=self.cfg.compact_model,
            messages=[{'role': 'user', 'content': prompt}]
        )
        summary = resp.message.content.strip()

        self.db.set_out_of_context(self.user_id)
        self.db.add_message(
            self.user_id, 'assistant',
            f"[COMPACTED HISTORY]\n{summary}",
            in_context=True
        )

        return summary
