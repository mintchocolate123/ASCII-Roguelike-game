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
    """滑鼠點擊卡牌區域（點到卡牌是索引，點到空白處是 None）。手牌、獎勵畫面都會用到。
    跟 PlayCard 不同：scene 會用兩段式（先選取、再點一次才確定）處理，
    數字鍵仍然走 PlayCard/Choose，一次就直接生效。"""

    index: int | None


@dataclass(frozen=True)
class HoverEndTurn:
    """滑鼠是否正停在結束回合按鈕上方，用來決定按鈕要不要顯示成 highlight 色。"""

    active: bool


@dataclass(frozen=True)
class HoverSkip:
    """滑鼠是否正停在獎勵畫面的跳過按鈕上方，用來決定按鈕要不要顯示成 highlight 色。"""

    active: bool


@dataclass(frozen=True)
class Skip:
    """點擊獎勵畫面的跳過按鈕：一律直接跳過，不管目前有沒有選取中的卡。"""

    pass


Action = Union[
    PlayCard,
    EndTurn,
    Choose,
    Confirm,
    Back,
    Reload,
    Quit,
    Inspect,
    ClickCard,
    HoverEndTurn,
    HoverSkip,
    Skip,
]
