from ollama import Client
from typing import List, Dict, Optional
from common.config import config
from run_bash import tools, tool_handler, all_tools
from to_do import ToDoManager
from db import DB
from command_manager import CommandManager
import json
import re
import sys
import threading


class Agent:
    def __init__(self, cfg: config, tools: Optional[List] = tools, db: DB = None, user_id: str = 'default_user'):
        self.config = cfg
        self.tools = tools
        self.todo_manager = ToDoManager()
        self.db = db
        self.user_id = user_id
        self.client = Client(host=cfg.base_url)
        self._system_prompt = ''
        self._last_user_message = ''

    KNOWLEDGE_TOOLS = {'fetch_text', 'read_file'}

    def _chunk(self, text: str, size: int = 1500, overlap: int = 200) -> list:
        chunks, start = [], 0
        while start < len(text):
            chunks.append(text[start:start + size])
            start += size - overlap
        return chunks

    def _store_knowledge(self, args: dict, result: str):
        source_ref = args.get('url') or args.get('file_path') or ''
        source_type = 'webpage' if 'url' in args else 'file'
        for i, chunk in enumerate(self._chunk(result)):
            embedding = self.get_embedding(chunk)
            self.db.store_knowledge(self.user_id, source_type, source_ref, chunk, embedding, i)

    def get_embedding(self, text: str) -> list:
        response = self.client.embeddings(model=self.config.embedding_model, prompt=text)
        embedding = response.embedding
        return embedding

    def _build_system_prompt(self) -> str:
        profile = self.db.get_user_profile(self.user_id)
        profile_text = json.dumps(profile, indent=2) if profile else "No profile yet."
        return self.config.system_prompt.format(user_profile=profile_text)

    def _build_messages(self, user_message: str) -> List[Dict]:
        
        history, recent_ids = self.db.get_recent_history(self.user_id, limit=10000)

        embedding = self.get_embedding(user_message)
        
        memories = self.db.semantic_search(
            embedding, top_k=5, user_id=self.user_id, exclude_ids=recent_ids
        )

        knowledge = self.db.search_knowledge(embedding, top_k=5, user_id=self.user_id)

        messages = list(history)

        if knowledge:
            rag_lines = "\n\n".join(
                f"[{k['source_type']} — {k['source_ref']}]\n{k['content']}" for k in knowledge
            )
            messages.insert(0, {'role': 'system', 'content': f"Relevant knowledge:\n{rag_lines}"})

        self._save_turn({'role': 'user', 'content': user_message})
        messages.append({'role': 'user', 'content': user_message})
        return messages

    def _update_profile(self, user_message: str, assistant_response: str):
        existing = self.db.get_user_profile(self.user_id)

        base_prompt = f"""You are a profile extraction engine. Extract facts the user explicitly stated and merge them into the existing profile JSON.

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
{{"identity": {{"name": "Simon"}}}}

Medium — user mentioned name, languages, and GitHub:
{{"identity": {{"name": "Simon"}}, "professional_profile": {{"languages": ["python", "typescript"]}}, "online_presence": {{"github_username": "YSMsimon"}}}}

Long — user shared many details:
{{"identity": {{"name": "Simon", "location": "Canada"}}, "professional_profile": {{"job_title": "backend developer", "languages": ["python", "go"], "frameworks": ["fastapi", "react"], "tools": ["docker", "postgresql"]}}, "online_presence": {{"github_username": "YSMsimon"}}, "current_projects": [{{"name": "ai-agent", "description": "local AI agent with memory", "status": "active", "tech_stack": ["python", "ollama", "postgresql"]}}], "learning_profile": {{"current_focus": "agent architecture"}}, "goals": {{"short_term": ["build fullstack apps"], "long_term": ["launch SaaS products"]}}}}

EXISTING PROFILE:
{json.dumps(existing) if existing else "{{}}"}

CONVERSATION:
USER: {user_message}
ASSISTANT: {assistant_response}

UPDATED PROFILE JSON:"""

        messages = [{'role': 'user', 'content': base_prompt}]
        max_retries = 3
        for _ in range(max_retries):
            resp = self.client.chat(model=self.config.profile_model, messages=messages)
            text = resp.message.content.strip()
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if match:
                text = match.group(1).strip()
            try:
                self.db.update_user_profile(self.user_id, json.loads(text))
                return
            except json.JSONDecodeError as e:
                error_feedback = (
                    f"Your previous response failed JSON parsing.\n"
                    f"Error: {e}\n"
                    f"Occurred at character position: {e.pos if hasattr(e, 'pos') else 'unknown'}\n"
                    f"Raw response that failed:\n{text}\n\n"
                    f"Fix the JSON and return only a valid raw JSON object. No nulls, no placeholders, only fields with real values."
                )
                messages.append({'role': 'assistant', 'content': resp.message.content})
                messages.append({'role': 'user', 'content': error_feedback})

    def _save_turn(self, new_messages: Dict):
        role = new_messages.get('role')
        content = new_messages.get('content')
        tool_call_id = new_messages.get('tool_call_id')
        self.db.add_message(self.user_id, role, content, None, tool_call_id)

        if role == 'user':
            self._last_user_message = content
        elif role == 'assistant' and self._last_user_message:
            threading.Thread(
                target=self._update_profile,
                args=(self._last_user_message, content),
                daemon=True
            ).start()

    def run(self, user_message: str) -> str:
        self._system_prompt = self._build_system_prompt()
        messages = self._build_messages(user_message)
        final_messages = self._execute(messages)
        for msg in reversed(final_messages):
            if isinstance(msg, dict) and msg.get('role') == 'assistant':
                return msg.get('content', '')
        return ''

    def _execute(self, messages: List[Dict]) -> List[Dict]:
        response = self.client.chat(
            model=self.config.model,
            messages=[{'role': 'system', 'content': self._system_prompt}] + messages,
            tools=self.tools,
            stream=True
        )

        full_content = ''
        tool_calls = None
        for chunk in response:
            if chunk.message.content:
                full_content += chunk.message.content
                print(chunk.message.content, end='', flush=True, file=sys.stderr)
            if chunk.message.tool_calls:
                tool_calls = chunk.message.tool_calls
        print(file=sys.stderr)

        self._save_turn({'role': 'assistant', 'content': full_content})
        messages = messages + [{'role': 'assistant', 'content': full_content}]

        if not tool_calls:
            return messages

        for tool_call in tool_calls:
            tool_call_id = getattr(tool_call, 'id', None)
            name = tool_call.function.name
            args = tool_call.function.arguments
            result = tool_handler[name](**args)
            if name in self.KNOWLEDGE_TOOLS and isinstance(result, str) and result.strip():
                self._store_knowledge(args, result)
            self._save_turn({'role': 'tool', 'content': f"Name: {name}, Arguments: {args}, Result: {result}", 'tool_call_id': tool_call_id})
            messages.append({'role': 'tool', 'content': f"Name: {name}, Arguments: {args}, Result: {result}", 'tool_call_id': tool_call_id})
        return self._execute(messages)


if __name__ == '__main__':
    db = DB()
    cfg = config()
    agent = Agent(cfg, tools=all_tools, db=db)
    commands = CommandManager(db, agent.user_id)
    try:
        while True:
            user_input = input("User> ")
            if commands.is_command(user_input):
                commands.handle(user_input)
                continue
            agent.run(user_input)
    except KeyboardInterrupt:
        print("\nExiting...")
        db.close()
