import sys
import re
from pathlib import Path
from dotenv import load_dotenv
import os

_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
WORKDIR = Path().cwd()
_PROMPTS_DIR = _PROJECT_ROOT / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def write_env_key(key: str, value: str):
    text = _ENV_PATH.read_text() if _ENV_PATH.exists() else ''
    pattern = re.compile(rf'^{re.escape(key)}\s*=.*$', re.MULTILINE)
    new_line = f'{key}={value}'
    if pattern.search(text):
        text = pattern.sub(new_line, text)
    else:
        text = text.rstrip('\n') + f'\n{new_line}\n'
    _ENV_PATH.write_text(text)
    os.environ[key] = value
    load_dotenv(dotenv_path=_ENV_PATH, override=True)


class config:
    def __init__(self):
        load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")
        self.model = os.getenv('MODEL')
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434/v1')
        self.ollama_api_key = os.getenv('OLLAMA_API_KEY', "dummy")
        self.external_api_key = os.getenv('EXTERNAL_API_KEY', "dummy")
        self.external_base_url = os.getenv('EXTERNAL_BASE_URL', 'https://openrouter.ai/api/v1')
        self.profile_model = os.getenv('PROFILE_MODEL') or self.model
        self.compact_model = os.getenv('COMPACT_MODEL') or self.model
        self.evaluator_model = os.getenv('EVALUATOR_MODEL') or self.model
        self.planner_model = os.getenv('PLANNER_MODEL') or self.model
        self.system_prompt = _load_prompt("agent.md")
        self.subagent_system_prompt = _load_prompt("subagent.md")
        self.compact_prompt = _load_prompt("compact.md")
        self.profile_prompt = _load_prompt("profile.md")
        self.planner_prompt = _load_prompt("planner.md")
        self.executor_prompt = _load_prompt("executor.md")
        self.evaluator_prompt = _load_prompt("evaluator.md")
        self.reasoning_prompt = _load_prompt("reasoning.md")
        self.compact_merge_prompt = _load_prompt("compact_merge.md")
        self._validate()

    def _validate(self):
        missing = []
        if not self.model:
            missing.append('MODEL')
        provider = self.model.split('/')[0] if self.model else None
        if provider == 'deepseek' and not self.deepseek_api_key:
            missing.append('DEEPSEEK_API_KEY')
        if provider == 'external' and not os.getenv('EXTERNAL_API_KEY'):
            missing.append('EXTERNAL_API_KEY')
        if provider == 'external' and not os.getenv('EXTERNAL_BASE_URL'):
            missing.append('EXTERNAL_BASE_URL')
        if missing:
            print(f"Missing required .env variables: {', '.join(missing)}")
            sys.exit(1)
