import sys
import json
from aioconsole import ainput, aprint
from agent.compact import Compactor
from common.config import config

COMMANDS = {
    '/help':              'Show available commands',
    '/exit':              'Exit the agent',
    '/delete-profile':    'Delete your saved user profile',
    '/profile':           'Show your current user profile',
    '/clear-history':     'Delete all conversation history for your user',
    '/compact':           'Compact conversation history into a summary',
    '/compact "<prompt>"':'Compact with extra instructions (e.g. /compact "focus on code decisions")',
    '/simple':           'Switch to simple conversation mode (faster)',
    '/deep':             'Switch to deep conversation mode (more costly)'
}


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
                print(f"  {name:<20} {desc}")
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

        print(f"Unknown command: {cmd}. Type /help to see available commands.")
        return True
