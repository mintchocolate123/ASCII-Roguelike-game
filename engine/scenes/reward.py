"""獎勵畫面：戰鬥獲勝後從獎勵池抽三張卡，可選一張或跳過。沿用手牌的卡牌樣式。"""
from __future__ import annotations

import random

from .. import layout
from ..actions import Action, Back, Choose, ClickCard, HoverSkip, PlayCard, Skip
from ..draw import draw_box, draw_card, draw_text, text_width
from ..grid import Grid
from ..run import Run
from .scene import Scene


class RewardScene(Scene):
    def __init__(self, run: Run, reward_pool: list[dict], *, supports_mouse: bool = True) -> None:
        self.run = run
        self.options = random.sample(reward_pool, k=min(layout.REWARD_CARD_COUNT, len(reward_pool)))
        self.supports_mouse = supports_mouse
        self.finished = False
        self.skipped = False
        self.chosen_index: int | None = None
        self.selected_index: int | None = None  # 滑鼠兩段式點擊：第一下選取，第二下才確定
        self.skip_hovered = False

    def handle(self, actions: list[Action]) -> None:
        for action in actions:
            self._handle_one(action)

    def _handle_one(self, action: Action) -> None:
        if isinstance(action, HoverSkip):
            self.skip_hovered = action.active
            return
        if isinstance(action, Skip):
            # 跳過按鈕：不管有沒有選取中的卡，點下去一律直接跳過。
            self.selected_index = None
            self.skipped = True
            self.finished = True
            return
        if isinstance(action, ClickCard):
            self._click_card(action.index)
            return
        if isinstance(action, (PlayCard, Choose)) and 0 <= action.index < len(self.options):
            self._choose(action.index)
            return
        if isinstance(action, Back):
            if self.selected_index is not None:
                # 點空白處或 Esc 取消選取；有選取中的卡時，Esc 只取消選取，不會直接跳過。
                self.selected_index = None
                return
            self.skipped = True
            self.finished = True

    def _click_card(self, index: int | None) -> None:
        if index is None or not (0 <= index < len(self.options)):
            self.selected_index = None
            return
        if self.selected_index == index:
            self.selected_index = None
            self._choose(index)
            return
        self.selected_index = index

    def _choose(self, index: int) -> None:
        self.chosen_index = index
        self.run.deck.append(dict(self.options[index]))
        self.finished = True

    def update(self, dt: float) -> None:
        pass

    def draw(self, grid: Grid) -> None:
        title = "戰鬥勝利！選擇一張卡加入牌組"
        title_x = max(0, (layout.SCREEN_WIDTH - text_width(title)) // 2)
        draw_text(grid, title_x, layout.REWARD_TITLE_ROW, title, fg="highlight")

        for i, card in enumerate(self.options):
            selected = i == self.selected_index
            x = layout.reward_card_x(i)
            y = layout.REWARD_ROW_TOP + (layout.SELECTED_CARD_ROW_OFFSET if selected else 0)
            draw_card(
                grid,
                x,
                y,
                name=card.get("name", "?"),
                cost=card.get("cost", 0),
                card_type=card.get("type", "attack"),
                description=card.get("description", ""),
                playable=True,
                highlighted=selected,
            )

        self._draw_skip_button(grid)

        if not self.supports_mouse:
            hint = "[1-3] 選擇這張卡        [B] 跳過"
            hint_x = max(0, (layout.SCREEN_WIDTH - text_width(hint)) // 2)
            draw_text(grid, hint_x, layout.REWARD_HINT_ROW, hint, fg="dim")

    def _draw_skip_button(self, grid: Grid) -> None:
        x, y = layout.REWARD_SKIP_BUTTON_X, layout.REWARD_SKIP_BUTTON_Y
        w, h = layout.REWARD_SKIP_BUTTON_WIDTH, layout.REWARD_SKIP_BUTTON_HEIGHT
        fg = "highlight" if self.skip_hovered else "frame"
        draw_box(grid, x, y, w, h, fg=fg, style="double")
        label = "跳過"
        draw_text(grid, x + max(1, (w - text_width(label)) // 2), y + h // 2 - 1, label, fg=fg)
        key_hint = "[B]"
        draw_text(grid, x + max(1, (w - text_width(key_hint)) // 2), y + h // 2 + 1, key_hint, fg=fg)
