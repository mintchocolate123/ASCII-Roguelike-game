"""繪圖函式：文字、框線、血條、ASCII 圖、卡牌。只寫入 Grid，不認識渲染器。"""
from __future__ import annotations

import unicodedata

from .grid import Grid

# 具名色表，兩種渲染器各自對應到 RGB 或 ANSI 色碼。
COLOR_NAMES = ("white", "red", "green", "cyan", "yellow", "blue", "gray", "black")

BOX_CHARS = {
    "tl": "┌",
    "tr": "┐",
    "bl": "└",
    "br": "┘",
    "h": "─",
    "v": "│",
}

BLOCK_FULL = "█"
BLOCK_EMPTY = "░"


def char_width(ch: str) -> int:
    """單一字元佔用的格數：東亞全形（W、F）為 2，其餘為 1。"""
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def text_width(s: str) -> int:
    """字串在畫面上實際佔用的格數，供排版計算使用。"""
    return sum(char_width(ch) for ch in s)


def draw_text(
    grid: Grid, x: int, y: int, text: str, fg: str = "white", bg: str | None = None
) -> int:
    """在 (x, y) 寫入文字，寬字元佔兩格。回傳寫入後下一個可用的 x 座標。"""
    cx = x
    for ch in text:
        w = char_width(ch)
        grid.set_cell(cx, y, ch, fg, bg)
        if w == 2:
            grid.set_cell(cx + 1, y, "", fg, bg, wide_tail=True)
        cx += w
    return cx


def draw_box(
    grid: Grid,
    x: int,
    y: int,
    w: int,
    h: int,
    fg: str = "white",
    bg: str | None = None,
    title: str | None = None,
) -> None:
    """畫一個矩形框線，w、h 為外框寬高（含邊線）。"""
    if w < 2 or h < 2:
        return
    grid.set_cell(x, y, BOX_CHARS["tl"], fg, bg)
    grid.set_cell(x + w - 1, y, BOX_CHARS["tr"], fg, bg)
    grid.set_cell(x, y + h - 1, BOX_CHARS["bl"], fg, bg)
    grid.set_cell(x + w - 1, y + h - 1, BOX_CHARS["br"], fg, bg)
    for i in range(1, w - 1):
        grid.set_cell(x + i, y, BOX_CHARS["h"], fg, bg)
        grid.set_cell(x + i, y + h - 1, BOX_CHARS["h"], fg, bg)
    for j in range(1, h - 1):
        grid.set_cell(x, y + j, BOX_CHARS["v"], fg, bg)
        grid.set_cell(x + w - 1, y + j, BOX_CHARS["v"], fg, bg)
    if title:
        tw = text_width(title)
        title_x = x + max(1, (w - tw) // 2)
        draw_text(grid, title_x, y, title, fg, bg)


def draw_hp_bar(
    grid: Grid,
    x: int,
    y: int,
    width: int,
    current: int,
    maximum: int,
    fg: str = "green",
    empty_fg: str = "gray",
    bg: str | None = None,
) -> None:
    """畫血條，依 current/maximum 比例決定填滿格數。"""
    maximum = max(maximum, 1)
    current = max(0, min(current, maximum))
    filled = round(width * current / maximum)
    for i in range(width):
        if i < filled:
            grid.set_cell(x + i, y, BLOCK_FULL, fg, bg)
        else:
            grid.set_cell(x + i, y, BLOCK_EMPTY, empty_fg, bg)


def draw_ascii_art(
    grid: Grid, x: int, y: int, lines: list[str], fg: str = "white", bg: str | None = None
) -> None:
    """逐行畫出 ASCII 圖。"""
    for row_offset, line in enumerate(lines):
        draw_text(grid, x, y + row_offset, line, fg, bg)


def draw_card(
    grid: Grid,
    x: int,
    y: int,
    w: int,
    h: int,
    name: str,
    cost: int,
    body_lines: list[str] | None = None,
    fg: str = "white",
    bg: str | None = None,
) -> None:
    """畫一張卡牌：外框、費用、置中名稱與內文。"""
    draw_box(grid, x, y, w, h, fg, bg)
    draw_text(grid, x + 1, y, str(cost), fg, bg)
    name_x = x + max(1, (w - text_width(name)) // 2)
    draw_text(grid, name_x, y + 1, name, fg, bg)
    for i, line in enumerate(body_lines or []):
        draw_text(grid, x + 1, y + 2 + i, line, fg, bg)
