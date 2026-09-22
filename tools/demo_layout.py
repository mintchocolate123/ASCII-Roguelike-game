"""1b 驗收 demo：用假資料畫出完整戰鬥畫面，跟 CLAUDE.md「畫面版面」一節的參考圖比對。

包含至少 5 張描述長度不同的卡牌，以及一張能量不足（灰階）的卡牌。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import layout
from engine.cardtext import resolve_description
from engine.draw import (
    draw_ascii_art,
    draw_banner,
    draw_box,
    draw_card,
    draw_energy_pips,
    draw_hline,
    draw_hp_bar,
    draw_text,
    draw_vline,
    text_width,
    wrap_text,
)
from engine.grid import Grid
from engine.render.terminal_renderer import TerminalRenderer

GOBLIN_ART = [
    "        .-\"\"\"-.        ",
    "       /  o o  \\       ",
    "      |    ^    |      ",
    "       \\ \\___/ /       ",
    "      __'-----'__      ",
    "     /  |     |  \\     ",
    "    /   |_____|   \\    ",
    "        /     \\        ",
    "       /_/   \\_\\       ",
    "                        ",
]

BATTLE_LOG = [
    "斬擊 造成 6 傷害",
    "哥布林 獲得 6 護盾",
    "你受到 5 傷害",
]

CARDS = [
    {"name": "斬擊", "cost": 1, "type": "attack", "damage": 6, "playable": True},
    {"name": "連斬", "cost": 1, "type": "attack", "damage": 3, "hits": 3, "playable": True},
    {"name": "背水", "cost": 1, "type": "attack", "damage": 10, "self_damage": 3, "playable": True},
    {"name": "洞察", "cost": 0, "type": "skill", "draw": 2, "playable": True},
    {"name": "盾擊", "cost": 1, "type": "attack", "damage": 5, "block": 5, "playable": False},
]


def draw_main_frame(grid: Grid, floor: int, turn: int) -> None:
    fg = "frame"
    # 外框：上框線（含欄 63 的 ╦）、左右邊、下框線（含欄 63 的 ╩）
    draw_box(grid, layout.FRAME_LEFT, layout.FRAME_TOP, layout.FRAME_WIDTH, layout.FRAME_HEIGHT, fg=fg, style="double")
    grid.set_cell(layout.PANEL_DIVIDER_COL, layout.FRAME_TOP, "╦", fg)

    # 標題列
    draw_text(grid, layout.LEFT_CONTENT_START + 1, layout.HEADER_ROW, f"◆ 地下第 {floor} 層", fg="text")
    turn_label = f"回合 {turn}"
    draw_text(
        grid,
        layout.LEFT_CONTENT_END - text_width(turn_label) + 1,
        layout.HEADER_ROW,
        turn_label,
        fg="text",
    )
    right_title = "─── 戰鬥紀錄 ───"
    title_x = layout.RIGHT_CONTENT_START + max(0, (layout.RIGHT_PANEL_CONTENT_WIDTH - text_width(right_title)) // 2)
    draw_text(grid, title_x, layout.HEADER_ROW, right_title, fg="text")

    # 欄 63 的垂直分隔線，從列 1 到列 16（列 2 與列 17 用專屬轉角字元覆寫）
    draw_vline(grid, layout.PANEL_DIVIDER_COL, layout.HEADER_ROW, layout.LEFT_DIVIDER_ROW - layout.HEADER_ROW + 1, fg)
    draw_vline(grid, layout.PANEL_DIVIDER_COL, layout.LEFT_DIVIDER_ROW, layout.ENEMY_STATUS_ROW - layout.LEFT_DIVIDER_ROW + 1, fg)

    # 列 2：左面板專屬分隔線
    draw_hline(grid, layout.FRAME_LEFT + 1, layout.LEFT_DIVIDER_ROW, layout.PANEL_DIVIDER_COL - 1, fg)
    grid.set_cell(layout.FRAME_LEFT, layout.LEFT_DIVIDER_ROW, "╠", fg)
    grid.set_cell(layout.PANEL_DIVIDER_COL, layout.LEFT_DIVIDER_ROW, "╣", fg)

    # 列 17：全寬分隔線
    draw_hline(grid, layout.FRAME_LEFT + 1, layout.FULL_DIVIDER_ROW, layout.FRAME_RIGHT - layout.FRAME_LEFT - 1, fg)
    grid.set_cell(layout.FRAME_LEFT, layout.FULL_DIVIDER_ROW, "╠", fg)
    grid.set_cell(layout.PANEL_DIVIDER_COL, layout.FULL_DIVIDER_ROW, "╩", fg)
    grid.set_cell(layout.FRAME_RIGHT, layout.FULL_DIVIDER_ROW, "╣", fg)


def draw_enemy(grid: Grid, name: str, hp: int, max_hp: int, block: int, intent_value: int) -> None:
    art_x = layout.LEFT_CONTENT_START + (layout.LEFT_CONTENT_END - layout.LEFT_CONTENT_START + 1 - layout.ENEMY_ART_WIDTH) // 2
    draw_ascii_art(grid, art_x, layout.ENEMY_ART_TOP, GOBLIN_ART, fg="green")

    banner_width = 40
    banner_x = layout.LEFT_CONTENT_START + (layout.LEFT_CONTENT_END - layout.LEFT_CONTENT_START + 1 - banner_width) // 2
    draw_banner(grid, banner_x, layout.ENEMY_BANNER_ROW, banner_width, name)

    hp_x = layout.LEFT_CONTENT_START + 15
    draw_text(grid, hp_x, layout.ENEMY_HP_ROW, "HP ", fg="text")
    draw_hp_bar(grid, hp_x + 3, layout.ENEMY_HP_ROW, 20, hp, max_hp)
    draw_text(grid, hp_x + 24, layout.ENEMY_HP_ROW, f"{hp}/{max_hp}", fg="text")
    if block > 0:
        draw_text(grid, hp_x + 35, layout.ENEMY_HP_ROW, f"盾 {block}", fg="block")

    intent = f">> 準備攻擊 {intent_value} <<"
    intent_x = layout.LEFT_CONTENT_START + (layout.LEFT_CONTENT_END - layout.LEFT_CONTENT_START + 1 - text_width(intent)) // 2
    draw_text(grid, intent_x, layout.ENEMY_INTENT_ROW, intent, fg="attack")


def draw_battle_log(grid: Grid, entries: list[str]) -> None:
    wrapped: list[str] = []
    for entry in entries:
        wrapped.extend(wrap_text(f"› {entry}", layout.RIGHT_PANEL_CONTENT_WIDTH))
    visible = wrapped[-(layout.RIGHT_PANEL_BOTTOM - layout.RIGHT_PANEL_TOP) :]
    start_row = layout.RIGHT_PANEL_BOTTOM - len(visible)
    for i, line in enumerate(visible):
        draw_text(grid, layout.RIGHT_CONTENT_START + 1, start_row + i, line, fg="text")


def draw_player(grid: Grid, hp: int, max_hp: int, block: int, energy: int, max_energy: int, draw_pile: int, discard: int) -> None:
    x = layout.LEFT_CONTENT_START + 1
    x = draw_text(grid, x, layout.PLAYER_STATUS_ROW, "[ 冒險者 ]  HP ", fg="text")
    draw_hp_bar(grid, x, layout.PLAYER_STATUS_ROW, 20, hp, max_hp)
    x = draw_text(grid, x + 21, layout.PLAYER_STATUS_ROW, f"{hp}/{max_hp}", fg="text")
    x = draw_text(grid, x + 4, layout.PLAYER_STATUS_ROW, f"盾 {block}", fg="block")
    x = draw_text(grid, x + 4, layout.PLAYER_STATUS_ROW, "能量 ", fg="text")
    x = draw_energy_pips(grid, x, layout.PLAYER_STATUS_ROW, energy, max_energy)
    draw_text(grid, x + 4, layout.PLAYER_STATUS_ROW, f"牌堆 {draw_pile} / 棄牌 {discard}", fg="text")


def draw_hand(grid: Grid, cards: list[dict]) -> None:
    for i, card in enumerate(cards[: layout.CARD_MAX_COUNT]):
        description = resolve_description(card)
        draw_card(
            grid,
            layout.card_slot_x(i),
            layout.HAND_ROW_TOP,
            name=card["name"],
            cost=card["cost"],
            card_type=card["type"],
            description=description,
            playable=card["playable"],
        )


def draw_hint_bar(grid: Grid) -> None:
    hint = "[1-7] 出牌        [E] 結束回合        滑鼠停留：查看詳細        [F5] 重新載入"
    hint_x = (layout.SCREEN_WIDTH - text_width(hint)) // 2
    draw_text(grid, hint_x, layout.HINT_ROW, hint, fg="dim")


def build_demo_grid() -> Grid:
    grid = Grid()
    draw_main_frame(grid, floor=3, turn=4)
    draw_enemy(grid, name="哥布林", hp=24, max_hp=35, block=6, intent_value=8)
    draw_battle_log(grid, BATTLE_LOG)
    draw_player(grid, hp=42, max_hp=50, block=5, energy=1, max_energy=3, draw_pile=7, discard=3)
    draw_hand(grid, CARDS)
    draw_hint_bar(grid)
    return grid


def main() -> None:
    grid = build_demo_grid()
    renderer = TerminalRenderer()
    renderer.present(grid)


if __name__ == "__main__":
    main()
