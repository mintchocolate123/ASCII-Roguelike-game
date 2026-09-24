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


@dataclass(frozen=True)
class ClickButton:
    """點擊一個具名按鈕（title/loading/rest/result 用的「開始遊戲」「繼續」「重新開始」
    「離開遊戲」等）。scene 只處理自己認得的名稱，收到別的畫面的按鈕名稱就直接忽略。

    這樣即使兩個畫面的按鈕剛好落在同一個座標（不同畫面不會同時顯示，但 renderer 不知道
    現在是哪個 scene），也不會誤觸不相干的動作——renderer 只負責照座標回報名稱，
    要不要理會由 scene 自己判斷。"""

    name: str


@dataclass(frozen=True)
class HoverButton:
    """滑鼠是否停留在某個具名按鈕上方，用來決定要不要顯示成 highlight 色。
    跟 ClickButton 一樣用名稱區分，scene 只理會自己的按鈕名稱。"""

    name: str
    active: bool


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
    ClickButton,
    HoverButton,
]
