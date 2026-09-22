"""字元格緩衝區：畫面由 Cell 組成的二維陣列，繪圖層只寫入這裡。"""
from __future__ import annotations

from dataclasses import dataclass

WIDTH = 96
HEIGHT = 32
CELL_PIXEL_WIDTH = 10
CELL_PIXEL_HEIGHT = 20


@dataclass
class Cell:
    char: str = " "
    fg: str = "text"
    bg: str | None = None
    wide_tail: bool = False  # 寬字元的第二格，渲染時要略過


class Grid:
    def __init__(self, width: int = WIDTH, height: int = HEIGHT) -> None:
        self.width = width
        self.height = height
        self.dirty = True
        self._cells: list[list[Cell]] = [
            [Cell() for _ in range(width)] for _ in range(height)
        ]

    def clear(self) -> None:
        for row in self._cells:
            for cell in row:
                cell.char = " "
                cell.fg = "text"
                cell.bg = None
                cell.wide_tail = False
        self.dirty = True

    def get(self, x: int, y: int) -> Cell:
        return self._cells[y][x]

    def set_cell(
        self,
        x: int,
        y: int,
        char: str,
        fg: str = "text",
        bg: str | None = None,
        wide_tail: bool = False,
    ) -> None:
        """寫入單一格子；超出畫面範圍直接裁切，不拋出例外。

        覆寫寬字元的前半格或後半格時，另一半會被清成空白，避免留下孤兒半格。
        """
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return
        row = self._cells[y]
        if not wide_tail:
            old = row[x]
            if old.wide_tail and x - 1 >= 0:
                head = row[x - 1]
                head.char = " "
                head.fg = "text"
                head.bg = None
                head.wide_tail = False
            elif x + 1 < self.width and row[x + 1].wide_tail:
                tail = row[x + 1]
                tail.char = " "
                tail.fg = "text"
                tail.bg = None
                tail.wide_tail = False
        cell = row[x]
        cell.char = char
        cell.fg = fg
        cell.bg = bg
        cell.wide_tail = wide_tail
        self.dirty = True


def plain_lines(grid: Grid) -> list[str]:
    """把 grid 轉成不含顏色的純文字，每行略過 wide_tail 格。測試對齊用。"""
    lines = []
    for y in range(grid.height):
        chars = [
            (cell.char if cell.char else " ")
            for x in range(grid.width)
            for cell in [grid.get(x, y)]
            if not cell.wide_tail
        ]
        lines.append("".join(chars))
    return lines
