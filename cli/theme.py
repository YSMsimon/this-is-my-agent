from rich.console import Console
from rich.theme import Theme

_theme = Theme({
    'agent.tool':     'bold cyan',
    'agent.deep':     'cyan',
    'agent.executor': 'yellow',
    'agent.success':  'bold green',
    'agent.warn':     'yellow',
    'agent.error':    'bold red',
    'agent.token':    'dim',
    'agent.dim':      'dim white',
})

console = Console(theme=_theme, highlight=False)
