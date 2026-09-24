"""獎勵畫面：戰鬥獲勝後從獎勵池抽三張卡，可選一張或跳過。沿用手牌的卡牌樣式。"""
from __future__ import annotations

import random

from .. import layout
from ..actions import Action, Back, Choose, PlayCard
from ..draw import draw_card, draw_text, text_width
from ..grid import Grid
from ..run import Run
from .scene import Scene

CARD_COUNT = 3
CARD_GAP = 3
TOP_ROW = 12


class RewardScene(Scene):
    def __init__(self, run: Run, reward_pool: list[dict]) -> None:
        self.run = run
        self.options = random.sample(reward_pool, k=min(CARD_COUNT, len(reward_pool)))
        self.finished = False
        self.skipped = False
        self.chosen_index: int | None = None

    def handle(self, actions: list[Action]) -> None:
        for action in actions:
            if isinstance(action, (PlayCard, Choose)) and 0 <= action.index < len(self.options):
                self._choose(action.index)
                return
            if isinstance(action, Back):
                self.skipped = True
                self.finished = True
                return

    def _choose(self, index: int) -> None:
        self.chosen_index = index
        self.run.deck.append(dict(self.options[index]))
        self.finished = True

    def update(self, dt: float) -> None:
        pass

    def draw(self, grid: Grid) -> None:
        title = "戰鬥勝利！選擇一張卡加入牌組"
        title_x = max(0, (layout.SCREEN_WIDTH - text_width(title)) // 2)
        draw_text(grid, title_x, TOP_ROW - 3, title, fg="highlight")

        total_width = len(self.options) * layout.CARD_WIDTH + max(0, len(self.options) - 1) * CARD_GAP
        start_x = max(0, (layout.SCREEN_WIDTH - total_width) // 2)
        for i, card in enumerate(self.options):
            x = start_x + i * (layout.CARD_WIDTH + CARD_GAP)
            draw_card(
                grid,
                x,
                TOP_ROW,
                name=card.get("name", "?"),
                cost=card.get("cost", 0),
                card_type=card.get("type", "attack"),
                description=card.get("description", ""),
                playable=True,
            )

        hint = "[1-3] 選擇這張卡        [B] 跳過"
        hint_x = max(0, (layout.SCREEN_WIDTH - text_width(hint)) // 2)
        draw_text(grid, hint_x, TOP_ROW + layout.CARD_HEIGHT + 2, hint, fg="dim")
