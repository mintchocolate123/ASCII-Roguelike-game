"""結算畫面：顯示通關或戰敗，可以重新開始或離開。"""
from __future__ import annotations

from .. import layout
from ..actions import Action, Back, Confirm
from ..draw import draw_text, text_width
from ..grid import Grid
from .scene import Scene


class ResultScene(Scene):
    def __init__(self, victory: bool, message: str | None = None) -> None:
        self.victory = victory
        self.message = message
        self.restart_requested = False
        self.quit_requested = False

    def handle(self, actions: list[Action]) -> None:
        for action in actions:
            if isinstance(action, Confirm):
                self.restart_requested = True
                return
            if isinstance(action, Back):
                self.quit_requested = True
                return

    def update(self, dt: float) -> None:
        pass

    def draw(self, grid: Grid) -> None:
        center_y = layout.SCREEN_HEIGHT // 2
        if self.victory:
            title, title_fg = "◆ 通關了！ ◆", "status_good"
        else:
            title, title_fg = "◆ 戰敗 ◆", "hp"

        self._draw_centered(grid, center_y - 3, title, fg=title_fg)
        if self.message:
            row = center_y - 1
            for line in self.message.split("\n")[:4]:
                self._draw_centered(grid, row, line, fg="text")
                row += 1
        self._draw_centered(grid, center_y + 3, "按 Enter 重新開始    按 Esc 離開遊戲", fg="dim")

    @staticmethod
    def _draw_centered(grid: Grid, y: int, text: str, fg: str) -> None:
        x = max(0, (layout.SCREEN_WIDTH - text_width(text)) // 2)
        draw_text(grid, x, y, text, fg=fg)
