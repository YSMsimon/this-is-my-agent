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
        self.model = os.getenv('MODEL')
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434/v1')
        self.ollama_api_key = os.getenv('OLLAMA_API_KEY', "dummy")
        self.embedding_model = os.getenv('EMBEDDING_MODEL')
        self.profile_model = os.getenv('PROFILE_MODEL')
        self.compact_model = os.getenv('COMPACT_MODEL')
        self.evaluator_model = os.getenv('EVALUATOR_MODEL')
        self.planner_model = os.getenv('PLANNER_MODEL')
        self.system_prompt = _load_prompt("agent.md")
        self.subagent_system_prompt = _load_prompt("subagent.md")
        self.compact_prompt = _load_prompt("compact.md")
        self.profile_prompt = _load_prompt("profile.md")
        self.planner_prompt = _load_prompt("planner.md")
        self.executor_prompt = _load_prompt("executor.md")
        self.evaluator_prompt = _load_prompt("evaluator.md")
