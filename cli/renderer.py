import sys
import shutil
from rich.console import Console
from rich.markdown import Markdown


_console = Console(highlight=False)
_CLEAR_LINE = '\r' + ' ' * 30 + '\r'
_BG = '\033[48;5;235m'   # grey15
_BW = '\033[1;37m'       # bold white
_R  = '\033[0m'


def print_user_message(message: str) -> None:
    """Replace the prompt line with a full-width grey15 background line.

    Uses raw ANSI to avoid rich Console's internal cursor tracking interfering
    with the \033[A line-clear.
    """
    width = shutil.get_terminal_size().columns
    line = f"  {message}"
    padded = line + " " * max(0, width - len(line))
    sys.stdout.write(f'\033[A\033[2K\r{_BG}{_BW}{padded}{_R}\n')
    sys.stdout.flush()


class StreamRenderer:
    """Buffers streaming LLM output and renders it as markdown once complete."""

    def __init__(self):
        self._buf = ""

    def on_chunk(self, chunk: str) -> None:
        self._buf += chunk

    def stop(self) -> str:
        print(_CLEAR_LINE, end='', flush=True)
        if self._buf:
            _console.print(Markdown(self._buf))
        return self._buf

    @property
    def started(self) -> bool:
        return bool(self._buf)
