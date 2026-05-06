from memory.db import DB
from common.config import config
from agent.loop import Agent
from cli.commands import CommandManager
from tools.manager import all_tools

if __name__ == '__main__':
    db = DB()
    cfg = config()
    agent = Agent(cfg, tools=all_tools, db=db)
    commands = CommandManager(db, agent.user_id, cfg)
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
