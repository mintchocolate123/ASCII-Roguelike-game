"""Scene 基底類別：battle、reward、rest...等畫面共用的介面。"""
from __future__ import annotations

from ..actions import Action
from ..grid import Grid


class Scene:
    def handle(self, actions: list[Action]) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, grid: Grid) -> None:
        pass
