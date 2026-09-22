"""mod 資料的 Pydantic 模型。驗證一律在引擎端執行，不依賴學生程式碼做檢查。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from engine.draw import text_width

ID_PATTERN = r"^[a-z][a-z0-9_]*$"


class ModManifest(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str
    version: str
    author: str = "unknown"
    depends: list[str] = []


class CardDef(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str
    type: Literal["attack", "skill", "power"]
    cost: int = Field(ge=0, le=5)
    description: Optional[str] = None  # 可用 {damage} 等佔位符；省略時自動產生
    count: int = Field(default=1, ge=0)  # 放入初始牌組的張數，0 表示只出現在獎勵池
    in_reward_pool: bool = True
    damage: Optional[int] = Field(default=None, ge=0)
    hits: Optional[int] = Field(default=None, ge=1)
    block: Optional[int] = Field(default=None, ge=0)
    heal: Optional[int] = Field(default=None, ge=0)
    draw: Optional[int] = Field(default=None, ge=0)
    energy: Optional[int] = Field(default=None, ge=0)
    self_damage: Optional[int] = Field(default=None, ge=0)
    effect: Optional[str] = None  # 第二階段：註冊表中的完整 id
    overrides: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_fits_card(cls, v: str) -> str:
        if text_width(v) > 10:
            raise ValueError("卡名太長：顯示寬度最多 10 格（5 個中文字）")
        return v


class EnemyAction(BaseModel):
    type: Literal["attack", "block"]
    value: int = Field(ge=0)


class EnemyDef(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str
    tier: Literal["normal", "elite", "boss"]
    hp: int = Field(ge=1)
    art: str
    color: str = "white"
    actions: list[EnemyAction] = Field(min_length=1)
    overrides: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_fits_band(cls, v: str) -> str:
        if text_width(v) > 16:
            raise ValueError("敵人名稱太長：顯示寬度最多 16 格（8 個中文字）")
        return v


class RunStage(BaseModel):
    type: Literal["battle", "rest"]
    tier: Optional[Literal["normal", "elite", "boss"]] = None
