import sys
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
}

class CommandManager:
    def __init__(self, db, user_id: str, cfg: config):
        self.db = db
        self.user_id = user_id
        self.cfg = cfg

    def is_command(self, text: str) -> bool:
        return text.strip().startswith('/')

    def handle(self, text: str) -> bool:
        cmd = text.strip().lower()

        if cmd == '/help':
            print("\nAvailable commands:")
            for name, desc in COMMANDS.items():
                print(f"  {name:<20} {desc}")
            print()
            return True

        if cmd == '/exit':
            print("Exiting...")
            self.db.close()
            sys.exit(0)

        if cmd == '/delete-profile':
            confirm = input("Delete your user profile? This cannot be undone. (Y/N): ").strip().lower()
            if confirm == 'y':
                self.db.delete_user_profile(self.user_id)
                print("Profile deleted.")
            else:
                print("Cancelled.")
            return True

        if cmd == '/profile':
            profile = self.db.get_user_profile(self.user_id)
            if profile:
                import json
                print(json.dumps(profile, indent=2))
            else:
                print("No profile found.")
            return True

        if cmd == '/clear-history':
            confirm = input("Delete all conversation history? This cannot be undone. (Y/N): ").strip().lower()
            if confirm == 'y':
                self.db.delete_user_history(self.user_id)
                print("History cleared.")
            else:
                print("Cancelled.")
            return True

        if text.strip().lower().startswith('/compact'):
            extra = text.strip()[len('/compact'):].strip().strip('"').strip("'") or None
            print("Compacting history...")
            compactor = Compactor(self.db, self.user_id, self.cfg)
            summary = compactor.compact(extra_prompt=extra)
            print(f"Done. Summary:\n{summary}")
            return True

        print(f"Unknown command: {cmd}. Type /help to see available commands.")
        return True
