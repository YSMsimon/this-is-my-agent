import asyncio
import sys
import json
from agent.compact import Compactor
from common.config import config, write_env_key

COMMANDS = {
    '/help':                        'Show available commands',
    '/exit':                        'Exit the agent',
    '/delete-profile':              'Delete your saved user profile',
    '/profile':                     'Show your current user profile',
    '/clear-history':               'Delete all conversation history for your user',
    '/compact':                     'Compact conversation history into a summary',
    '/compact "<prompt>"':          'Compact with extra instructions (e.g. /compact "focus on code decisions")',
    '/simple':                      'Switch to simple conversation mode (faster)',
    '/deep':                        'Switch to deep conversation mode (more costly)',
    '/context-window <n|off>':      'Limit history to last N messages; use "off" to remove limit',
    '/model':                       'Show all current model settings',
    '/model <model>':               'Change main model (e.g. /model deepseek/deepseek-chat)',
    '/model <role> <model>':        'Change a sub-model role: compact, planner, evaluator, profile',
    '/model all <model>':           'Set all models (main + all sub-models) to the same model',
    '/apikey <provider> <key>':     'Change API key for a provider: deepseek, ollama',
}

_SUB_MODELS = {'compact', 'planner', 'evaluator', 'profile'}

_MODEL_ENV_KEYS = {
    'model':           'MODEL',
    'compact_model':   'COMPACT_MODEL',
    'planner_model':   'PLANNER_MODEL',
    'evaluator_model': 'EVALUATOR_MODEL',
    'profile_model':   'PROFILE_MODEL',
}


async def _stdin_confirm(prompt: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)


class CommandManager:
    def __init__(self, db, user_id: str, cfg: config, agent, confirm_fn=None):
        self.db = db
        self.user_id = user_id
        self.cfg = cfg
        self.agent = agent
        self._confirm = confirm_fn or _stdin_confirm

    def is_command(self, text: str) -> bool:
        return text.strip().startswith('/')

    async def handle(self, text: str) -> bool:
        cmd = text.strip().lower()

        if cmd == '/help':
            print("\nAvailable commands:")
            for name, desc in COMMANDS.items():
                print(f"  {name:<30} {desc}")
            print()
            return True

        if cmd == '/exit':
            print("Exiting...")
            await self.db.close()
            sys.exit(0)

        if cmd == '/delete-profile':
            confirm = await self._confirm("Delete your user profile? This cannot be undone. (Y/N): ")
            if confirm.strip().lower() == 'y':
                await self.db.delete_user_profile(self.user_id)
                print("Profile deleted.")
            else:
                print("Cancelled.")
            return True

        if cmd == '/profile':
            profile = await self.db.get_user_profile(self.user_id)
            if profile:
                print(json.dumps(profile, indent=2))
            else:
                print("No profile found.")
            return True

        if cmd == '/clear-history':
            confirm = await self._confirm("Delete all conversation history? This cannot be undone. (Y/N): ")
            if confirm.strip().lower() == 'y':
                await self.db.delete_user_history(self.user_id)
                print("History cleared.")
            else:
                print("Cancelled.")
            return True

        if text.strip().lower().startswith('/compact'):
            extra = text.strip()[len('/compact'):].strip().strip('"').strip("'") or None
            print("Compacting history...")
            compactor = Compactor(self.db, self.user_id, self.cfg, self.agent.adapter)
            summary = await compactor.compact(extra_prompt=extra)
            print(f"Done. Summary:\n{summary}")
            return True

        if cmd == '/simple':
            self.agent.mode = 'simple'
            print("Switched to simple mode.")
            return True

        if cmd == '/deep':
            self.agent.mode = 'deep'
            print("Switched to deep mode.")
            return True

        if text.strip().lower().startswith('/context-window'):
            raw = text.strip()[len('/context-window'):].strip()
            if not raw:
                current = self.cfg.context_window
                print(f"context window: {current if current is not None else 'off (no limit)'}")
                return True
            if raw.lower() == 'off':
                write_env_key('CONTEXT_WINDOW', '')
                self.cfg.context_window = None
                print("context window disabled — written to .env")
                return True
            try:
                value = int(raw)
            except ValueError:
                print(f"Invalid value '{raw}'. Use a positive integer or 'off'.")
                return True
            if value <= 0:
                print("context window must be a positive integer greater than 0.")
                return True
            write_env_key('CONTEXT_WINDOW', str(value))
            self.cfg.context_window = value
            print(f"context window set to {value} — written to .env")
            return True

        if text.strip().lower().startswith('/model'):
            raw = text.strip()[len('/model'):].strip()
            if not raw:
                cfg = self.cfg
                default = '(default)'
                print(f"  MODEL:           {cfg.model}")
                print(f"  COMPACT_MODEL:   {cfg.compact_model}{'' if cfg.compact_model != cfg.model else '  ' + default}")
                print(f"  PLANNER_MODEL:   {cfg.planner_model}{'' if cfg.planner_model != cfg.model else '  ' + default}")
                print(f"  EVALUATOR_MODEL: {cfg.evaluator_model}{'' if cfg.evaluator_model != cfg.model else '  ' + default}")
                print(f"  PROFILE_MODEL:   {cfg.profile_model}{'' if cfg.profile_model != cfg.model else '  ' + default}")
                return True
            parts = raw.split(None, 1)
            # normalise role: accept 'compact', 'compact_model', 'COMPACT_MODEL' etc.
            role_raw = parts[0].lower().removesuffix('_model')
            if len(parts) == 2 and role_raw == 'all':
                model_str = parts[1]
                if '/' not in model_str:
                    print(f"Model must be in 'provider/model' format, e.g. deepseek/deepseek-chat")
                    return True
                for cfg_key, env_key in _MODEL_ENV_KEYS.items():
                    write_env_key(env_key, model_str)
                    setattr(self.cfg, cfg_key, model_str)
                print(f"All models set to {model_str} — written to .env")
            elif len(parts) == 2 and role_raw in _SUB_MODELS:
                model_str = parts[1]
                if '/' not in model_str:
                    print(f"Model must be in 'provider/model' format, e.g. deepseek/deepseek-chat")
                    return True
                cfg_key = f"{role_raw}_model"
                write_env_key(_MODEL_ENV_KEYS[cfg_key], model_str)
                setattr(self.cfg, cfg_key, model_str)
                print(f"{role_raw} model set to {model_str} — written to .env")
            elif len(parts) == 2 and '/' not in parts[0]:
                print(f"Unknown role '{parts[0]}'. Use: compact, planner, evaluator, profile, all")
            else:
                model_str = parts[0]
                if '/' not in model_str:
                    print(f"Model must be in 'provider/model' format, e.g. deepseek/deepseek-chat")
                    return True
                write_env_key('MODEL', model_str)
                self.cfg.model = model_str
                print(f"Model set to {model_str} — written to .env")
            return True

        if text.strip().lower().startswith('/apikey'):
            raw = text.strip()[len('/apikey'):].strip()
            parts = raw.split(None, 1)
            if len(parts) != 2:
                print("Usage: /apikey <provider> <key>  (providers: deepseek, ollama, external)")
                return True
            provider, key = parts[0].lower(), parts[1].strip()
            if provider == 'deepseek':
                write_env_key('DEEPSEEK_API_KEY', key)
                self.agent.adapter._providers.pop('deepseek', None)
                print("DeepSeek API key updated in .env.")
            elif provider == 'ollama':
                write_env_key('OLLAMA_API_KEY', key)
                self.agent.adapter._providers.pop('ollama', None)
                print("Ollama API key updated in .env.")
            elif provider == 'external':
                write_env_key('EXTERNAL_API_KEY', key)
                self.agent.adapter._providers.pop('external', None)
                print("External API key updated in .env.")
            else:
                print(f"Unknown provider '{provider}'. Supported: deepseek, ollama, external")
            return True

        print(f"Unknown command: {text.strip()}. Type /help to see available commands.")
        return True
