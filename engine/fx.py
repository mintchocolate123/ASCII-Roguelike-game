"""視覺效果佇列：效果由引擎比較 bridge 呼叫前後的 view 差異自動產生，
rules.py 不需要呼叫任何 fx API。

- 敵人 HP 下降：敵人圖閃紅並左右抖動 1 格（ENEMY_HIT）
- 玩家 HP 下降：玩家狀態列閃紅（PLAYER_HIT）
- 護盾增加：護盾數字閃藍色（PLAYER_BLOCK_GAIN / ENEMY_BLOCK_GAIN）
- 傷害數字彈出：受擊位置浮出數字往上飄後淡出，扣血用 hp 色、被護盾吸收的量用 block 色
- 延遲血條：血條先快速掉到新值，後面留一段較淡的顏色慢慢追上

以上全部由 diff_triggers()／diff_damage_numbers() 這兩個純函式，比較同一次 bridge 呼叫
前後的 player_view/enemy_view 算出來，觸發流程完全不變：battle scene 在呼叫 play_card／
enemy_act 前後各拍一次 view 快照，算完直接餵給 FxQueue，不需要碰 rules.py。

效果播放期間 battle scene 不接受輸入，但點擊或按任意鍵會呼叫 skip() 立刻快轉到結果狀態
（不是取消）。終端機版（supports_animation() 回傳 False）跟 --no-fx 都會讓
battle scene 完全不排入任何效果。
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

DAMAGE_NUMBER_DURATION = 0.8  # 傷害數字從彈出到消失的總時間
DAMAGE_NUMBER_RISE = 3  # 往上飄幾格
DAMAGE_NUMBER_FADE_AT = 0.6  # 進度超過這個比例後開始淡出（改用 dim 色）

HP_LAG_DURATION = 0.6  # 較淡的殘影血條追上新血量要花多久


@dataclass
class _Effect:
    kind: str
    duration: float
    elapsed: float = 0.0

    @property
    def active(self) -> bool:
        return self.elapsed < self.duration


@dataclass
class _FloatingNumber:
    amount: int
    color: str  # "hp" 或 "block"
    origin: str  # "player" 或 "enemy"，決定要從哪個位置飄出
    duration: float
    elapsed: float = 0.0

    @property
    def active(self) -> bool:
        return self.elapsed < self.duration

    @property
    def progress(self) -> float:
        return 0.0 if self.duration <= 0 else min(1.0, self.elapsed / self.duration)

    @property
    def row_offset(self) -> int:
        """目前該往上飄幾格（負數）。"""
        return -round(DAMAGE_NUMBER_RISE * self.progress)

    @property
    def display_color(self) -> str:
        return "dim" if self.progress >= DAMAGE_NUMBER_FADE_AT else self.color


@dataclass
class _HpLag:
    from_value: int
    to_value: int
    duration: float
    elapsed: float = 0.0

    @property
    def active(self) -> bool:
        return self.elapsed < self.duration

    @property
    def current(self) -> int:
        """目前殘影血條該停在哪個值：從 from_value 慢慢追到 to_value。"""
        if self.duration <= 0:
            return self.to_value
        t = min(1.0, self.elapsed / self.duration)
        return round(self.from_value + (self.to_value - self.from_value) * t)


class FxQueue:
    """目前正在播放的效果，可以同時播好幾種（閃爍/抖動效果依種類區分、傷害數字可以同時有好幾個）。"""

    def __init__(self) -> None:
        self._effects: dict[str, _Effect] = {}
        self._numbers: list[_FloatingNumber] = []
        self._hp_lag: dict[str, _HpLag] = {}

    # -- 閃爍／抖動效果（敵人被打、玩家被打、護盾增加） -----------------------

    def trigger(self, kind: str, duration: float = DEFAULT_DURATION) -> None:
        self._effects[kind] = _Effect(kind, duration)

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

    # -- 傷害數字彈出 -----------------------------------------------------

    def spawn_number(self, amount: int, color: str, origin: str, duration: float = DAMAGE_NUMBER_DURATION) -> None:
        self._numbers.append(_FloatingNumber(amount, color, origin, duration))

    def numbers_for(self, origin: str) -> list[_FloatingNumber]:
        """回傳目前這個位置（"player" 或 "enemy"）還在飄的數字，依出現順序排列。"""
        return [n for n in self._numbers if n.origin == origin]

    # -- 延遲血條 ---------------------------------------------------------

    def start_hp_lag(self, target: str, from_value: int, to_value: int, duration: float = HP_LAG_DURATION) -> None:
        """血量下降時呼叫：血條本身立刻顯示新值，另外留一段殘影慢慢從舊值追到新值。"""
        if from_value <= to_value:
            return  # 只有下降才需要殘影，上升（回血）不用
        self._hp_lag[target] = _HpLag(from_value, to_value, duration)

    def hp_lag_value(self, target: str) -> int | None:
        """殘影血條目前該停在哪個值；沒有殘影在跑時回傳 None（畫面上就不畫殘影）。"""
        lag = self._hp_lag.get(target)
        return lag.current if lag is not None else None

    # -- 共用 ---------------------------------------------------------------

    def update(self, dt: float) -> None:
        for kind in list(self._effects):
            effect = self._effects[kind]
            effect.elapsed += dt
            if not effect.active:
                del self._effects[kind]
        for number in self._numbers:
            number.elapsed += dt
        self._numbers = [n for n in self._numbers if n.active]
        for target in list(self._hp_lag):
            lag = self._hp_lag[target]
            lag.elapsed += dt
            if not lag.active:
                del self._hp_lag[target]

    @property
    def is_playing(self) -> bool:
        return bool(self._effects) or bool(self._numbers) or bool(self._hp_lag)

    def skip(self) -> None:
        """播放期間收到任何輸入時呼叫：不是取消，是直接快轉到目前所有效果的最終狀態
        （閃爍/抖動停止、殘影血條追上新值、還沒飄完的數字直接消失）。"""
        self._effects = {}
        self._numbers = []
        self._hp_lag = {}

    def clear(self) -> None:
        self.skip()


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


def diff_damage_numbers(
    before_player: dict, after_player: dict, before_enemy: dict, after_enemy: dict
) -> list[tuple[str, int, str]]:
    """比較 bridge 呼叫前後的 view，算出這次要彈出的傷害數字：
    回傳 (origin, amount, color) 的清單，origin 是 "player" 或 "enemy"，
    扣血用 "hp" 色、被護盾吸收的量用 "block" 色。"""
    numbers: list[tuple[str, int, str]] = []
    for origin, before, after in (("player", before_player, after_player), ("enemy", before_enemy, after_enemy)):
        hp_lost = before.get("hp", 0) - after.get("hp", 0)
        if hp_lost > 0:
            numbers.append((origin, hp_lost, "hp"))
        block_absorbed = before.get("block", 0) - after.get("block", 0)
        if block_absorbed > 0:
            numbers.append((origin, block_absorbed, "block"))
    return numbers
