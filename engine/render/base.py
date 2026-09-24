"""Renderer 介面：畫面呈現與輸入解析的抽象界線，繪圖層透過這層與裝置隔離。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..actions import Action
from ..grid import Grid


class Renderer(ABC):
    @abstractmethod
    def present(self, grid: Grid) -> None:
        ...

    @abstractmethod
    def poll_actions(self) -> list[Action]:
        ...

    @abstractmethod
    def supports_animation(self) -> bool:
        ...

    @abstractmethod
    def supports_mouse(self) -> bool:
        ...

    def close(self) -> None:
        """釋放渲染器持有的資源（例如關閉視窗）。預設不需要做任何事。"""
        pass
