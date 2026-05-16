from cli.commands import COMMANDS

SLASH_COMMANDS = sorted({k.split()[0] for k in COMMANDS.keys()})
