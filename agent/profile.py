import json
import re
from ollama import AsyncClient
from common.config import config


class ProfileManager:
    def __init__(self, db, user_id: str, cfg: config):
        self.db = db
        self.user_id = user_id
        self.client = AsyncClient(host=cfg.base_url)
        self.cfg = cfg

    async def update(self, user_message: str, assistant_response: str):
        existing = await self.db.get_user_profile(self.user_id)
        prompt = (
            f"{self.cfg.profile_prompt}"
            f"\nEXISTING PROFILE:\n{json.dumps(existing) if existing else '{}'}"
            f"\n\nCONVERSATION:\nUSER: {user_message}\nASSISTANT: {assistant_response}"
            f"\n\nUPDATED PROFILE:"
        )

        messages = [{'role': 'user', 'content': prompt}]
        for _ in range(3):
            resp = await self.client.chat(model=self.cfg.profile_model, messages=messages)
            text = resp.message.content.strip()
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if match:
                text = match.group(1).strip()
            try:
                await self.db.update_user_profile(self.user_id, json.loads(text))
                return
            except json.JSONDecodeError as e:
                messages.append({'role': 'assistant', 'content': resp.message.content})
                messages.append({'role': 'user', 'content': (
                    f"Your previous response failed JSON parsing.\n"
                    f"Error: {e}\n"
                    f"Raw response:\n{text}\n\n"
                    f"Fix the JSON and return only a valid raw JSON object."
                )})
