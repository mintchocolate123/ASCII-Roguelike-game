"""一局遊戲的進度：依 run.json 推進關卡，在戰鬥之間保存玩家血量與牌組，
每場戰鬥開始時重建抽牌堆（由 rules.py 的 create_player 負責）。
"""
from __future__ import annotations

import random

REST_HEAL_RATIO = 0.3


class Run:
    """一局遊戲的進度：目前在第幾關、牌組、血量。

    hp/max_hp 一開始是 None，因為到底玩家滿血是多少由 rules.py 決定，不是引擎決定；
    第一次呼叫 create_player() 之後才知道，之後每場戰鬥開始前再把保存的 hp 蓋回去。
    """

    def __init__(self, stages: list[dict], deck: list[dict]) -> None:
        self.stages = stages
        self.stage_index = 0
        self.deck = deck
        self.hp: int | None = None
        self.max_hp: int | None = None

    @property
    def current_stage(self) -> dict | None:
        if 0 <= self.stage_index < len(self.stages):
            return self.stages[self.stage_index]
        return None

    @property
    def is_finished(self) -> bool:
        return self.stage_index >= len(self.stages)

    @property
    def floor(self) -> int:
        """給畫面顯示用的樓層數，從 1 開始。"""
        return self.stage_index + 1

    def advance(self) -> None:
        self.stage_index += 1

    def record_hp(self, hp: int, max_hp: int) -> None:
        self.hp = hp
        self.max_hp = max_hp

    def rest_heal(self) -> int:
        """回復 30% 最大血量，回傳實際回復的量。"""
        if self.max_hp is None or self.hp is None:
            return 0
        healed_target = min(self.max_hp, self.hp + int(self.max_hp * REST_HEAL_RATIO))
        healed_amount = healed_target - self.hp
        self.hp = healed_target
        return healed_amount


def build_starting_deck(cards: dict[str, dict]) -> list[dict]:
    """依每張卡的 count 展開成初始牌組的卡片清單。"""
    deck: list[dict] = []
    for card in cards.values():
        deck.extend(dict(card) for _ in range(card.get("count", 0)))
    return deck


def pick_enemy(enemies: dict[str, dict], *, full_id: str | None = None, tier: str | None = None) -> dict:
    """指定 full_id 就直接取用；否則從符合 tier 的敵人中隨機選一個。"""
    if full_id is not None:
        if full_id not in enemies:
            raise KeyError(f"找不到敵人「{full_id}」。")
        return dict(enemies[full_id])
    candidates = [e for e in enemies.values() if tier is None or e["tier"] == tier]
    if not candidates:
        raise ValueError(f"沒有 tier 為「{tier}」的敵人可用。" if tier else "沒有可用的敵人。")
    return dict(random.choice(candidates))
