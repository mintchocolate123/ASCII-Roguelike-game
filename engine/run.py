"""一局遊戲的進度。目前只提供單場戰鬥需要的部分：組出初始牌組、選擇對手；
戰鬥之間保存玩家狀態、reward/rest 留到後面的階段再擴充。
"""
from __future__ import annotations

import random


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
