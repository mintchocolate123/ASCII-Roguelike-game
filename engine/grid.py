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
    fg: str = "white"
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
                cell.fg = "white"
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
        fg: str = "white",
        bg: str | None = None,
        wide_tail: bool = False,
    ) -> None:
        """寫入單一格子；超出畫面範圍直接裁切，不拋出例外。"""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return
        cell = self._cells[y][x]
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
