import json
import re
from ollama import Client
from common.config import config

BASE_PROMPT = """\
You are a profile extraction engine. Extract facts the user explicitly stated and merge them into the existing profile JSON.

RULES:
- Only include fields that have real extracted values from this conversation.
- NEVER add a field just because it exists in the schema — only add it if the user stated a value.
- NEVER use null, empty strings, or placeholder text. If you don't have a value, omit the field entirely.
- Preserve all existing fields. Overwrite only if the user explicitly corrected something.
- For lists: append new unique items, never duplicate.
- Output ONLY raw JSON. No markdown, no code fences, no commentary.

AVAILABLE FIELDS (only use the ones you have real values for):
identity: name, age, location, timezone, occupation, education
professional_profile: job_title, experience_years, background_summary, skills([name,level,years]), languages[], frameworks[], tools[]
online_presence: github_username, github_repos([name,description,url]), website, linkedin, youtube_channel, twitter
current_projects: [name, description, status, tech_stack[], goals[]]
learning_profile: learning_goals[], current_focus, preferred_learning_style[], difficulty_preference
interests: technical[], business[], personal[]
preferences: editor, os, communication_style, response_format[], likes[], dislikes[]
goals: short_term[], long_term[]

EXAMPLES:

Short — user only mentioned their name:
{"identity": {"name": "Simon"}}

Medium — user mentioned name, languages, and GitHub:
{"identity": {"name": "Simon"}, "professional_profile": {"languages": ["python", "typescript"]}, "online_presence": {"github_username": "YSMsimon"}}

Long — user shared many details:
{"identity": {"name": "Simon", "location": "Canada"}, "professional_profile": {"job_title": "backend developer", "languages": ["python", "go"], "frameworks": ["fastapi", "react"], "tools": ["docker", "postgresql"]}, "online_presence": {"github_username": "YSMsimon"}, "current_projects": [{"name": "ai-agent", "description": "local AI agent with memory", "status": "active", "tech_stack": ["python", "ollama", "postgresql"]}], "learning_profile": {"current_focus": "agent architecture"}, "goals": {"short_term": ["build fullstack apps"], "long_term": ["launch SaaS products"]}}
"""


class ProfileManager:
    def __init__(self, db, user_id: str, cfg: config):
        self.db = db
        self.user_id = user_id
        self.client = Client(host=cfg.base_url)
        self.cfg = cfg

    def update(self, user_message: str, assistant_response: str):
        existing = self.db.get_user_profile(self.user_id)
        prompt = (
            f"{BASE_PROMPT}"
            f"\nEXISTING PROFILE:\n{json.dumps(existing) if existing else '{}'}"
            f"\n\nCONVERSATION:\nUSER: {user_message}\nASSISTANT: {assistant_response}"
            f"\n\nUPDATED PROFILE:"
        )

        messages = [{'role': 'user', 'content': prompt}]
        for _ in range(3):
            resp = self.client.chat(model=self.cfg.profile_model, messages=messages)
            text = resp.message.content.strip()
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if match:
                text = match.group(1).strip()
            try:
                self.db.update_user_profile(self.user_id, json.loads(text))
                return
            except json.JSONDecodeError as e:
                messages.append({'role': 'assistant', 'content': resp.message.content})
                messages.append({'role': 'user', 'content': (
                    f"Your previous response failed JSON parsing.\n"
                    f"Error: {e}\n"
                    f"Raw response:\n{text}\n\n"
                    f"Fix the JSON and return only a valid raw JSON object."
                )})
