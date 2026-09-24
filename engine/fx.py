"""視覺效果佇列：效果由引擎比較 bridge 呼叫前後的 view 差異自動產生，
rules.py 不需要呼叫任何 fx API。

- 敵人 HP 下降：敵人圖閃紅並左右抖動 1 格（ENEMY_HIT）
- 玩家 HP 下降：玩家狀態列閃紅（PLAYER_HIT）
- 護盾增加：護盾數字閃藍色（PLAYER_BLOCK_GAIN / ENEMY_BLOCK_GAIN）

效果播放期間 battle scene 不接受輸入。終端機版（supports_animation() 回傳 False）
直接略過，不會產生任何效果。
"""
from __future__ import annotations

from dataclasses import dataclass

ENEMY_HIT = "enemy_hit"
PLAYER_HIT = "player_hit"
PLAYER_BLOCK_GAIN = "player_block_gain"
ENEMY_BLOCK_GAIN = "enemy_block_gain"

DEFAULT_DURATION = 0.4
FLASH_INTERVAL = 0.08  # 閃爍間隔：每經過這麼多秒切換一次顏色
SHAKE_OFFSETS = (-1, 1, -1, 1, 0)  # 敵人抖動的左右位移序列，最後回到 0


@dataclass
class _Effect:
    kind: str
    duration: float
    elapsed: float = 0.0

    @property
    def active(self) -> bool:
        return self.elapsed < self.duration


class FxQueue:
    """目前正在播放的效果，依種類（kind）區分，可以同時播好幾種效果。"""

    def __init__(self) -> None:
        self._effects: dict[str, _Effect] = {}

    def trigger(self, kind: str, duration: float = DEFAULT_DURATION) -> None:
        self._effects[kind] = _Effect(kind, duration)

    def update(self, dt: float) -> None:
        for kind in list(self._effects):
            effect = self._effects[kind]
            effect.elapsed += dt
            if not effect.active:
                del self._effects[kind]

    @property
    def is_playing(self) -> bool:
        return bool(self._effects)

    def is_active(self, kind: str) -> bool:
        return kind in self._effects

    def flash_on(self, kind: str) -> bool:
        """這一刻該不該顯示強調色，用簡單的時間切割做出「閃」的效果。"""
        effect = self._effects.get(kind)
        if effect is None:
            return False
        return int(effect.elapsed / FLASH_INTERVAL) % 2 == 0

    def shake_offset(self) -> int:
        """敵人圖目前該往左或右偏移幾格；沒有 ENEMY_HIT 效果時回傳 0。"""
        effect = self._effects.get(ENEMY_HIT)
        if effect is None:
            return 0
        step_duration = effect.duration / len(SHAKE_OFFSETS)
        index = min(int(effect.elapsed / step_duration), len(SHAKE_OFFSETS) - 1)
        return SHAKE_OFFSETS[index]

    def clear(self) -> None:
        self._effects.clear()


def diff_triggers(before_player: dict, after_player: dict, before_enemy: dict, after_enemy: dict) -> list[str]:
    """比較 bridge 呼叫前後的 player_view / enemy_view，回傳這次應該觸發的效果種類。"""
    triggers: list[str] = []
    if after_enemy.get("hp", 0) < before_enemy.get("hp", 0):
        triggers.append(ENEMY_HIT)
    if after_player.get("hp", 0) < before_player.get("hp", 0):
        triggers.append(PLAYER_HIT)
    if after_player.get("block", 0) > before_player.get("block", 0):
        triggers.append(PLAYER_BLOCK_GAIN)
    if after_enemy.get("block", 0) > before_enemy.get("block", 0):
        triggers.append(ENEMY_BLOCK_GAIN)
    return triggers
