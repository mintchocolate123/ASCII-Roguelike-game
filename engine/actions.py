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


Action = Union[PlayCard, EndTurn, Choose, Confirm, Back, Reload, Quit]
