"""標題畫面：按 Enter 開始新的一局遊戲。"""
from __future__ import annotations

from .. import layout
from ..actions import Action, ClickButton, Confirm, HoverButton
from ..draw import draw_button, draw_text, text_width
from ..grid import Grid
from .scene import Scene

TITLE = "ASCII 卡牌遊戲"
SUBTITLE = "簡化版殺戮尖塔"
BUTTON_NAME = "title_start"


class TitleScene(Scene):
    def __init__(self, *, supports_mouse: bool = True) -> None:
        self.supports_mouse = supports_mouse
        self.finished = False
        self.start_hovered = False

    def handle(self, actions: list[Action]) -> None:
        for action in actions:
            if isinstance(action, Confirm):
                self.finished = True
                return
            if isinstance(action, ClickButton) and action.name == BUTTON_NAME:
                self.finished = True
                return
            if isinstance(action, HoverButton) and action.name == BUTTON_NAME:
                self.start_hovered = action.active

    def update(self, dt: float) -> None:
        pass

    def draw(self, grid: Grid) -> None:
        center_y = layout.SCREEN_HEIGHT // 2
        self._draw_centered(grid, center_y - 2, TITLE, fg="highlight")
        self._draw_centered(grid, center_y, SUBTITLE, fg="text")

        if self.supports_mouse:
            draw_button(
                grid,
                layout.TITLE_START_BUTTON_X,
                layout.TITLE_START_BUTTON_Y,
                layout.MENU_BUTTON_WIDTH,
                layout.MENU_BUTTON_HEIGHT,
                "開始遊戲",
                key_hint="[Enter]",
                hovered=self.start_hovered,
            )
        else:
            self._draw_centered(grid, layout.TITLE_START_BUTTON_Y, "按 Enter 開始遊戲", fg="dim")

    @staticmethod
    def _draw_centered(grid: Grid, y: int, text: str, fg: str) -> None:
        x = max(0, (layout.SCREEN_WIDTH - text_width(text)) // 2)
        draw_text(grid, x, y, text, fg=fg)
