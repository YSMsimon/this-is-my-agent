import math
import sys
import shutil

_BG = '\033[48;5;235m'   # grey15  (#262626)
_BW = '\033[1;37m'       # bold white
_R  = '\033[0m'


def print_user_message(message: str) -> None:
    """Redraw the submitted prompt line(s) with a full-width dark background.

    Handles multi-line input by moving up as many lines as prompt_toolkit
    occupied, then erasing to end of screen before redrawing.
    """
    width = shutil.get_terminal_size().columns
    full = f'  ❯  {message}'
    lines_occupied = max(1, math.ceil(len(full) / width))
    last_line_len = len(full) % width
    extra = (width - last_line_len) % width
    padded = full + ' ' * extra

    sys.stdout.write(f'\033[{lines_occupied}A\r\033[J{_BG}{_BW}{padded}{_R}\n')
    sys.stdout.flush()
