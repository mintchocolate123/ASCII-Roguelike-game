"""繪圖函式：文字、換行、框線、血條、ASCII 圖、卡牌。只寫入 Grid，不認識渲染器。"""
from __future__ import annotations

import unicodedata

from .grid import Grid

BOX_STYLES = {
    "single": {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│"},
    "double": {"tl": "╔", "tr": "╗", "bl": "╚", "br": "╝", "h": "═", "v": "║"},
}

TYPE_COLORS = {"attack": "attack", "skill": "skill", "power": "power"}
TYPE_LABELS = {"attack": "攻擊", "skill": "技能", "power": "能力"}

BLOCK_FULL = "█"
BLOCK_EMPTY = "░"

# 行首禁則：這些標點不可以出現在一行的開頭。
FORBIDDEN_LEADING = set("，。、；：！？）」』…")


# ---------------------------------------------------------------------------
# 寬度計算
# ---------------------------------------------------------------------------


def char_width(ch: str) -> int:
    """單一字元佔用的格數：東亞全形（W、F）為 2，其餘（含寬度不明確的 A 類，如 ─═║█░◆◇●）為 1。"""
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def text_width(s: str) -> int:
    """字串在畫面上實際佔用的格數，供排版計算使用。"""
    return sum(char_width(ch) for ch in s)


# ---------------------------------------------------------------------------
# 換行
# ---------------------------------------------------------------------------


def _tokenize(s: str) -> list[str]:
    """把字串切成排版單位：連續 ASCII 英數字視為一個單位，其餘每個字元各自成一個單位。"""
    tokens: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch.isascii() and ch.isalnum():
            j = i + 1
            while j < n and s[j].isascii() and s[j].isalnum():
                j += 1
            tokens.append(s[i:j])
            i = j
        else:
            tokens.append(ch)
            i += 1
    return tokens


def _merge_forbidden_leading(tokens: list[str]) -> list[str]:
    """把行首禁則標點黏在前一個單位後面，讓它們永遠不會被拆到下一行的開頭。"""
    merged: list[str] = []
    for tok in tokens:
        if merged and tok in FORBIDDEN_LEADING:
            merged[-1] += tok
        else:
            merged.append(tok)
    return merged


def _split_oversized(unit: str, width: int) -> list[str]:
    """單位本身超過 width 時才強制切斷。"""
    pieces: list[str] = []
    start = 0
    n = len(unit)
    while start < n:
        end = start
        w = 0
        while end < n:
            cw = char_width(unit[end])
            if w + cw > width:
                break
            w += cw
            end += 1
        if end == start:
            end = start + 1  # 單一字元本身就超過 width，至少前進一格避免死迴圈
        pieces.append(unit[start:end])
        start = end
    return pieces


def _pack_line(units: list[str], width: int) -> list[str]:
    lines: list[str] = []
    current: list[str] = []
    current_width = 0
    for unit in units:
        uw = text_width(unit)
        if uw > width:
            if current:
                lines.append("".join(current))
                current = []
                current_width = 0
            lines.extend(_split_oversized(unit, width))
            continue
        if current_width + uw > width:
            lines.append("".join(current))
            current = [unit]
            current_width = uw
        else:
            current.append(unit)
            current_width += uw
    if current:
        lines.append("".join(current))
    return lines


def wrap_text(text: str, width: int) -> list[str]:
    """依顯示寬度換行。中文字之間可斷行；連續英數字視為一個單位；行首禁止標點；`\\n` 強制換行。"""
    if text == "":
        return []
    result: list[str] = []
    for segment in text.split("\n"):
        if segment == "":
            result.append("")
            continue
        units = _merge_forbidden_leading(_tokenize(segment))
        result.extend(_pack_line(units, width))
    return result


# ---------------------------------------------------------------------------
# 基本圖形
# ---------------------------------------------------------------------------


def draw_text(grid: Grid, x: int, y: int, text: str, fg: str = "text", bg: str | None = None) -> int:
    """在 (x, y) 寫入文字，寬字元佔兩格。回傳寫入後下一個可用的 x 座標。"""
    cx = x
    for ch in text:
        w = char_width(ch)
        if w == 2 and cx + 1 >= grid.width:
            break  # 寬字元只剩一格空間時整個字不畫
        grid.set_cell(cx, y, ch, fg, bg)
        if w == 2:
            grid.set_cell(cx + 1, y, "", fg, bg, wide_tail=True)
        cx += w
    return cx


def draw_hline(
    grid: Grid,
    x: int,
    y: int,
    length: int,
    fg: str = "frame",
    bg: str | None = None,
    double: bool = True,
    left_cap: str | None = None,
    right_cap: str | None = None,
) -> None:
    """畫一條水平線，可指定兩端要覆寫的轉角/T 字符號。"""
    ch = "═" if double else "─"
    for i in range(length):
        grid.set_cell(x + i, y, ch, fg, bg)
    if left_cap:
        grid.set_cell(x, y, left_cap, fg, bg)
    if right_cap:
        grid.set_cell(x + length - 1, y, right_cap, fg, bg)


def draw_vline(
    grid: Grid,
    x: int,
    y: int,
    length: int,
    fg: str = "frame",
    bg: str | None = None,
    double: bool = True,
    top_cap: str | None = None,
    bottom_cap: str | None = None,
) -> None:
    """畫一條垂直線，可指定兩端要覆寫的轉角/T 字符號。"""
    ch = "║" if double else "│"
    for i in range(length):
        grid.set_cell(x, y + i, ch, fg, bg)
    if top_cap:
        grid.set_cell(x, y, top_cap, fg, bg)
    if bottom_cap:
        grid.set_cell(x, y + length - 1, bottom_cap, fg, bg)


def draw_box(
    grid: Grid,
    x: int,
    y: int,
    w: int,
    h: int,
    fg: str = "frame",
    bg: str | None = None,
    title: str | None = None,
    style: str = "single",
) -> None:
    """畫一個矩形框線，w、h 為外框寬高（含邊線）。style 為 'single' 或 'double'。"""
    if w < 2 or h < 2:
        return
    chars = BOX_STYLES.get(style, BOX_STYLES["single"])
    grid.set_cell(x, y, chars["tl"], fg, bg)
    grid.set_cell(x + w - 1, y, chars["tr"], fg, bg)
    grid.set_cell(x, y + h - 1, chars["bl"], fg, bg)
    grid.set_cell(x + w - 1, y + h - 1, chars["br"], fg, bg)
    for i in range(1, w - 1):
        grid.set_cell(x + i, y, chars["h"], fg, bg)
        grid.set_cell(x + i, y + h - 1, chars["h"], fg, bg)
    for j in range(1, h - 1):
        grid.set_cell(x, y + j, chars["v"], fg, bg)
        grid.set_cell(x + w - 1, y + j, chars["v"], fg, bg)
    if title:
        tw = text_width(title)
        title_x = x + max(1, (w - tw) // 2)
        draw_text(grid, title_x, y, title, fg, bg)


def draw_banner(
    grid: Grid,
    x: int,
    y: int,
    width: int,
    name: str,
    frame_fg: str = "frame",
    text_fg: str = "text",
    bg: str | None = None,
) -> None:
    """畫置中的標題帶，例如 ════[ 哥布林 ]════，框線與名稱分開上色。"""
    for i in range(width):
        grid.set_cell(x + i, y, "═", frame_fg, bg)
    label = f"[ {name} ]"
    lw = text_width(label)
    start = x + max(0, (width - lw) // 2)
    cx = draw_text(grid, start, y, "[ ", frame_fg, bg)
    cx = draw_text(grid, cx, y, name, text_fg, bg)
    draw_text(grid, cx, y, " ]", frame_fg, bg)


def draw_hp_bar(
    grid: Grid,
    x: int,
    y: int,
    width: int,
    current: int,
    maximum: int,
    fg: str = "hp",
    empty_fg: str = "hp_empty",
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


def draw_energy_pips(
    grid: Grid, x: int, y: int, current: int, maximum: int, fg: str = "energy", bg: str | None = None
) -> int:
    """畫能量點數，◆ 為剩餘、◇ 為已用。回傳寫入後下一個可用的 x 座標。"""
    current = max(0, min(current, maximum))
    text = "◆" * current + "◇" * (maximum - current)
    return draw_text(grid, x, y, text, fg, bg)


def draw_ascii_art(
    grid: Grid, x: int, y: int, lines: list[str], fg: str = "text", bg: str | None = None
) -> None:
    """逐行畫出 ASCII 圖。"""
    for row_offset, line in enumerate(lines):
        draw_text(grid, x, y + row_offset, line, fg, bg)


# ---------------------------------------------------------------------------
# 卡牌
# ---------------------------------------------------------------------------


def draw_keyword_text(
    grid: Grid,
    x: int,
    y: int,
    text: str,
    base_fg: str = "text",
    keyword_fg: str = "keyword",
    bg: str | None = None,
) -> int:
    """畫一行文字，【】包住的片段改用 keyword_fg 上色，括號本身不顯示。"""
    cx = x
    buf = ""
    in_keyword = False

    def flush(color: str) -> None:
        nonlocal cx, buf
        if buf:
            cx = draw_text(grid, cx, y, buf, color, bg)
            buf = ""

    for ch in text:
        if ch == "【":
            flush(base_fg)
            in_keyword = True
        elif ch == "】":
            flush(keyword_fg)
            in_keyword = False
        else:
            buf += ch
    flush(keyword_fg if in_keyword else base_fg)
    return cx


def draw_card(
    grid: Grid,
    x: int,
    y: int,
    name: str,
    cost: int,
    card_type: str,
    description: str,
    playable: bool = True,
    highlighted: bool = False,
    w: int = 12,
    h: int = 10,
) -> None:
    """畫一張卡牌：雙線外框、費用、名稱、分隔線與描述。"""
    if not playable:
        border_fg = text_fg = cost_fg = type_fg = "dim"
    elif highlighted:
        border_fg = type_fg = "highlight"
        text_fg = "text"
        cost_fg = "energy"
    else:
        border_fg = type_fg = TYPE_COLORS.get(card_type, "frame")
        text_fg = "text"
        cost_fg = "energy"

    draw_box(grid, x, y, w, h, fg=border_fg, style="double")

    draw_text(grid, x + 1, y, f"◆{cost}", cost_fg)

    name_x = x + max(1, (w - text_width(name)) // 2)
    draw_text(grid, name_x, y + 1, name, text_fg)

    grid.set_cell(x, y + 2, "╟", border_fg)
    grid.set_cell(x + w - 1, y + 2, "╢", border_fg)
    for i in range(1, w - 1):
        grid.set_cell(x + i, y + 2, "─", border_fg)

    lines = wrap_text(description, w - 2)[:6]
    for li, line in enumerate(lines):
        ly = y + 3 + li
        if not playable:
            plain = line.replace("【", "").replace("】", "")
            draw_text(grid, x + 1, ly, plain, "dim")
        else:
            draw_keyword_text(grid, x + 1, ly, line, "text", "keyword")

    label = TYPE_LABELS.get(card_type, card_type)
    label_x = x + max(1, (w - text_width(label)) // 2)
    draw_text(grid, label_x, y + h - 1, label, type_fg)
