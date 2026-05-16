from rich.console import Console
from rich.markdown import Markdown

_CLEAR_LINE = '\r' + ' ' * 30 + '\r'


class StreamRenderer:
    """Buffers streaming LLM output and renders it as markdown once complete."""

    def __init__(self):
        self._buf = ""

    def on_chunk(self, chunk: str) -> None:
        self._buf += chunk

    def stop(self) -> str:
        print(_CLEAR_LINE, end='', flush=True)
        if self._buf:
            Console(highlight=False).print(Markdown(self._buf))
        return self._buf

    @property
    def started(self) -> bool:
        return bool(self._buf)
