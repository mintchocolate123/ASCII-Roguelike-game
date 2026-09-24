"""結算畫面：顯示通關或戰敗，可以重新開始或離開。"""
from __future__ import annotations

from .. import layout
from ..actions import Action, Back, ClickButton, Confirm, HoverButton
from ..draw import draw_button, draw_text, text_width
from ..grid import Grid
from .scene import Scene

RESTART_BUTTON_NAME = "result_restart"
QUIT_BUTTON_NAME = "result_quit"


class ResultScene(Scene):
    def __init__(self, victory: bool, message: str | None = None, *, supports_mouse: bool = True) -> None:
        self.victory = victory
        self.message = message
        self.supports_mouse = supports_mouse
        self.restart_requested = False
        self.quit_requested = False
        self.restart_hovered = False
        self.quit_hovered = False

    def handle(self, actions: list[Action]) -> None:
        for action in actions:
            if isinstance(action, Confirm):
                self.restart_requested = True
                return
            if isinstance(action, Back):
                self.quit_requested = True
                return
            if isinstance(action, ClickButton):
                if action.name == RESTART_BUTTON_NAME:
                    self.restart_requested = True
                    return
                if action.name == QUIT_BUTTON_NAME:
                    self.quit_requested = True
                    return
            if isinstance(action, HoverButton):
                if action.name == RESTART_BUTTON_NAME:
                    self.restart_hovered = action.active
                elif action.name == QUIT_BUTTON_NAME:
                    self.quit_hovered = action.active

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

        if self.supports_mouse:
            draw_button(
                grid,
                layout.RESULT_RESTART_BUTTON_X,
                layout.RESULT_BUTTON_ROW,
                layout.MENU_BUTTON_WIDTH,
                layout.MENU_BUTTON_HEIGHT,
                "重新開始",
                key_hint="[Enter]",
                hovered=self.restart_hovered,
            )
            draw_button(
                grid,
                layout.RESULT_QUIT_BUTTON_X,
                layout.RESULT_BUTTON_ROW,
                layout.MENU_BUTTON_WIDTH,
                layout.MENU_BUTTON_HEIGHT,
                "離開遊戲",
                key_hint="[Esc]",
                hovered=self.quit_hovered,
            )
        else:
            self._draw_centered(grid, layout.RESULT_BUTTON_ROW, "按 Enter 重新開始    按 Esc 離開遊戲", fg="dim")

    @staticmethod
    def _draw_centered(grid: Grid, y: int, text: str, fg: str) -> None:
        x = max(0, (layout.SCREEN_WIDTH - text_width(text)) // 2)
        draw_text(grid, x, y, text, fg=fg)
