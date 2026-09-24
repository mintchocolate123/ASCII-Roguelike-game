"""載入畫面：顯示 mod 載入報告。有致命錯誤時只顯示報告，不能開始遊戲。"""
from __future__ import annotations

from .. import layout
from ..actions import Action, Confirm
from ..draw import draw_box, draw_text, text_width, wrap_text
from ..grid import Grid
from ..mod.report import LoadReport
from .scene import Scene

CONTENT_WIDTH = layout.SCREEN_WIDTH - 8


class LoadingScene(Scene):
    def __init__(self, report: LoadReport) -> None:
        self.report = report
        self.finished = False

    def handle(self, actions: list[Action]) -> None:
        if self.report.has_fatal:
            return  # 卡在這一頁，不能開始遊戲
        for action in actions:
            if isinstance(action, Confirm):
                self.finished = True
                return

    def update(self, dt: float) -> None:
        pass

    def draw(self, grid: Grid) -> None:
        title = "載入報告" if not self.report.has_fatal else "載入失敗"
        title_color = "hp" if self.report.has_fatal else "frame"
        x, y, w = 4, 1, layout.SCREEN_WIDTH - 8
        h = layout.SCREEN_HEIGHT - 4
        draw_box(grid, x, y, w, h, fg=title_color, style="double", title=title)

        lines: list[str] = []
        for line in self.report.format_text().split("\n"):
            lines.extend(wrap_text(line, CONTENT_WIDTH) or [""])
        max_rows = h - 4
        for row, line in enumerate(lines[:max_rows]):
            draw_text(grid, x + 2, y + 2 + row, line, fg="text")

        if self.report.has_fatal:
            prompt = "載入失敗，無法開始遊戲。請修正 mods/ 底下的內容後重新執行。"
        else:
            prompt = "按 Enter 繼續"
        prompt_x = x + max(1, (w - text_width(prompt)) // 2)
        draw_text(grid, prompt_x, y + h - 2, prompt, fg="dim")
