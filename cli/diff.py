"""Claude Code-style diff rendering with red/green line backgrounds."""
import difflib
import shutil
from rich.panel import Panel
from rich.text import Text
from cli.theme import console

_MAX_LINES = 200  # truncate very large diffs


def _diff_text(old_lines: list[str], new_lines: list[str], context: int = 3) -> Text:
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm='', n=context))
    inner_w = max(40, shutil.get_terminal_size().columns - 6)
    out = Text(no_wrap=True, overflow='fold')

    shown = 0
    for line in diff[2:]:  # skip the --- +++ file headers
        if shown >= _MAX_LINES:
            out.append(f'  … diff truncated after {_MAX_LINES} lines …', style='dim yellow')
            break
        if line.startswith('-'):
            content = ('─ ' + line[1:]).ljust(inner_w)
            out.append(content, style='#ffaaaa on #3d1010')
        elif line.startswith('+'):
            content = ('+ ' + line[1:]).ljust(inner_w)
            out.append(content, style='#aaffaa on #103d10')
        elif line.startswith('@@'):
            out.append(line, style='dim cyan')
        else:
            out.append('  ' + line, style='dim')
        out.append('\n')
        shown += 1

    return out


def print_diff(file_path: str, old: str, new: str) -> None:
    """Print a unified diff between old and new content in Claude Code style."""
    old_lines = old.splitlines()
    new_lines = new.splitlines()

    if old_lines == new_lines:
        return

    out = _diff_text(old_lines, new_lines)
    console.print(Panel(
        out,
        title=f'[dim]{file_path}[/]',
        border_style='dim',
        padding=(0, 0),
    ))


def print_new_file(file_path: str, content: str) -> None:
    """Print all lines as additions for a newly created file."""
    inner_w = max(40, shutil.get_terminal_size().columns - 6)
    out = Text(no_wrap=True, overflow='fold')
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if i >= _MAX_LINES:
            out.append(f'  … {len(lines) - _MAX_LINES} more lines …', style='dim yellow')
            break
        out.append(('+ ' + line).ljust(inner_w), style='#aaffaa on #103d10')
        out.append('\n')
    console.print(Panel(
        out,
        title=f'[dim]{file_path}[/] [dim green](new file)[/]',
        border_style='dim green',
        padding=(0, 0),
    ))
