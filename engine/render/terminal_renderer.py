"""終端機渲染器：ANSI 色碼整頁輸出，poll_actions() 以 input() 阻塞讀取。"""
from __future__ import annotations

import sys

from ..actions import Action, Back, Confirm, EndTurn, PlayCard, Quit, Reload
from ..grid import Grid
from .base import Renderer

ANSI_RESET = "\x1b[0m"
CLEAR_SCREEN = "\x1b[2J\x1b[H"

ANSI_FG = {
    "white": "37",
    "red": "31",
    "green": "32",
    "cyan": "36",
    "yellow": "33",
    "blue": "34",
    "gray": "90",
    "black": "30",
}
ANSI_BG = {
    "white": "47",
    "red": "41",
    "green": "42",
    "cyan": "46",
    "yellow": "43",
    "blue": "44",
    "gray": "100",
    "black": "40",
}


def _ensure_utf8_stdout() -> None:
    """避免 Windows 預設 cp950 造成中文亂碼。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def parse_action(line: str) -> Action | None:
    """把終端機輸入的一行文字轉成 Action；看不懂的輸入回傳 None。"""
    cmd = line.strip().lower()
    if cmd in ("1", "2", "3", "4", "5", "6", "7"):
        return PlayCard(int(cmd) - 1)
    if cmd == "e":
        return EndTurn()
    if cmd in ("", "enter"):
        return Confirm()
    if cmd == "b":
        return Back()
    if cmd == "r":
        return Reload()
    if cmd == "q":
        return Quit()
    return None


class TerminalRenderer(Renderer):
    def __init__(self, out=None) -> None:
        _ensure_utf8_stdout()
        self._out = out if out is not None else sys.stdout

    def render_to_string(self, grid: Grid) -> str:
        """把 grid 轉成含 ANSI 色碼的整頁字串，供 present() 輸出，也方便測試。"""
        lines = []
        for y in range(grid.height):
            parts = []
            current_fg: str | None = None
            current_bg: str | None = None
            for x in range(grid.width):
                cell = grid.get(x, y)
                if cell.wide_tail:
                    continue
                if cell.fg != current_fg or cell.bg != current_bg:
                    codes = [ANSI_FG.get(cell.fg, ANSI_FG["white"])]
                    if cell.bg:
                        codes.append(ANSI_BG.get(cell.bg, ANSI_BG["black"]))
                    parts.append(ANSI_RESET + f"\x1b[{';'.join(codes)}m")
                    current_fg = cell.fg
                    current_bg = cell.bg
                parts.append(cell.char if cell.char else " ")
            parts.append(ANSI_RESET)
            lines.append("".join(parts))
        return "\n".join(lines)

    def present(self, grid: Grid) -> None:
        if not grid.dirty:
            return
        self._out.write(CLEAR_SCREEN)
        self._out.write(self.render_to_string(grid))
        self._out.write("\n")
        self._out.flush()
        grid.dirty = False

    def poll_actions(self) -> list[Action]:
        try:
            line = input("> ")
        except EOFError:
            return [Quit()]
        action = parse_action(line)
        return [action] if action is not None else []

    def supports_animation(self) -> bool:
        return False
