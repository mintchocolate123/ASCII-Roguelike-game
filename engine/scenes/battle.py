"""戰鬥畫面：終端機版第一階段。走 BATTLE_START -> PLAYER_TURN -> ENEMY_TURN ->
（分出勝負前一直循環）-> BATTLE_END 的狀態機，每次狀態轉換都呼叫 check_result。

所有跟 mod 程式碼的接觸都透過 bridge，這個檔案完全不 import mods 底下的任何東西。
"""
from __future__ import annotations

from .. import layout
from ..actions import Action, Back, ClickCard, Confirm, EndTurn, HoverEndTurn, Inspect, PlayCard, Reload
from ..bridge import Bridge, ModCallError
from ..draw import (
    TYPE_LABELS,
    draw_ascii_art,
    draw_banner,
    draw_box,
    draw_button,
    draw_card,
    draw_energy_pips,
    draw_hline,
    draw_hp_bar,
    draw_keyword_text,
    draw_text,
    draw_vline,
    text_width,
    wrap_text,
)
from ..fx import (
    ENEMY_BLOCK_GAIN,
    ENEMY_HIT,
    INTENT_CHANGE,
    PLAYER_BLOCK_GAIN,
    PLAYER_HIT,
    SCREEN_SHAKE,
    SCREEN_SHAKE_THRESHOLD,
    FxQueue,
    diff_damage_numbers,
    diff_triggers,
)
from ..grid import Grid
from .scene import Scene


class _ShiftedGrid:
    """把 set_cell 的欄座標整體位移 dx 格的 grid 包裝，只用來實作頭目大招的整面畫面晃動。
    只包裝 draw.py 實際會用到的介面（width/height/set_cell），dx 通常是 -1、0、1。"""

    def __init__(self, grid: Grid, dx: int) -> None:
        self._grid = grid
        self._dx = dx
        self.width = grid.width
        self.height = grid.height

    def set_cell(self, x: int, y: int, char: str, fg: str = "text", bg: str | None = None, wide_tail: bool = False) -> None:
        self._grid.set_cell(x + self._dx, y, char, fg, bg, wide_tail)


STATE_BATTLE_START = "battle_start"
STATE_PLAYER_TURN = "player_turn"
STATE_ENEMY_TURN = "enemy_turn"
STATE_BATTLE_END = "battle_end"
STATE_SHOWING_ERROR = "showing_error"

ERROR_PANEL_WIDTH = 90


class BattleScene(Scene):
    def __init__(
        self,
        bridge: Bridge,
        player,
        enemy,
        *,
        floor: int = 1,
        supports_animation: bool = True,
        supports_mouse: bool = True,
    ) -> None:
        self.bridge = bridge
        self.player = player
        self.enemy = enemy
        self.floor = floor
        self.turn = 1
        self.supports_animation = supports_animation
        self.supports_mouse = supports_mouse

        self.battle_log: list[str] = []
        self.inspect_index: int | None = None
        self.selected_index: int | None = None  # 滑鼠兩段式點擊：第一下選取，第二下才出牌
        self.end_turn_hovered = False
        self.result: str | None = None
        self.current_intent: dict | None = None

        self.fatal_error: ModCallError | None = None
        self.error_recoverable = False
        self._resume_state: str | None = None
        self.finished = False
        self._pending_finish = False  # 分出勝負後，等敵人死亡動畫播完（或被跳過）才真的設 finished

        self.fx = FxQueue()
        self.reload_requested = False

        self.state = STATE_BATTLE_START
        self._enter_battle_start()

    # ------------------------------------------------------------------
    # 狀態機
    # ------------------------------------------------------------------

    def _log(self, message: str) -> None:
        self.battle_log.append(message)

    def _call_hook(self, name: str, *args) -> bool:
        """回傳 True 表示成功（或本來就沒實作），False 表示已經進入錯誤畫面。"""
        try:
            self.bridge.call_hook(name, *args)
        except ModCallError as exc:
            self._fatal(exc)
            return False
        return True

    def _check_and_maybe_end(self) -> bool:
        """呼叫 check_result；分出勝負就轉成 BATTLE_END。回傳戰鬥是否已經結束（含出錯）。

        如果敵人死亡動畫正在播（self.fx.enemy_death_active），先不設定 finished，
        等動畫播完（或被跳過）由 update() 補設，避免下一個畫面在動畫播到一半時就跳走。"""
        if self._pending_finish:
            return True
        try:
            result = self.bridge.check_result(self.player, self.enemy)
        except ModCallError as exc:
            self._fatal(exc)
            return True
        if result is not None:
            self.result = result
            self.state = STATE_BATTLE_END
            self._log("你獲勝了！" if result == "win" else "你被擊敗了……")
            self._call_hook("on_battle_end", self.player, self.enemy)
            if self.fx.enemy_death_active:
                self._pending_finish = True
            else:
                self.finished = True
            return True
        return False

    def _enter_battle_start(self) -> None:
        self.state = STATE_BATTLE_START
        if not self._call_hook("on_battle_start", self.player, self.enemy):
            return
        if self._check_and_maybe_end():
            return
        self._enter_player_turn()

    def _enter_player_turn(self, *, prev_action_index: int | None = None) -> None:
        self.state = STATE_PLAYER_TURN
        try:
            self.bridge.start_turn(self.player)
        except ModCallError as exc:
            self._fatal(exc)
            return
        if not self._call_hook("on_turn_start", self.player):
            return
        if self._check_and_maybe_end():
            return
        try:
            self.current_intent = self.bridge.get_enemy_intent(self.enemy)
        except ModCallError as exc:
            self._fatal(exc)
            return
        if (
            self.supports_animation
            and prev_action_index is not None
            and self.enemy.get("action_index") != prev_action_index
        ):
            # 意圖變化：敵人切換到下一個行動時，意圖那一行閃一下。不是數值變化，
            # 直接比較 action_index 就好，不需要塞進 diff_triggers()。
            self.fx.trigger(INTENT_CHANGE)

    def _enter_enemy_turn(self) -> None:
        self.state = STATE_ENEMY_TURN
        if self._check_and_maybe_end():
            return
        if not self._call_hook("on_turn_end", self.player):
            return
        prev_action_index = self.enemy.get("action_index")
        before_player = dict(self.bridge.player_view(self.player))
        before_enemy = dict(self.bridge.enemy_view(self.enemy))
        try:
            message = self.bridge.enemy_act(self.enemy, self.player)
        except ModCallError as exc:
            self._fatal(exc)
            return
        self._log(message)
        self._trigger_fx(before_player, before_enemy, is_enemy_attack=True)
        if self._check_and_maybe_end():
            return
        self.turn += 1
        self._enter_player_turn(prev_action_index=prev_action_index)

    def _trigger_fx(self, before_player: dict, before_enemy: dict, *, is_enemy_attack: bool = False) -> None:
        """比較呼叫前後的 view，自動排入對應的效果。終端機版／--no-fx（supports_animation=False）
        直接略過，不會排入任何效果。"""
        if not self.supports_animation:
            return
        after_player = self.bridge.player_view(self.player)
        after_enemy = self.bridge.enemy_view(self.enemy)

        for kind in diff_triggers(before_player, after_player, before_enemy, after_enemy):
            self.fx.trigger(kind)

        for origin, amount, color in diff_damage_numbers(before_player, after_player, before_enemy, after_enemy):
            self.fx.spawn_number(amount, color, origin)

        for origin, before, after in (("player", before_player, after_player), ("enemy", before_enemy, after_enemy)):
            self.fx.start_hp_lag(origin, before.get("hp", 0), after.get("hp", 0))

        if is_enemy_attack:
            # 頭目大招整面晃動：敵人單次攻擊造成的傷害（打進 hp 的 + 被護盾吸收的）達到門檻才整面晃，
            # 沒達到門檻的一般攻擊維持原本只晃受擊方（enemy_hit 只晃敵人圖；玩家被打只閃紅，不新增晃動）。
            hp_lost = before_player.get("hp", 0) - after_player.get("hp", 0)
            block_absorbed = before_player.get("block", 0) - after_player.get("block", 0)
            total_damage = max(0, hp_lost) + max(0, block_absorbed)
            if total_damage >= SCREEN_SHAKE_THRESHOLD:
                self.fx.trigger(SCREEN_SHAKE)

        # 敵人死亡：不是數值變化本身，是「hp 從 > 0 掉到 <= 0」這個事件，view diff 的
        # diff_triggers() 只回傳 kind 字串沒辦法帶 art，這裡直接明確呼叫 start_enemy_death()。
        if before_enemy.get("hp", 0) > 0 and after_enemy.get("hp", 0) <= 0:
            self.fx.start_enemy_death(after_enemy.get("art", []))

    def _fatal(self, error: ModCallError) -> None:
        """battle 流程本身出錯：顯示錯誤面板，玩家確認後結束整場戰鬥（回到標題等級的安全狀態）。"""
        self.fatal_error = error
        self._resume_state = self.state
        self.state = STATE_SHOWING_ERROR
        self.error_recoverable = False

    def _card_error(self, error: ModCallError) -> None:
        """出牌本身出錯：顯示錯誤面板，玩家確認後取消這次出牌，留在原本的回合繼續玩。"""
        self.fatal_error = error
        self._resume_state = STATE_PLAYER_TURN
        self.state = STATE_SHOWING_ERROR
        self.error_recoverable = True

    # ------------------------------------------------------------------
    # 輸入
    # ------------------------------------------------------------------

    def handle(self, actions: list[Action]) -> None:
        for action in actions:
            self._handle_one(action)

    def _handle_one(self, action: Action) -> None:
        if isinstance(action, Reload):
            # F5 隨時都能按：出錯畫面卡住、效果播放中，都不應該擋住重新載入。
            self.reload_requested = True
            return
        if self.fx.is_playing:
            # 效果播放期間不接受輸入，但任何輸入都會讓效果立刻快轉到結果狀態
            # （不是取消，下一個輸入才會被當成正常的遊戲操作處理）。
            self.fx.skip()
            return
        if self.state == STATE_SHOWING_ERROR:
            if isinstance(action, (Confirm, Back)):
                self._dismiss_error()
            return
        if self.finished:
            return
        if isinstance(action, Inspect):
            hand = self.bridge.player_view(self.player).get("hand", [])
            if action.index is not None and 0 <= action.index < len(hand):
                self.inspect_index = action.index
            else:
                self.inspect_index = None
            return
        if isinstance(action, HoverEndTurn):
            self.end_turn_hovered = action.active
            return
        if isinstance(action, Back):
            self.inspect_index = None
            self.selected_index = None
            return
        if self.state != STATE_PLAYER_TURN:
            return
        if isinstance(action, ClickCard):
            self._click_card(action.index)
        elif isinstance(action, PlayCard):
            self._play_card(action.index)  # 數字鍵：一律直接出牌，不用兩段式
        elif isinstance(action, EndTurn):
            self._enter_enemy_turn()

    def _click_card(self, index: int | None) -> None:
        """滑鼠兩段式點擊：點空白處或點到範圍外取消選取；點第一下選取（能量不足的卡只顯示
        詳情、不會進入選取狀態）；對已經選取的那張卡再點一次才會真的出牌。"""
        hand = self.bridge.player_view(self.player).get("hand", [])
        if index is None or not (0 <= index < len(hand)):
            self.selected_index = None
            self.inspect_index = None
            return
        if self.selected_index == index:
            # 不在這裡先清掉 selected_index：_play_card 需要知道這張卡點擊當下是不是選取中，
            # 才能算出飛出動畫該從哪一列（選取中的卡畫面上整張上移了一格）開始飛。
            # _play_card 自己會在算完之後把 selected_index 清掉。
            self._play_card(index)
            return
        self.inspect_index = index
        self.selected_index = index if self._card_playable_for_display(index) else None

    def _dismiss_error(self) -> None:
        if self.error_recoverable:
            self.state = self._resume_state or STATE_PLAYER_TURN
        else:
            self.finished = True
        self.fatal_error = None

    def _play_card(self, index: int) -> None:
        hand = self.bridge.player_view(self.player).get("hand", [])
        if index < 0 or index >= len(hand):
            self._log("沒有這張牌。")
            return
        card = hand[index]  # 出牌成功後會被移出手牌，先記下卡面內容給飛出動畫用

        try:
            can = self.bridge.can_play(self.player, index)
        except ModCallError as exc:
            self._card_error(exc)
            return
        if not can:
            self._log(f"現在無法使用「{hand[index].get('name', '?')}」。")
            return

        if not self._call_hook("before_play", self.player, self.enemy, index):
            return

        before_player = dict(self.bridge.player_view(self.player))
        before_enemy = dict(self.bridge.enemy_view(self.enemy))
        try:
            message = self.bridge.play_card(self.player, self.enemy, index)
        except ModCallError as exc:
            self._card_error(exc)
            return
        self._log(message)
        self.inspect_index = None
        card_y = layout.HAND_ROW_TOP + (
            layout.SELECTED_CARD_ROW_OFFSET if self.selected_index == index else 0
        )
        self.selected_index = None
        self._trigger_fx(before_player, before_enemy)

        if self.supports_animation:
            # 出牌飛出：不是數值變化，直接明確呼叫，記下這張卡原本畫在畫面上的位置。
            self.fx.start_card_fly(card, layout.card_slot_x(index), card_y)

        if not self._call_hook("after_play", self.player, self.enemy, index):
            return
        self._check_and_maybe_end()

    # ------------------------------------------------------------------
    # 更新／繪圖
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self.fx.update(dt)
        if self._pending_finish and not self.fx.is_playing:
            self._pending_finish = False
            self.finished = True

    def draw(self, grid: Grid) -> None:
        if self.state == STATE_SHOWING_ERROR:
            self._draw_error_panel(grid)
            return
        # 頭目大招整面晃動：套一層幫座標加位移的 grid 包裝，這次畫面剩下的內容全部一起偏移，
        # 不用在每個 _draw_* 裡各自加位移。
        target = grid
        screen_dx = self.fx.shake_offset(SCREEN_SHAKE)
        if screen_dx:
            target = _ShiftedGrid(grid, screen_dx)
        player_view = self.bridge.player_view(self.player)
        enemy_view = self.bridge.enemy_view(self.enemy)
        self._draw_frame(target)
        self._draw_enemy(target, enemy_view)
        self._draw_right_panel(target, player_view)
        self._draw_player_status(target, player_view)
        self._draw_hand(target, player_view)
        self._draw_flying_card(target)
        self._draw_hint(target)

    # -- 主框 -----------------------------------------------------------

    def _draw_frame(self, grid: Grid) -> None:
        fg = "frame"
        draw_box(grid, layout.FRAME_LEFT, layout.FRAME_TOP, layout.FRAME_WIDTH, layout.FRAME_HEIGHT, fg=fg, style="double")
        grid.set_cell(layout.PANEL_DIVIDER_COL, layout.FRAME_TOP, "╦", fg)

        draw_text(grid, layout.LEFT_CONTENT_START + 1, layout.HEADER_ROW, f"◆ 地下第 {self.floor} 層", fg="text")
        turn_label = f"回合 {self.turn}"
        draw_text(
            grid,
            layout.LEFT_CONTENT_END - text_width(turn_label) + 1,
            layout.HEADER_ROW,
            turn_label,
            fg="text",
        )
        showing_detail = self.selected_index is not None or self.inspect_index is not None
        title = "檢視卡牌" if showing_detail else "戰鬥紀錄"
        right_title = f"─── {title} ───"
        title_x = layout.RIGHT_CONTENT_START + max(
            0, (layout.RIGHT_PANEL_CONTENT_WIDTH - text_width(right_title)) // 2
        )
        draw_text(grid, title_x, layout.HEADER_ROW, right_title, fg="text")

        draw_vline(grid, layout.PANEL_DIVIDER_COL, layout.HEADER_ROW, layout.ENEMY_STATUS_ROW - layout.HEADER_ROW + 1, fg)

        draw_hline(grid, layout.FRAME_LEFT + 1, layout.LEFT_DIVIDER_ROW, layout.PANEL_DIVIDER_COL - 1, fg)
        grid.set_cell(layout.FRAME_LEFT, layout.LEFT_DIVIDER_ROW, "╠", fg)
        grid.set_cell(layout.PANEL_DIVIDER_COL, layout.LEFT_DIVIDER_ROW, "╣", fg)

        draw_hline(grid, layout.FRAME_LEFT + 1, layout.FULL_DIVIDER_ROW, layout.FRAME_RIGHT - layout.FRAME_LEFT - 1, fg)
        grid.set_cell(layout.FRAME_LEFT, layout.FULL_DIVIDER_ROW, "╠", fg)
        grid.set_cell(layout.PANEL_DIVIDER_COL, layout.FULL_DIVIDER_ROW, "╩", fg)
        grid.set_cell(layout.FRAME_RIGHT, layout.FULL_DIVIDER_ROW, "╣", fg)

    # -- 敵人 -------------------------------------------------------------

    def _draw_enemy(self, grid: Grid, enemy_view: dict) -> None:
        full_art = enemy_view.get("art", [])
        # 敵人死亡：ASCII 圖逐行消失。寬度用完整的圖算，不要用逐漸變少的那幾行算，
        # 不然圖會一邊消失一邊左右跳動。
        art = self.fx.enemy_death_art if self.fx.enemy_death_active else full_art
        art_width = max((text_width(line) for line in full_art), default=0)
        left_width = layout.LEFT_CONTENT_END - layout.LEFT_CONTENT_START + 1
        art_x = layout.LEFT_CONTENT_START + max(0, (left_width - art_width) // 2) + self.fx.shake_offset(ENEMY_HIT)
        art_color = "hp" if self.fx.flash_on(ENEMY_HIT) else enemy_view.get("color", "white")
        draw_ascii_art(grid, art_x, layout.ENEMY_ART_TOP, art, fg=art_color)

        banner_width = 40
        banner_x = layout.LEFT_CONTENT_START + (left_width - banner_width) // 2
        draw_banner(grid, banner_x, layout.ENEMY_BANNER_ROW, banner_width, enemy_view.get("name", "?"))

        hp = enemy_view.get("hp", 0)
        max_hp = enemy_view.get("max_hp", max(hp, 1))
        block = enemy_view.get("block", 0)
        hp_x = layout.LEFT_CONTENT_START + 15
        draw_text(grid, hp_x, layout.ENEMY_HP_ROW, "HP ", fg="text")
        draw_hp_bar(grid, hp_x + 3, layout.ENEMY_HP_ROW, 20, hp, max_hp, lag_current=self.fx.hp_lag_value("enemy"))
        draw_text(grid, hp_x + 24, layout.ENEMY_HP_ROW, f"{hp}/{max_hp}", fg="text")
        if block > 0:
            block_color = "highlight" if self.fx.flash_on(ENEMY_BLOCK_GAIN) else "block"
            draw_text(grid, hp_x + 35, layout.ENEMY_HP_ROW, f"盾 {block}", fg=block_color)

        self._draw_damage_numbers(grid, "enemy", layout.ENEMY_DAMAGE_NUMBER_X, layout.ENEMY_DAMAGE_NUMBER_Y)

        if self.current_intent is not None:
            intent = self._format_intent(self.current_intent)
            if self.fx.flash_on(INTENT_CHANGE):
                intent_color = "highlight"
            else:
                intent_color = "attack" if self.current_intent.get("type") == "attack" else "skill"
            intent_x = layout.LEFT_CONTENT_START + max(0, (left_width - text_width(intent)) // 2)
            draw_text(grid, intent_x, layout.ENEMY_INTENT_ROW, intent, fg=intent_color)

    @staticmethod
    def _format_intent(intent: dict) -> str:
        value = intent.get("value", 0)
        if intent.get("type") == "attack":
            return f">> 準備攻擊 {value} <<"
        return f">> 準備防禦 {value} <<"

    def _draw_damage_numbers(self, grid: Grid, origin: str, x: int, y: int) -> None:
        """畫出從 (x, y) 往上飄的傷害數字：扣血用 hp 色，被護盾吸收的量用 block 色。"""
        for i, number in enumerate(self.fx.numbers_for(origin)):
            draw_text(grid, x + i * 5, y + number.row_offset, f"-{number.amount}", fg=number.display_color)

    # -- 右面板：戰鬥紀錄 / 卡牌詳細資訊 ------------------------------------

    def _draw_right_panel(self, grid: Grid, player_view: dict) -> None:
        hand = player_view.get("hand", [])
        # 選取中的卡片「固定顯示」詳情，優先於滑鼠移入等短暫的檢視。
        detail_index = self.selected_index if self.selected_index is not None else self.inspect_index
        if detail_index is not None and 0 <= detail_index < len(hand):
            self._draw_card_detail(grid, hand[detail_index])
            return
        self._draw_battle_log(grid)

    def _draw_battle_log(self, grid: Grid) -> None:
        wrapped: list[str] = []
        for entry in self.battle_log:
            wrapped.extend(wrap_text(f"› {entry}", layout.RIGHT_PANEL_CONTENT_WIDTH))
        visible_height = layout.RIGHT_PANEL_BOTTOM - layout.RIGHT_PANEL_TOP
        visible = wrapped[-visible_height:] if visible_height > 0 else []
        start_row = layout.RIGHT_PANEL_BOTTOM - len(visible)
        for i, line in enumerate(visible):
            draw_text(grid, layout.RIGHT_CONTENT_START + 1, start_row + i, line, fg="text")

    def _draw_card_detail(self, grid: Grid, card: dict) -> None:
        y = layout.RIGHT_PANEL_TOP
        x = layout.RIGHT_CONTENT_START + 1
        type_label = TYPE_LABELS.get(card.get("type"), card.get("type", "?"))
        draw_text(grid, x, y, card.get("name", "?"), fg="text")
        draw_text(grid, x, y + 1, f"費用 {card.get('cost', '?')}　類型 {type_label}", fg="text")
        lines = wrap_text(card.get("description", ""), layout.RIGHT_PANEL_CONTENT_WIDTH)
        for i, line in enumerate(lines):
            draw_keyword_text(grid, x, y + 3 + i, line, "text", "keyword")

    # -- 玩家狀態 ---------------------------------------------------------

    def _draw_player_status(self, grid: Grid, player_view: dict) -> None:
        hp = player_view.get("hp", 0)
        max_hp = player_view.get("max_hp", max(hp, 1))
        block = player_view.get("block", 0)
        energy = player_view.get("energy", 0)
        max_energy = max(energy, player_view.get("max_energy", energy))
        draw_pile = len(player_view.get("draw_pile", []))
        discard = len(player_view.get("discard", []))

        hit_flash = self.fx.flash_on(PLAYER_HIT)
        text_color = "hp" if hit_flash else "text"
        block_color = "hp" if hit_flash else ("highlight" if self.fx.flash_on(PLAYER_BLOCK_GAIN) else "block")

        x = layout.LEFT_CONTENT_START + 1
        x = draw_text(
            grid, x, layout.PLAYER_STATUS_ROW, f"[ {player_view.get('name', '冒險者')} ]  HP ", fg=text_color
        )
        draw_hp_bar(grid, x, layout.PLAYER_STATUS_ROW, 20, hp, max_hp, lag_current=self.fx.hp_lag_value("player"))
        x = draw_text(grid, x + 21, layout.PLAYER_STATUS_ROW, f"{hp}/{max_hp}", fg=text_color)
        x = draw_text(grid, x + 4, layout.PLAYER_STATUS_ROW, f"盾 {block}", fg=block_color)
        x = draw_text(grid, x + 4, layout.PLAYER_STATUS_ROW, "能量 ", fg=text_color)
        x = draw_energy_pips(grid, x, layout.PLAYER_STATUS_ROW, energy, max_energy)
        draw_text(grid, x + 4, layout.PLAYER_STATUS_ROW, f"牌堆 {draw_pile} / 棄牌 {discard}", fg=text_color)

        self._draw_damage_numbers(grid, "player", layout.PLAYER_DAMAGE_NUMBER_X, layout.PLAYER_DAMAGE_NUMBER_Y)

    # -- 手牌 -------------------------------------------------------------

    def _draw_hand(self, grid: Grid, player_view: dict) -> None:
        hand = player_view.get("hand", [])
        for i, card in enumerate(hand[: layout.CARD_MAX_COUNT]):
            playable = self._card_playable_for_display(i)
            selected = i == self.selected_index
            y = layout.HAND_ROW_TOP + (layout.SELECTED_CARD_ROW_OFFSET if selected else 0)
            draw_card(
                grid,
                layout.card_slot_x(i),
                y,
                name=card.get("name", "?"),
                cost=card.get("cost", 0),
                card_type=card.get("type", "attack"),
                description=card.get("description", ""),
                playable=playable,
                highlighted=selected or (i == self.inspect_index),
            )
        self._draw_end_turn_button(grid)

    def _draw_flying_card(self, grid: Grid) -> None:
        """出牌飛出：卡片打出的當下記下卡面內容跟原本的位置，往上飛出畫面再消失，
        跟目前的手牌清單無關（那張卡此時已經從手牌移除了）。"""
        fly = self.fx.card_fly
        if fly is None:
            return
        draw_card(
            grid,
            fly.x,
            fly.current_y,
            name=fly.card.get("name", "?"),
            cost=fly.card.get("cost", 0),
            card_type=fly.card.get("type", "attack"),
            description=fly.card.get("description", ""),
            playable=True,
        )

    def _card_playable_for_display(self, index: int) -> bool:
        """畫面上要不要把卡片畫成灰階；這裡失敗就保守顯示成可以使用，
        真正出牌時 can_play 出錯還是會照常跳出錯誤面板。"""
        try:
            return self.bridge.can_play(self.player, index)
        except ModCallError:
            return True

    def _draw_end_turn_button(self, grid: Grid) -> None:
        draw_button(
            grid,
            layout.END_TURN_BUTTON_X,
            layout.END_TURN_BUTTON_Y,
            layout.END_TURN_BUTTON_WIDTH,
            layout.END_TURN_BUTTON_HEIGHT,
            "結束回合",
            key_hint="[E]",
            hovered=self.end_turn_hovered,
        )

    # -- 操作提示 ---------------------------------------------------------

    def _draw_hint(self, grid: Grid) -> None:
        if self.supports_mouse:
            return  # 滑鼠版有結束回合按鈕跟卡牌懸停可以用，不需要額外的文字提示
        hint = "[1-7] 出牌        [E] 結束回合        [?N] 檢視卡牌        [?] 取消檢視"
        hint_x = max(0, (layout.SCREEN_WIDTH - text_width(hint)) // 2)
        draw_text(grid, hint_x, layout.HINT_ROW, hint, fg="dim")

    # -- 錯誤面板 ---------------------------------------------------------

    def _draw_error_panel(self, grid: Grid) -> None:
        raw_lines = self.fatal_error.panel_lines() if self.fatal_error else ["發生未知錯誤。"]
        inner_width = ERROR_PANEL_WIDTH - 4
        wrapped_lines: list[str] = []
        for line in raw_lines:
            wrapped_lines.extend(wrap_text(line, inner_width) or [""])

        title = "發生錯誤（已安全接住，可以繼續遊戲）" if self.error_recoverable else "發生嚴重錯誤"
        h = min(28, len(wrapped_lines) + 6)
        x = (layout.SCREEN_WIDTH - ERROR_PANEL_WIDTH) // 2
        y = 2

        draw_box(grid, x, y, ERROR_PANEL_WIDTH, h, fg="hp", style="double", title=title)
        for row, line in enumerate(wrapped_lines[: h - 5]):
            draw_text(grid, x + 2, y + 2 + row, line, fg="text")

        prompt = "按 Enter 繼續出牌" if self.error_recoverable else "按 Enter 結束這場戰鬥"
        draw_text(grid, x + 2, y + h - 2, prompt, fg="dim")
