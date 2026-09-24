"""休息畫面：回復 30% 最大血量，按 Enter 或按鈕繼續前進。"""
from __future__ import annotations

from .. import layout
from ..actions import Action, ClickButton, Confirm, HoverButton
from ..draw import draw_button, draw_text, text_width
from ..grid import Grid
from ..run import Run
from .scene import Scene

BUTTON_NAME = "rest_continue"


class RestScene(Scene):
    def __init__(self, run: Run, *, supports_mouse: bool = True) -> None:
        self.run = run
        self.healed_amount = run.rest_heal()
        self.supports_mouse = supports_mouse
        self.finished = False
        self.continue_hovered = False

    def handle(self, actions: list[Action]) -> None:
        for action in actions:
            if isinstance(action, Confirm):
                self.finished = True
                return
            if isinstance(action, ClickButton) and action.name == BUTTON_NAME:
                self.finished = True
                return
            if isinstance(action, HoverButton) and action.name == BUTTON_NAME:
                self.continue_hovered = action.active

    def update(self, dt: float) -> None:
        pass

    def draw(self, grid: Grid) -> None:
        center_y = layout.SCREEN_HEIGHT // 2
        title = "◆ 休息點 ◆"
        message = f"回復了 {self.healed_amount} 點生命（{self.run.hp} / {self.run.max_hp}）"

        self._draw_centered(grid, center_y - 2, title, fg="highlight")
        self._draw_centered(grid, center_y, message, fg="status_good" if self.healed_amount else "text")

        if self.supports_mouse:
            draw_button(
                grid,
                layout.REST_CONTINUE_BUTTON_X,
                layout.REST_CONTINUE_BUTTON_Y,
                layout.MENU_BUTTON_WIDTH,
                layout.MENU_BUTTON_HEIGHT,
                "繼續前進",
                key_hint="[Enter]",
                hovered=self.continue_hovered,
            )
        else:
            self._draw_centered(grid, layout.REST_CONTINUE_BUTTON_Y, "按 Enter 繼續前進", fg="dim")

    @staticmethod
    def _draw_centered(grid: Grid, y: int, text: str, fg: str) -> None:
        x = max(0, (layout.SCREEN_WIDTH - text_width(text)) // 2)
        draw_text(grid, x, y, text, fg=fg)
