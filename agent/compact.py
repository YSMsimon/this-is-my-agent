from adapters import Adapter
from common.config import config


class Compactor:
    def __init__(self, db, user_id: str, cfg: config, adapter: Adapter):
        self.db = db
        self.user_id = user_id
        self.cfg = cfg
        self.adapter = adapter

    async def compact(self, extra_prompt: str = None) -> str:
        history = await self.db.get_all_history(self.user_id)
        if not history:
            return "No history to compact."

        conversation = "\n".join(
            f"[{m['role'].upper()}]: {m['content']}" for m in history
        )

        prompt = self.cfg.compact_prompt
        if extra_prompt:
            prompt += f"\n\nAdditional instructions: {extra_prompt}"
        prompt += f"\n\nCONVERSATION:\n{conversation}\n\nSUMMARY:"

        resp = await self.adapter.complete(
            model=self.cfg.compact_model,
            messages=[{'role': 'user', 'content': prompt}]
        )
        summary = resp.content.strip()

        await self.db.set_out_of_context(self.user_id)
        await self.db.add_message(
            self.user_id, 'assistant',
            f"[COMPACTED HISTORY]\n{summary}",
            in_context=True
        )

        return summary
