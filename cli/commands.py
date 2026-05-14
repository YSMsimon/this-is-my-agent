import sys
import json
from aioconsole import ainput, aprint
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
    '/apikey <provider> <key>':     'Change API key for a provider: deepseek, ollama',
}

_SUB_MODELS = {'compact', 'planner', 'evaluator', 'profile'}


class CommandManager:
    def __init__(self, db, user_id: str, cfg: config, agent):
        self.db = db
        self.user_id = user_id
        self.cfg = cfg
        self.agent = agent

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
            confirm = await ainput("Delete your user profile? This cannot be undone. (Y/N): ")
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
            confirm = await ainput("Delete all conversation history? This cannot be undone. (Y/N): ")
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
            await aprint(f"Done. Summary:\n{summary}")
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
                current = self.agent.context_window
                print(f"context window: {current if current is not None else 'off (no limit)'}")
                return True
            if raw.lower() == 'off':
                await self.db.set_context_window(self.user_id, None)
                self.agent.context_window = None
                self.agent._context_window_loaded = True
                print("context window disabled — full history will be loaded.")
                return True
            try:
                value = int(raw)
            except ValueError:
                print(f"Invalid value '{raw}'. Use a positive integer or 'off'.")
                return True
            if value <= 0:
                print("context window must be a positive integer greater than 0.")
                return True
            await self.db.set_context_window(self.user_id, value)
            self.agent.context_window = value
            self.agent._context_window_loaded = True
            print(f"context window set to {value} messages.")
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
            if len(parts) == 2 and role_raw in _SUB_MODELS:
                model_str = parts[1]
                if '/' not in model_str:
                    print(f"Model must be in 'provider/model' format, e.g. deepseek/deepseek-chat")
                    return True
                db_key = f"{role_raw}_model"
                await self.db.set_user_setting(self.user_id, db_key, model_str)
                setattr(self.cfg, db_key, model_str)
                print(f"{role_raw} model set to {model_str}")
            elif len(parts) == 2 and '/' not in parts[0]:
                # two words but first isn't a known role
                print(f"Unknown role '{parts[0]}'. Use: compact, planner, evaluator, profile")
            else:
                model_str = parts[0]
                if '/' not in model_str:
                    print(f"Model must be in 'provider/model' format, e.g. deepseek/deepseek-chat")
                    return True
                await self.db.set_user_setting(self.user_id, 'model', model_str)
                self.cfg.model = model_str
                print(f"Model set to {model_str}")
            return True

        if text.strip().lower().startswith('/apikey'):
            raw = text.strip()[len('/apikey'):].strip()
            parts = raw.split(None, 1)
            if len(parts) != 2:
                print("Usage: /apikey <provider> <key>  (providers: deepseek, ollama)")
                return True
            provider, key = parts[0].lower(), parts[1].strip()
            if provider == 'deepseek':
                write_env_key('DEEPSEEK_API_KEY', key)
                self.cfg.deepseek_api_key = key
                self.agent.adapter._providers.pop('deepseek', None)
                print("DeepSeek API key updated in .env.")
            elif provider == 'ollama':
                write_env_key('OLLAMA_API_KEY', key)
                self.cfg.ollama_api_key = key
                self.agent.adapter._providers.pop('ollama', None)
                print("Ollama API key updated in .env.")
            else:
                print(f"Unknown provider '{provider}'. Supported: deepseek, ollama")
            return True

        print(f"Unknown command: {text.strip()}. Type /help to see available commands.")
        return True
