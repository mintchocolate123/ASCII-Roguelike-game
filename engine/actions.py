"""抽象輸入動作：渲染器把輸入轉成這些型別，scene 不認識輸入裝置細節。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class PlayCard:
    index: int


@dataclass(frozen=True)
class EndTurn:
    pass


@dataclass(frozen=True)
class Choose:
    index: int


@dataclass(frozen=True)
class Confirm:
    pass


@dataclass(frozen=True)
class Back:
    pass


@dataclass(frozen=True)
class Reload:
    pass


@dataclass(frozen=True)
class Quit:
    pass


@dataclass(frozen=True)
class Inspect:
    index: int | None  # None 表示結束檢視


@dataclass(frozen=True)
class ClickCard:
    """滑鼠點擊手牌區域（點到卡牌是索引，點到空白處是 None）。
    跟 PlayCard 不同：scene 會用兩段式（先選取、再點一次才出牌）處理，
    數字鍵仍然走 PlayCard，一次就直接出牌。"""

    index: int | None


@dataclass(frozen=True)
class HoverEndTurn:
    """滑鼠是否正停在結束回合按鈕上方，用來決定按鈕要不要顯示成 highlight 色。"""

    active: bool


Action = Union[
    PlayCard, EndTurn, Choose, Confirm, Back, Reload, Quit, Inspect, ClickCard, HoverEndTurn
]
