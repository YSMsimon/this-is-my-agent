import asyncio
import sys
import json
from agent.compact import Compactor
from common.config import config, write_env_key
from cli.theme import console
from rich.table import Table

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
            t = Table(box=None, show_header=False, padding=(0, 2))
            t.add_column(style='bold cyan', no_wrap=True)
            t.add_column(style='dim')
            for name, desc in COMMANDS.items():
                t.add_row(name, desc)
            console.print()
            console.print(t)
            console.print()
            return True

        if cmd == '/exit':
            console.print('[dim]Exiting…[/]')
            await self.db.close()
            sys.exit(0)

        if cmd == '/delete-profile':
            confirm = await self._confirm("Delete your user profile? This cannot be undone. (Y/N): ")
            if confirm.strip().lower() == 'y':
                await self.db.delete_user_profile(self.user_id)
                console.print('[agent.success]✓[/] Profile deleted.')
            else:
                console.print('[dim]Cancelled.[/]')
            return True

        if cmd == '/profile':
            profile = await self.db.get_user_profile(self.user_id)
            if profile:
                console.print_json(json.dumps(profile))
            else:
                console.print('[dim]No profile found.[/]')
            return True

        if cmd == '/clear-history':
            confirm = await self._confirm("Delete all conversation history? This cannot be undone. (Y/N): ")
            if confirm.strip().lower() == 'y':
                await self.db.delete_user_history(self.user_id)
                console.print('[agent.success]✓[/] History cleared.')
            else:
                console.print('[dim]Cancelled.[/]')
            return True

        if text.strip().lower().startswith('/compact'):
            extra = text.strip()[len('/compact'):].strip().strip('"').strip("'") or None
            with console.status('[dim]Compacting history…[/]', spinner='dots'):
                compactor = Compactor(self.db, self.user_id, self.cfg, self.agent.adapter)
                summary = await compactor.compact(extra_prompt=extra)
            console.print(f'[agent.success]✓[/] [dim]Done.[/]\n\n{summary}')
            return True

        if cmd == '/simple':
            self.agent.mode = 'simple'
            console.print('[dim]Switched to [bold]simple[/] mode.[/]')
            return True

        if cmd == '/deep':
            self.agent.mode = 'deep'
            console.print('[dim]Switched to [bold cyan]deep[/] mode.[/]')
            return True

        if text.strip().lower().startswith('/context-window'):
            raw = text.strip()[len('/context-window'):].strip()
            if not raw:
                current = self.cfg.context_window
                console.print(f'[dim]context window:[/] {current if current is not None else "off (no limit)"}')
                return True
            if raw.lower() == 'off':
                write_env_key('CONTEXT_WINDOW', '')
                self.cfg.context_window = None
                console.print('[dim]context window [bold]disabled[/] — written to .env[/]')
                return True
            try:
                value = int(raw)
            except ValueError:
                console.print(f"[agent.warn]Invalid value '{raw}'.[/] Use a positive integer or 'off'.")
                return True
            if value <= 0:
                console.print('[agent.warn]context window must be a positive integer greater than 0.[/]')
                return True
            write_env_key('CONTEXT_WINDOW', str(value))
            self.cfg.context_window = value
            console.print(f'[dim]context window set to [bold]{value}[/] — written to .env[/]')
            return True

        if text.strip().lower().startswith('/model'):
            raw = text.strip()[len('/model'):].strip()
            if not raw:
                cfg = self.cfg
                t = Table.grid(padding=(0, 2))
                t.add_column(style='dim', width=18)
                t.add_column(style='white')
                t.add_column(style='dim green')
                t.add_row('model',     cfg.model,           '')
                for label, val in [
                    ('compact',   cfg.compact_model),
                    ('planner',   cfg.planner_model),
                    ('evaluator', cfg.evaluator_model),
                    ('profile',   cfg.profile_model),
                ]:
                    tag = '(= model)' if val == cfg.model else ''
                    t.add_row(label, val, tag)
                console.print(t)
                return True
            parts = raw.split(None, 1)
            role_raw = parts[0].lower().removesuffix('_model')
            if len(parts) == 2 and role_raw == 'all':
                model_str = parts[1]
                if '/' not in model_str:
                    console.print("[agent.warn]Model must be in 'provider/model' format.[/]")
                    return True
                for cfg_key, env_key in _MODEL_ENV_KEYS.items():
                    write_env_key(env_key, model_str)
                    setattr(self.cfg, cfg_key, model_str)
                console.print(f'[agent.success]✓[/] All models set to [bold]{model_str}[/]')
            elif len(parts) == 2 and role_raw in _SUB_MODELS:
                model_str = parts[1]
                if '/' not in model_str:
                    console.print("[agent.warn]Model must be in 'provider/model' format.[/]")
                    return True
                cfg_key = f"{role_raw}_model"
                write_env_key(_MODEL_ENV_KEYS[cfg_key], model_str)
                setattr(self.cfg, cfg_key, model_str)
                console.print(f'[agent.success]✓[/] [dim]{role_raw}[/] model set to [bold]{model_str}[/]')
            elif len(parts) == 2 and '/' not in parts[0]:
                console.print(f"[agent.warn]Unknown role '{parts[0]}'.[/] Use: compact, planner, evaluator, profile, all")
            else:
                model_str = parts[0]
                if '/' not in model_str:
                    console.print("[agent.warn]Model must be in 'provider/model' format.[/]")
                    return True
                write_env_key('MODEL', model_str)
                self.cfg.model = model_str
                console.print(f'[agent.success]✓[/] Model set to [bold]{model_str}[/]')
            return True

        if text.strip().lower().startswith('/apikey'):
            raw = text.strip()[len('/apikey'):].strip()
            parts = raw.split(None, 1)
            if len(parts) != 2:
                console.print('[dim]Usage:[/] /apikey <provider> <key>  [dim](providers: deepseek, ollama, external)[/]')
                return True
            provider, key = parts[0].lower(), parts[1].strip()
            if provider == 'deepseek':
                write_env_key('DEEPSEEK_API_KEY', key)
                self.agent.adapter._providers.pop('deepseek', None)
                console.print('[agent.success]✓[/] DeepSeek API key updated.')
            elif provider == 'ollama':
                write_env_key('OLLAMA_API_KEY', key)
                self.agent.adapter._providers.pop('ollama', None)
                console.print('[agent.success]✓[/] Ollama API key updated.')
            elif provider == 'external':
                write_env_key('EXTERNAL_API_KEY', key)
                self.agent.adapter._providers.pop('external', None)
                console.print('[agent.success]✓[/] External API key updated.')
            else:
                console.print(f"[agent.warn]Unknown provider '{provider}'.[/] Supported: deepseek, ollama, external")
            return True

        console.print(f"[agent.warn]Unknown command:[/] {text.strip()}  [dim]Type /help to see available commands.[/]")
        return True
