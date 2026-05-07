from pathlib import Path
from dotenv import load_dotenv
import os

WORKDIR = Path().cwd()
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


class config:
    def __init__(self):
        load_dotenv()
        self.base_url = os.getenv('BASE_URL')
        self.model = os.getenv('MODEL')
        self.embedding_model = os.getenv('EMBEDDING_MODEL')
        self.profile_model = os.getenv('PROFILE_MODEL')
        self.compact_model = os.getenv('COMPACT_MODEL')
        self.system_prompt = _load_prompt("agent.md")
        self.subagent_system_prompt = _load_prompt("subagent.md")
        self.compact_prompt = _load_prompt("compact.md")
        self.profile_prompt = _load_prompt("profile.md")
