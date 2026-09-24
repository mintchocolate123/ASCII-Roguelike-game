"""視覺效果佇列。

大部分效果由引擎比較 bridge 呼叫前後的 view 差異自動產生，rules.py 不需要呼叫任何 fx API：
- 敵人 HP 下降：敵人圖閃紅並左右抖動 1 格（ENEMY_HIT）
- 玩家 HP 下降：玩家狀態列閃紅（PLAYER_HIT）
- 護盾增加：護盾數字閃藍色（PLAYER_BLOCK_GAIN / ENEMY_BLOCK_GAIN）
- 傷害數字彈出：受擊位置浮出數字往上飄後淡出，扣血用 hp 色、被護盾吸收的量用 block 色。
  多段攻擊（卡牌有 hits 欄位且大於 1）不會只彈一個總和數字：battle scene 會把這次對敵人造成
  的總傷害（扣血 + 護盾吸收）依卡牌資料判斷後平均拆成 hits 份，依序間隔短暫時間彈出，最後
  一份補上除不盡的餘數，全部用 hp 色顯示（不再細分扣血／護盾吸收）
- 延遲血條：血條先快速掉到新值，後面留一段較淡的顏色慢慢追上
- 頭目大招整面晃動：敵人單次攻擊造成的傷害達到門檻時整個畫面晃動（SCREEN_SHAKE），
  沒達到門檻的一般攻擊維持只晃玩家狀態列（PLAYER_HIT 的 shake_offset）
- 意圖變化：敵人切換到下一個行動時，意圖那一行閃一下（INTENT_CHANGE）

以上都由 diff_triggers()／diff_damage_numbers() 這兩個純函式，比較同一次 bridge 呼叫
前後的 player_view/enemy_view 算出來（SCREEN_SHAKE／INTENT_CHANGE 門檻與切換判斷則是
battle scene 自己算好門檻/action_index 後直接呼叫 trigger()，不需要碰 rules.py）。

以下兩種效果不是數值變化，view diff 推斷不出來，battle scene 會在知道發生什麼事的當下
直接呼叫對應的明確介面排入效果，不會硬塞進 diff_triggers()：
- 出牌飛出：start_card_fly(card, x, y, target_x, target_y, width, height)，scene 在卡片被
  打出、從手牌移除前先記下它原本的卡面內容、座標跟原本的卡片尺寸；卡片會往 target（敵人圖
  中心）飛，過程中逐漸縮小成單格再消失，不是整張維持原尺寸位移
- 敵人死亡：start_enemy_death(art)，scene 在偵測到 enemy hp 從 > 0 掉到 <= 0 時呼叫；
  battle scene 會等這個動畫播完（或被跳過）才真正進入 BATTLE_END，避免畫面卡在半途跳走

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
SCREEN_SHAKE = "screen_shake"
INTENT_CHANGE = "intent_change"

DEFAULT_DURATION = 0.4
FLASH_INTERVAL = 0.08  # 閃爍間隔：每經過這麼多秒切換一次顏色
SHAKE_OFFSETS = (-1, 1, -1, 1, 0)  # 抖動的左右位移序列，最後回到 0；受擊方晃動與整面晃動共用

DAMAGE_NUMBER_DURATION = 0.8  # 傷害數字從彈出到消失的總時間
DAMAGE_NUMBER_RISE = 3  # 往上飄幾格
DAMAGE_NUMBER_FADE_AT = 0.6  # 進度超過這個比例後開始淡出（改用 dim 色）
DAMAGE_NUMBER_STAGGER_INTERVAL = 0.12  # 多段攻擊每一份數字之間，依序彈出的間隔

HP_LAG_DURATION = 0.6  # 較淡的殘影血條追上新血量要花多久

SCREEN_SHAKE_THRESHOLD = 20  # 敵人單次攻擊造成的傷害達到這個門檻，才會整面晃動而不是只晃玩家狀態列

CARD_FLY_DURATION = 0.2  # 出牌後卡片飛向敵人要花多久：距離比之前的「飛出畫面」短很多，要快才有打擊感

ENEMY_DEATH_DURATION = 0.8  # 敵人死亡、ASCII 圖逐行消失的總時間


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
    slot: int = 0  # 水平排列的固定順位，不受目前顯示中的數字增減影響（多段攻擊會有好幾個）
    delay: float = 0.0  # 要再經過多久才開始出現；多段攻擊靠這個做出依序彈出的效果
    elapsed: float = 0.0

    @property
    def visible(self) -> bool:
        """delay 還沒過完之前，這個數字還「沒輪到」，不該畫出來（但仍然算在 is_playing 裡）。"""
        return self.elapsed >= self.delay

    @property
    def active(self) -> bool:
        return self.elapsed < self.delay + self.duration

    @property
    def progress(self) -> float:
        if not self.visible or self.duration <= 0:
            return 0.0
        return min(1.0, (self.elapsed - self.delay) / self.duration)

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


@dataclass
class _CardFly:
    """出牌飛出：卡片從原本手牌位置的中心飛向 target（敵人圖中心），過程中逐漸縮小成單格。"""

    card: dict
    x: int
    y: int
    width: int
    height: int
    target_x: int
    target_y: int
    duration: float
    elapsed: float = 0.0

    @property
    def active(self) -> bool:
        return self.elapsed < self.duration

    @property
    def progress(self) -> float:
        return 0.0 if self.duration <= 0 else min(1.0, self.elapsed / self.duration)

    @property
    def current_width(self) -> int:
        """從原本的寬度逐漸縮到 1（單格）。"""
        return max(1, round(self.width - (self.width - 1) * self.progress))

    @property
    def current_height(self) -> int:
        return max(1, round(self.height - (self.height - 1) * self.progress))

    @property
    def current_center(self) -> tuple[int, int]:
        """目前縮小中的卡片中心，從原本卡片的中心線性飛向 target。"""
        start_cx = self.x + self.width / 2
        start_cy = self.y + self.height / 2
        cx = start_cx + (self.target_x - start_cx) * self.progress
        cy = start_cy + (self.target_y - start_cy) * self.progress
        return round(cx), round(cy)

    @property
    def current_x(self) -> int:
        """目前縮小中的卡片左上角欄座標（by 中心跟目前寬度反推）。"""
        cx, _ = self.current_center
        return cx - self.current_width // 2

    @property
    def current_y(self) -> int:
        _, cy = self.current_center
        return cy - self.current_height // 2


@dataclass
class _EnemyDeath:
    """敵人死亡：ASCII 圖逐行消失（從最後一行開始收）。"""

    art: list
    duration: float
    elapsed: float = 0.0

    @property
    def active(self) -> bool:
        return self.elapsed < self.duration

    @property
    def progress(self) -> float:
        return 0.0 if self.duration <= 0 else min(1.0, self.elapsed / self.duration)

    @property
    def visible_art(self) -> list:
        total = len(self.art)
        remaining = max(0, total - round(total * self.progress))
        return self.art[:remaining]


class FxQueue:
    """目前正在播放的效果，可以同時播好幾種（閃爍/抖動效果依種類區分、傷害數字可以同時有好幾個）。"""

    def __init__(self) -> None:
        self._effects: dict[str, _Effect] = {}
        self._numbers: list[_FloatingNumber] = []
        self._hp_lag: dict[str, _HpLag] = {}
        self._card_fly: _CardFly | None = None
        self._enemy_death: _EnemyDeath | None = None

    # -- 閃爍／抖動效果（敵人被打、玩家被打、護盾增加、整面晃動、意圖變化） -----

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

    def shake_offset(self, kind: str = ENEMY_HIT) -> int:
        """指定種類（預設 ENEMY_HIT）目前該往左或右偏移幾格；沒有對應效果時回傳 0。
        ENEMY_HIT／PLAYER_HIT 用來晃受擊方本身，SCREEN_SHAKE 用來晃整個畫面（見 battle scene
        的 draw()，會透過一個幫整格座標加上位移的 Grid proxy 套用到整幅畫面）。"""
        effect = self._effects.get(kind)
        if effect is None:
            return 0
        step_duration = effect.duration / len(SHAKE_OFFSETS)
        index = min(int(effect.elapsed / step_duration), len(SHAKE_OFFSETS) - 1)
        return SHAKE_OFFSETS[index]

    # -- 傷害數字彈出 -----------------------------------------------------

    def _next_slot(self, origin: str) -> int:
        """這個位置目前已經有幾個數字（含還沒輪到出現的），新數字的水平排列順位接在後面。"""
        return sum(1 for n in self._numbers if n.origin == origin)

    def spawn_number(self, amount: int, color: str, origin: str, duration: float = DAMAGE_NUMBER_DURATION) -> None:
        self._numbers.append(_FloatingNumber(amount, color, origin, duration, slot=self._next_slot(origin)))

    def spawn_staggered_numbers(
        self,
        total: int,
        count: int,
        color: str,
        origin: str,
        *,
        duration: float = DAMAGE_NUMBER_DURATION,
        interval: float = DAMAGE_NUMBER_STAGGER_INTERVAL,
    ) -> None:
        """多段攻擊（卡牌有 hits 欄位）用：把 total 平均拆成 count 份，依序間隔 interval 秒
        彈出，除不盡的餘數補在最後一份。count <= 0 或 total <= 0 時什麼都不做。"""
        if count <= 0 or total <= 0:
            return
        base = total // count
        remainder = total - base * count
        slot = self._next_slot(origin)
        for i in range(count):
            amount = base + (remainder if i == count - 1 else 0)
            if amount <= 0:
                continue
            self._numbers.append(
                _FloatingNumber(amount, color, origin, duration, slot=slot, delay=i * interval)
            )
            slot += 1

    def numbers_for(self, origin: str) -> list[_FloatingNumber]:
        """回傳目前這個位置（"player" 或 "enemy"）還在飄、而且已經輪到出現的數字。"""
        return [n for n in self._numbers if n.origin == origin and n.visible]

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

    # -- 出牌飛出 -----------------------------------------------------------
    # 不是數值變化，view diff 推斷不出來：battle scene 在卡片打出、從手牌移除前，
    # 自己記下卡面內容、原本畫在畫面上的座標跟尺寸，明確呼叫這個介面排入效果。

    def start_card_fly(
        self,
        card: dict,
        x: int,
        y: int,
        target_x: int,
        target_y: int,
        width: int,
        height: int,
        duration: float = CARD_FLY_DURATION,
    ) -> None:
        self._card_fly = _CardFly(dict(card), x, y, width, height, target_x, target_y, duration)

    @property
    def card_fly(self) -> _CardFly | None:
        """目前正在飛出畫面的卡片；沒有時回傳 None。"""
        return self._card_fly

    # -- 敵人死亡 -----------------------------------------------------------
    # 一樣不是數值變化：battle scene 偵測到 enemy hp 從 > 0 掉到 <= 0 時明確呼叫，
    # 引擎會等這個動畫播完（或被跳過）才真正把 finished 設成 True。

    def start_enemy_death(self, art: list, duration: float = ENEMY_DEATH_DURATION) -> None:
        self._enemy_death = _EnemyDeath(list(art), duration)

    @property
    def enemy_death_active(self) -> bool:
        return self._enemy_death is not None

    @property
    def enemy_death_art(self) -> list | None:
        """死亡動畫目前該顯示的 ASCII 圖（逐行變少）；沒有動畫在跑時回傳 None。"""
        return self._enemy_death.visible_art if self._enemy_death is not None else None

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
        if self._card_fly is not None:
            self._card_fly.elapsed += dt
            if not self._card_fly.active:
                self._card_fly = None
        if self._enemy_death is not None:
            self._enemy_death.elapsed += dt
            if not self._enemy_death.active:
                self._enemy_death = None

    @property
    def is_playing(self) -> bool:
        return (
            bool(self._effects)
            or bool(self._numbers)
            or bool(self._hp_lag)
            or self._card_fly is not None
            or self._enemy_death is not None
        )

    def skip(self) -> None:
        """播放期間收到任何輸入時呼叫：不是取消，是直接快轉到目前所有效果的最終狀態
        （閃爍/抖動停止、殘影血條追上新值、還沒飄完的數字跟還沒飛完的卡片直接消失、
        敵人死亡動畫直接收尾）。"""
        self._effects = {}
        self._numbers = []
        self._hp_lag = {}
        self._card_fly = None
        self._enemy_death = None

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
