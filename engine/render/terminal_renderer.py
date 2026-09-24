"""終端機渲染器：ANSI 色碼整頁輸出，poll_actions() 以 input() 阻塞讀取。"""
from __future__ import annotations

import shutil
import sys

from .. import palette
from ..actions import Action, Back, Confirm, EndTurn, Inspect, PlayCard, Quit, Reload
from ..grid import Grid
from .base import Renderer

ANSI_RESET = "\x1b[0m"
CLEAR_SCREEN = "\x1b[2J\x1b[H"

MIN_TERMINAL_WIDTH = 96
MIN_TERMINAL_HEIGHT = 33  # 32 格畫面 + 至少 1 行輸入提示


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
    if cmd.startswith("?"):
        rest = cmd[1:]
        if rest == "":
            return Inspect(None)
        if rest.isdigit():
            return Inspect(int(rest) - 1)
        return None
    return None


class TerminalRenderer(Renderer):
    def __init__(self, out=None, terminal_size: tuple[int, int] | None = None) -> None:
        _ensure_utf8_stdout()
        self._out = out if out is not None else sys.stdout
        self._terminal_size = terminal_size

    def _get_terminal_size(self) -> tuple[int, int]:
        if self._terminal_size is not None:
            return self._terminal_size
        size = shutil.get_terminal_size(fallback=(MIN_TERMINAL_WIDTH, MIN_TERMINAL_HEIGHT))
        return size.columns, size.lines

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
                    seq = ANSI_RESET + f"\x1b[38;5;{palette.ansi256(cell.fg)}m"
                    if cell.bg:
                        seq += f"\x1b[48;5;{palette.ansi256(cell.bg)}m"
                    parts.append(seq)
                    current_fg = cell.fg
                    current_bg = cell.bg
                parts.append(cell.char if cell.char else " ")
            parts.append(ANSI_RESET)
            lines.append("".join(parts))
        return "\n".join(lines)

    def present(self, grid: Grid) -> None:
        if not grid.dirty:
            return
        cols, lines = self._get_terminal_size()
        if cols < MIN_TERMINAL_WIDTH or lines < MIN_TERMINAL_HEIGHT:
            self._out.write(CLEAR_SCREEN)
            self._out.write(
                f"視窗太小，請放大終端機視窗到至少 {MIN_TERMINAL_WIDTH} 欄 x "
                f"{MIN_TERMINAL_HEIGHT} 列後再繼續。\n"
                f"目前視窗大小：{cols} 欄 x {lines} 列。\n"
            )
            self._out.flush()
            grid.dirty = False
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

    def supports_mouse(self) -> bool:
        return False
