"""休息畫面：回復 30% 最大血量，按 Enter 繼續前進。"""
from __future__ import annotations

from .. import layout
from ..actions import Action, Confirm
from ..draw import draw_text, text_width
from ..grid import Grid
from ..run import Run
from .scene import Scene


class RestScene(Scene):
    def __init__(self, run: Run) -> None:
        self.run = run
        self.healed_amount = run.rest_heal()
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
        title = "◆ 休息點 ◆"
        message = f"回復了 {self.healed_amount} 點生命（{self.run.hp} / {self.run.max_hp}）"
        prompt = "按 Enter 繼續前進"

        self._draw_centered(grid, center_y - 2, title, fg="highlight")
        self._draw_centered(grid, center_y, message, fg="status_good" if self.healed_amount else "text")
        self._draw_centered(grid, center_y + 3, prompt, fg="dim")

    @staticmethod
    def _draw_centered(grid: Grid, y: int, text: str, fg: str) -> None:
        x = max(0, (layout.SCREEN_WIDTH - text_width(text)) // 2)
        draw_text(grid, x, y, text, fg=fg)
