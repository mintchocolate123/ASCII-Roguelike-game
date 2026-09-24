"""標題畫面：按 Enter 開始新的一局遊戲。"""
from __future__ import annotations

from .. import layout
from ..actions import Action, Confirm
from ..draw import draw_text, text_width
from ..grid import Grid
from .scene import Scene

TITLE = "ASCII 卡牌遊戲"
SUBTITLE = "簡化版殺戮尖塔"
PROMPT = "按 Enter 開始遊戲"


class TitleScene(Scene):
    def __init__(self) -> None:
        self.finished = False

    def handle(self, actions: list[Action]) -> None:
        for action in actions:
            if isinstance(action, Confirm):
                self.finished = True
                return

    def update(self, dt: float) -> None:
        pass

    def draw(self, grid: Grid) -> None:
        center_y = layout.SCREEN_HEIGHT // 2
        self._draw_centered(grid, center_y - 2, TITLE, fg="highlight")
        self._draw_centered(grid, center_y, SUBTITLE, fg="text")
        self._draw_centered(grid, center_y + 3, PROMPT, fg="dim")

    @staticmethod
    def _draw_centered(grid: Grid, y: int, text: str, fg: str) -> None:
        x = max(0, (layout.SCREEN_WIDTH - text_width(text)) // 2)
        draw_text(grid, x, y, text, fg=fg)
