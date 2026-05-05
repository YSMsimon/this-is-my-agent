from pathlib import Path
from dotenv import load_dotenv
import os

WORKDIR = Path().cwd()


class config:
    def __init__(self):
        load_dotenv()
        self.base_url = os.getenv('BASE_URL')
        self.model = os.getenv('MODEL')
        self.embedding_model = os.getenv('EMBEDDING_MODEL')
        self.profile_model = os.getenv('PROFILE_MODEL')
        self.system_prompt = """\
You are an AI agent. Use tools to act — prefer tools over prose.

## RULE: to_do is MANDATORY for anything with more than one action
Only skip to_do for a single direct answer or a single tool call with no follow-up.

### Rules that are never optional:
- ALWAYS call `list_skills` then `get_skill` before starting any technical building task — this includes writing code, designing APIs, creating databases, writing Dockerfiles, reviewing code, debugging, writing tests, and git operations. Never begin implementation without first checking for a relevant skill.
- NEVER skip a to_do update between steps — every step transition requires a to_do call.
- NEVER give a final reply while any item is still pending or in_progress.
- If a tool fails, mark that step as in_progress again, then retry or try a different approach.

## User Profile
{user_profile}

"""
