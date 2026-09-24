from pathlib import Path

from engine import layout
from engine.actions import Back, ClickCard, Confirm, EndTurn, HoverEndTurn, Inspect, PlayCard, Reload
from engine.bridge import Bridge
from engine.fx import ENEMY_HIT, INTENT_CHANGE, PLAYER_BLOCK_GAIN, PLAYER_HIT, SCREEN_SHAKE, SCREEN_SHAKE_THRESHOLD
from engine.grid import Grid, plain_lines
from engine.scenes.battle import STATE_PLAYER_TURN, STATE_SHOWING_ERROR, BattleScene

REAL_RULES_PATH = Path(__file__).resolve().parent.parent / "mods" / "core" / "rules.py"


def _player(draw_pile, *, hp=50):
    return {
        "name": "測試玩家",
        "hp": hp,
        "max_hp": 50,
        "block": 0,
        "energy": 3,
        "draw_pile": list(draw_pile),
        "hand": [],
        "discard": [],
    }


def _enemy(hp=10, actions=None):
    return {
        "id": "core:test_dummy",
        "name": "測試假人",
        "hp": hp,
        "max_hp": hp,
        "block": 0,
        "actions": actions or [{"type": "attack", "value": 3}],
        "action_index": 0,
        "art": ["( x )"],
        "color": "white",
    }


def _card(**overrides):
    card = {"id": "test_card", "name": "測試卡", "cost": 1, "type": "attack", "description": "測試用卡片。"}
    card.update(overrides)
    return card


def _bridge():
    return Bridge(REAL_RULES_PATH)


# ---------------------------------------------------------------------------
# 開場與抽牌
# ---------------------------------------------------------------------------


def test_battle_starts_in_player_turn_with_hand_drawn_from_draw_pile():
    card = _card(damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy())
    assert scene.state == STATE_PLAYER_TURN
    assert scene.player["hand"] == [card]
    assert scene.player["draw_pile"] == []


# ---------------------------------------------------------------------------
# 出牌造成傷害、分出勝負
# ---------------------------------------------------------------------------


def test_play_card_deals_damage_and_wins_when_enemy_dies():
    card = _card(damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=5))
    scene.handle([PlayCard(0)])
    assert scene.enemy["hp"] == 0
    assert scene.result == "win"
    # finished 要等敵人死亡動畫播完才會設成 True（見「敵人死亡」一節）。
    scene.update(999)
    assert scene.finished is True
    assert any("獲勝" in m for m in scene.battle_log)


def test_play_card_appends_returned_message_to_battle_log():
    card = _card(damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99))
    scene.handle([PlayCard(0)])
    assert any("造成 5 點傷害" in m for m in scene.battle_log)


def test_play_card_out_of_range_is_ignored_gracefully():
    scene = BattleScene(_bridge(), _player([]), _enemy())
    scene.handle([PlayCard(3)])
    assert scene.state == STATE_PLAYER_TURN
    assert scene.fatal_error is None


# ---------------------------------------------------------------------------
# 結束回合、敵人行動、戰敗
# ---------------------------------------------------------------------------


def test_end_turn_runs_enemy_action_and_advances_turn_counter():
    scene = BattleScene(_bridge(), _player([]), _enemy(hp=99, actions=[{"type": "attack", "value": 7}]))
    assert scene.turn == 1
    scene.handle([EndTurn()])
    assert scene.player["hp"] == 43  # 50 - 7
    assert scene.turn == 2
    assert any("攻擊" in m for m in scene.battle_log)


def test_loses_when_enemy_attack_reduces_player_hp_to_zero():
    scene = BattleScene(_bridge(), _player([], hp=3), _enemy(hp=99, actions=[{"type": "attack", "value": 5}]))
    scene.handle([EndTurn()])
    assert scene.result == "lose"
    assert scene.finished is True


# ---------------------------------------------------------------------------
# 沒被處理的欄位（hits、draw）不能讓遊戲出錯
# ---------------------------------------------------------------------------


def test_card_with_hits_field_not_handled_by_rules_does_not_crash():
    card = _card(id="flurry_like", name="連斬", damage=3, hits=3)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99))
    scene.handle([PlayCard(0)])
    assert scene.fatal_error is None
    assert scene.state == STATE_PLAYER_TURN
    assert scene.enemy["hp"] == 96  # hits 被忽略，只扣一次 damage


def test_card_with_draw_field_not_handled_by_rules_does_not_crash():
    card = _card(id="insight_like", name="洞察", cost=0, draw=2)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99))
    scene.handle([PlayCard(0)])
    assert scene.fatal_error is None
    assert scene.state == STATE_PLAYER_TURN


# ---------------------------------------------------------------------------
# Inspect：檢視卡牌詳細資訊
# ---------------------------------------------------------------------------


def test_inspect_sets_and_clears_index():
    card = _card(name="測試卡")
    scene = BattleScene(_bridge(), _player([card]), _enemy())
    scene.handle([Inspect(0)])
    assert scene.inspect_index == 0
    scene.handle([Inspect(None)])
    assert scene.inspect_index is None


def test_inspect_out_of_range_clears_index():
    scene = BattleScene(_bridge(), _player([]), _enemy())
    scene.handle([Inspect(5)])
    assert scene.inspect_index is None


def test_back_action_clears_inspect_index():
    card = _card(name="測試卡")
    scene = BattleScene(_bridge(), _player([card]), _enemy())
    scene.handle([Inspect(0)])
    scene.handle([Back()])
    assert scene.inspect_index is None


def test_draw_shows_card_detail_in_right_panel_when_inspecting():
    card = _card(name="測試卡", description="這是描述。")
    scene = BattleScene(_bridge(), _player([card]), _enemy())
    scene.handle([Inspect(0)])
    grid = Grid()
    scene.draw(grid)
    lines = plain_lines(grid)
    assert any("測試卡" in line for line in lines)
    assert any("這是描述" in line for line in lines)


# ---------------------------------------------------------------------------
# 出牌時發生錯誤：可以復原，取消這次出牌，繼續戰鬥
# ---------------------------------------------------------------------------


def test_play_card_bridge_error_is_recoverable_and_resumes_battle():
    card = _card(damage=5)
    bridge = _bridge()
    bridge.rules.play_card = lambda player, enemy, hand_index: (_ for _ in ()).throw(ValueError("壞掉的卡牌效果"))

    scene = BattleScene(bridge, _player([card]), _enemy(hp=99))
    scene.handle([PlayCard(0)])

    assert scene.state == STATE_SHOWING_ERROR
    assert scene.error_recoverable is True
    assert scene.fatal_error is not None
    assert "play_card" in scene.fatal_error.function_name

    scene.handle([Confirm()])
    assert scene.state == STATE_PLAYER_TURN
    assert scene.fatal_error is None
    assert scene.finished is False


def test_error_panel_is_drawn_and_dismissable():
    card = _card(damage=5)
    bridge = _bridge()
    bridge.rules.play_card = lambda player, enemy, hand_index: (_ for _ in ()).throw(ValueError("壞掉的卡牌效果"))
    scene = BattleScene(bridge, _player([card]), _enemy(hp=99))
    scene.handle([PlayCard(0)])

    grid = Grid()
    scene.draw(grid)
    lines = plain_lines(grid)
    assert any("play_card" in line for line in lines)
    assert any("ValueError" in line for line in lines)


# ---------------------------------------------------------------------------
# 戰鬥流程出錯（不是出牌）：不能復原，安全結束這場戰鬥
# ---------------------------------------------------------------------------


def test_battle_flow_error_is_fatal_and_ends_battle_safely():
    bridge = _bridge()
    scene = BattleScene(bridge, _player([]), _enemy(hp=99, actions=[{"type": "attack", "value": 3}]))
    bridge.rules.enemy_act = lambda enemy, player: (_ for _ in ()).throw(RuntimeError("戰鬥流程壞掉了"))

    scene.handle([EndTurn()])
    assert scene.state == STATE_SHOWING_ERROR
    assert scene.error_recoverable is False

    scene.handle([Confirm()])
    assert scene.finished is True
    assert scene.result is None  # 不是正常的勝負，是被迫中止


def test_missing_required_function_ends_battle_safely_without_crashing():
    bridge = _bridge()
    del bridge.rules.check_result
    scene = BattleScene(bridge, _player([]), _enemy(hp=99))
    # __init__ 裡就會呼叫 check_result，應該已經進入錯誤畫面而不是丟出例外
    assert scene.state == STATE_SHOWING_ERROR
    assert scene.error_recoverable is False
    assert "check_result" in scene.fatal_error.function_name


# ---------------------------------------------------------------------------
# fx：效果由引擎比較 bridge 呼叫前後的 view 差異自動產生
# ---------------------------------------------------------------------------


def test_playing_damage_card_triggers_enemy_hit_fx():
    card = _card(damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.is_active(ENEMY_HIT) is True


def test_playing_block_card_triggers_player_block_gain_fx():
    card = _card(id="defend_like", name="防禦", block=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.is_active(PLAYER_BLOCK_GAIN) is True


def test_enemy_attack_triggers_player_hit_fx():
    scene = BattleScene(
        _bridge(), _player([]), _enemy(hp=99, actions=[{"type": "attack", "value": 5}]), supports_animation=True
    )
    scene.handle([EndTurn()])
    assert scene.fx.is_active(PLAYER_HIT) is True


def test_fx_blocks_further_input_until_it_expires():
    card = _card(damage=5)
    scene = BattleScene(_bridge(), _player([card, card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.is_playing is True
    hand_len_during_fx = len(scene.player["hand"])

    # fx 播放期間輸入被忽略，手牌不會變
    scene.handle([PlayCard(0)])
    assert len(scene.player["hand"]) == hand_len_during_fx

    scene.update(10.0)  # 讓效果播完
    assert scene.fx.is_playing is False
    scene.handle([PlayCard(0)])
    assert len(scene.player["hand"]) == hand_len_during_fx - 1


def test_terminal_mode_never_queues_fx():
    card = _card(damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=False)
    scene.handle([PlayCard(0)])
    assert scene.fx.is_playing is False


def test_update_advances_fx_timers():
    card = _card(damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.is_playing is True
    scene.update(10.0)
    assert scene.fx.is_playing is False


def test_draw_applies_enemy_shake_and_flash_color_while_hit_fx_active():
    card = _card(damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99, actions=[{"type": "attack", "value": 1}]),
                         supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.is_active(ENEMY_HIT) is True

    grid = Grid()
    scene.draw(grid)
    # 敵人圖的顏色應該變成 hp（閃紅）而不是原本的 color
    from engine import layout

    # x=0 是主框的左邊框（frame 色），敵人圖從 x=1 開始找第一個非空白字元。
    first_char_x = next(
        x for x in range(1, grid.width) if grid.get(x, layout.ENEMY_ART_TOP).char not in (" ", "")
    )
    assert grid.get(first_char_x, layout.ENEMY_ART_TOP).fg == "hp"


# ---------------------------------------------------------------------------
# Reload（F5）：隨時可以按，包含 fx 播放中與錯誤畫面
# ---------------------------------------------------------------------------


def test_reload_sets_flag_even_while_fx_playing():
    card = _card(damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.is_playing is True
    scene.handle([Reload()])
    assert scene.reload_requested is True


def test_reload_sets_flag_even_while_showing_error():
    bridge = _bridge()
    bridge.rules.play_card = lambda player, enemy, hand_index: (_ for _ in ()).throw(ValueError("boom"))
    card = _card(damage=5)
    scene = BattleScene(bridge, _player([card]), _enemy(hp=99))
    scene.handle([PlayCard(0)])
    assert scene.state == STATE_SHOWING_ERROR
    scene.handle([Reload()])
    assert scene.reload_requested is True


# ---------------------------------------------------------------------------
# 手牌兩段式點擊：第一下選取、第二下出牌
# ---------------------------------------------------------------------------


def test_click_card_first_time_selects_and_shows_detail():
    card = _card(damage=5, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99))
    scene.handle([ClickCard(0)])
    assert scene.selected_index == 0
    assert scene.inspect_index == 0
    assert scene.enemy["hp"] == 99  # 還沒出牌


def test_click_card_second_time_plays_it():
    card = _card(damage=5, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99))
    scene.handle([ClickCard(0)])
    scene.handle([ClickCard(0)])
    assert scene.enemy["hp"] == 94
    assert scene.selected_index is None
    assert any("造成 5 點傷害" in m for m in scene.battle_log)


def test_click_different_card_switches_selection():
    card_a = _card(id="a", damage=1, cost=1)
    card_b = _card(id="b", damage=1, cost=1)
    scene = BattleScene(_bridge(), _player([card_a, card_b]), _enemy(hp=99))
    scene.handle([ClickCard(0)])
    assert scene.selected_index == 0
    scene.handle([ClickCard(1)])
    assert scene.selected_index == 1
    assert scene.enemy["hp"] == 99  # 換選取，還沒出牌


def test_click_unaffordable_card_shows_detail_but_cannot_select_or_play():
    expensive_card = _card(damage=5, cost=99)  # 玩家能量只有 3，打不起
    scene = BattleScene(_bridge(), _player([expensive_card]), _enemy(hp=99))
    scene.handle([ClickCard(0)])
    assert scene.inspect_index == 0
    assert scene.selected_index is None

    # 再點一次同一張卡：因為從來沒有真的「選取」成功，這裡還是第一下的行為，不會出牌
    scene.handle([ClickCard(0)])
    assert scene.selected_index is None
    assert scene.enemy["hp"] == 99
    assert scene.player["energy"] == 3  # 完全沒有扣能量


def test_click_blank_deselects():
    card = _card(damage=5, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99))
    scene.handle([ClickCard(0)])
    assert scene.selected_index == 0

    scene.handle([ClickCard(None)])
    assert scene.selected_index is None
    assert scene.inspect_index is None


def test_esc_deselects():
    card = _card(damage=5, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99))
    scene.handle([ClickCard(0)])
    scene.handle([Back()])
    assert scene.selected_index is None
    assert scene.inspect_index is None


def test_click_out_of_range_index_deselects():
    scene = BattleScene(_bridge(), _player([]), _enemy(hp=99))
    scene.handle([ClickCard(5)])
    assert scene.selected_index is None


def test_number_key_play_resets_stale_mouse_selection():
    """驗收條件：數字鍵一律直接出牌；出牌後任何滑鼠選取狀態都要清掉，不會殘留指到錯的手牌索引。"""
    card_a = _card(id="a", damage=1, cost=1)
    card_b = _card(id="b", damage=1, cost=1)
    scene = BattleScene(_bridge(), _player([card_a, card_b]), _enemy(hp=99))
    scene.handle([ClickCard(1)])
    assert scene.selected_index == 1
    scene.handle([PlayCard(0)])  # 數字鍵直接出第一張牌，不管選取狀態
    assert scene.selected_index is None


def test_fx_playing_blocks_click_card():
    card = _card(damage=5, cost=1)
    scene = BattleScene(_bridge(), _player([card, card]), _enemy(hp=99), supports_animation=True)
    scene.handle([ClickCard(0)])
    scene.handle([ClickCard(0)])  # 出牌，觸發 enemy_hit 效果
    assert scene.fx.is_playing is True

    scene.handle([ClickCard(0)])  # 效果播放中，這次點擊應該被忽略
    assert scene.enemy["hp"] == 94  # 沒有再扣一次血


# ---------------------------------------------------------------------------
# 結束回合按鈕：滑鼠移上去 highlight、點擊等於 EndTurn
# ---------------------------------------------------------------------------


def test_hover_end_turn_sets_flag():
    scene = BattleScene(_bridge(), _player([]), _enemy(hp=99))
    assert scene.end_turn_hovered is False
    scene.handle([HoverEndTurn(True)])
    assert scene.end_turn_hovered is True
    scene.handle([HoverEndTurn(False)])
    assert scene.end_turn_hovered is False


def test_draw_end_turn_button_exists_and_highlights_on_hover():
    scene = BattleScene(_bridge(), _player([]), _enemy(hp=99, actions=[{"type": "attack", "value": 1}]))
    grid = Grid()
    scene.draw(grid)
    assert grid.get(layout.END_TURN_BUTTON_X, layout.END_TURN_BUTTON_Y).char == "╔"
    assert grid.get(layout.END_TURN_BUTTON_X, layout.END_TURN_BUTTON_Y).fg == "frame"

    scene.handle([HoverEndTurn(True)])
    grid2 = Grid()
    scene.draw(grid2)
    assert grid2.get(layout.END_TURN_BUTTON_X, layout.END_TURN_BUTTON_Y).fg == "highlight"


# ---------------------------------------------------------------------------
# 畫面：選取的卡片整張上移一格、pygame 版不畫列 31 提示、終端機版保留提示
# ---------------------------------------------------------------------------


def test_draw_shifts_selected_card_up_by_one_row():
    card = _card(damage=5, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99))
    scene.handle([ClickCard(0)])

    grid = Grid()
    scene.draw(grid)
    x = layout.card_slot_x(0)
    assert grid.get(x, layout.HAND_ROW_TOP - 1).char == "╔"  # 上移後，卡片頂端出現在原本上面那一列
    assert grid.get(x, layout.HAND_ROW_TOP).char != "╔"  # 原本的位置已經不是卡片頂端了


def test_draw_unselected_card_stays_at_normal_row():
    card = _card(damage=5, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99))
    grid = Grid()
    scene.draw(grid)
    x = layout.card_slot_x(0)
    assert grid.get(x, layout.HAND_ROW_TOP).char == "╔"


def test_hint_row_hidden_when_supports_mouse():
    scene = BattleScene(_bridge(), _player([]), _enemy(hp=99), supports_mouse=True)
    grid = Grid()
    scene.draw(grid)
    assert plain_lines(grid)[layout.HINT_ROW].strip() == ""


def test_hint_row_shown_when_not_supports_mouse():
    scene = BattleScene(_bridge(), _player([]), _enemy(hp=99), supports_mouse=False)
    grid = Grid()
    scene.draw(grid)
    assert "出牌" in plain_lines(grid)[layout.HINT_ROW]


# ---------------------------------------------------------------------------
# 傷害數字彈出：扣血用 hp 色，被護盾吸收的量用 block 色
# ---------------------------------------------------------------------------


def test_playing_damage_card_spawns_hp_colored_number_on_enemy():
    card = _card(damage=6, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    numbers = scene.fx.numbers_for("enemy")
    assert len(numbers) == 1
    assert numbers[0].amount == 6
    assert numbers[0].color == "hp"


def test_enemy_attack_absorbed_by_block_spawns_block_colored_number():
    scene = BattleScene(
        _bridge(), _player([]), _enemy(hp=99, actions=[{"type": "attack", "value": 5}]), supports_animation=True
    )
    scene.player["block"] = 5  # 建立 scene 時 start_turn 已經把 block 重置過，要在這裡才設得上
    scene.handle([EndTurn()])
    numbers = scene.fx.numbers_for("player")
    assert len(numbers) == 1
    assert numbers[0].amount == 5
    assert numbers[0].color == "block"
    assert scene.player["hp"] == 50  # 完全被護盾吸收，沒有扣血


def test_enemy_attack_partially_absorbed_spawns_both_numbers():
    scene = BattleScene(
        _bridge(), _player([]), _enemy(hp=99, actions=[{"type": "attack", "value": 8}]), supports_animation=True
    )
    scene.player["block"] = 3
    scene.handle([EndTurn()])
    numbers = {(n.amount, n.color) for n in scene.fx.numbers_for("player")}
    assert numbers == {(5, "hp"), (3, "block")}


def test_draw_shows_damage_number_near_enemy_hp_row():
    card = _card(damage=6, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    grid = Grid()
    scene.draw(grid)
    lines = plain_lines(grid)
    assert any("-6" in line for line in lines)


def test_terminal_mode_never_spawns_damage_numbers():
    card = _card(damage=6, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=False)
    scene.handle([PlayCard(0)])
    assert scene.fx.numbers_for("enemy") == []


# ---------------------------------------------------------------------------
# 延遲血條：血條先快速掉到新值，殘影慢慢追上
# ---------------------------------------------------------------------------


def test_playing_damage_card_starts_hp_lag_on_enemy():
    card = _card(damage=6, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=20), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.enemy["hp"] == 14
    assert scene.fx.hp_lag_value("enemy") == 20  # 殘影還停在舊值，血條本身已經是新值


def test_draw_hp_bar_ghost_segment_visible_right_after_hit():
    card = _card(damage=6, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=20), supports_animation=True)
    scene.handle([PlayCard(0)])
    grid = Grid()
    scene.draw(grid)
    hp_x = layout.LEFT_CONTENT_START + 15 + 3
    row = [grid.get(hp_x + i, layout.ENEMY_HP_ROW) for i in range(20)]
    assert any(cell.fg == "dim" for cell in row)  # 殘影用 dim 色


def test_heal_does_not_start_hp_lag():
    card = _card(heal=6, cost=1)
    scene = BattleScene(_bridge(), _player([card], hp=30), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.hp_lag_value("player") is None


# ---------------------------------------------------------------------------
# 動畫可跳過：播放期間任何輸入都立刻快轉到結果狀態（不是取消）
# ---------------------------------------------------------------------------


def test_any_input_during_fx_skips_to_end_immediately():
    card = _card(damage=6, cost=1)
    scene = BattleScene(_bridge(), _player([card, card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.is_playing is True

    scene.handle([PlayCard(0)])  # 播放中按任意鍵：快轉，不是真的出牌
    assert scene.fx.is_playing is False
    assert scene.enemy["hp"] == 93  # 只扣了第一次的傷害，這次輸入沒有被當成出牌


def test_skip_via_click_also_works():
    card = _card(damage=6, cost=1)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.is_playing is True
    scene.handle([ClickCard(None)])
    assert scene.fx.is_playing is False


def test_next_input_after_skip_is_treated_as_a_normal_action():
    card = _card(damage=6, cost=1)
    scene = BattleScene(_bridge(), _player([card, card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])  # 出第一張牌，觸發效果
    scene.handle([PlayCard(0)])  # 快轉
    assert scene.fx.is_playing is False
    scene.handle([PlayCard(0)])  # 這次是正常輸入，應該真的出牌
    assert scene.enemy["hp"] == 87  # 93 - 6


# ---------------------------------------------------------------------------
# 出牌飛出：卡片打出的當下記下卡面內容跟原本座標，之後往上飛出畫面再消失
# ---------------------------------------------------------------------------


def test_playing_card_starts_card_fly_with_snapshot_and_slot_position():
    card = _card(name="斬擊", damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    fly = scene.fx.card_fly
    assert fly is not None
    assert fly.card["name"] == "斬擊"
    assert fly.x == layout.card_slot_x(0)
    assert fly.y == layout.HAND_ROW_TOP


def test_playing_selected_card_starts_fly_from_the_raised_row():
    """兩段式點擊選取中的卡片畫面上會整張上移一格，出牌飛出動畫要接著從那個位置開始飛，
    不能瞬間跳回沒選取時的列。"""
    card = _card(damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=True)
    scene.handle([ClickCard(0)])  # 第一下選取
    scene.handle([ClickCard(0)])  # 第二下出牌
    fly = scene.fx.card_fly
    assert fly is not None
    assert fly.y == layout.HAND_ROW_TOP + layout.SELECTED_CARD_ROW_OFFSET


def test_terminal_mode_never_starts_card_fly():
    card = _card(damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=False)
    scene.handle([PlayCard(0)])
    assert scene.fx.card_fly is None


def test_draw_shows_flying_card_name_at_its_current_position():
    card = _card(name="斬擊", damage=5)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    fly = scene.fx.card_fly
    grid = Grid()
    scene.draw(grid)
    lines = plain_lines(grid)
    assert "斬擊" in lines[fly.current_y + 1]  # 卡片第 1 列（從 0 開始）畫卡名


def test_card_fly_clears_when_skipped_by_next_input():
    card = _card(damage=5, cost=1)
    scene = BattleScene(_bridge(), _player([card, card]), _enemy(hp=99), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.card_fly is not None
    scene.handle([PlayCard(0)])  # 任意輸入快轉
    assert scene.fx.card_fly is None


# ---------------------------------------------------------------------------
# 敵人死亡：ASCII 圖逐行消失，播完（或被跳過）才真的進入下一個畫面
# ---------------------------------------------------------------------------


def test_enemy_death_starts_when_hp_drops_to_zero():
    card = _card(damage=10)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=5), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.enemy_death_active is True
    assert scene.result == "win"


def test_finished_waits_for_enemy_death_animation_to_complete():
    card = _card(damage=10)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=5), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.finished is False  # 動畫還沒播完，不能直接跳下一個畫面

    scene.update(999)  # 讓動畫播完
    assert scene.fx.enemy_death_active is False
    assert scene.finished is True


def test_enemy_death_animation_can_be_skipped_by_any_input():
    card = _card(damage=10)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=5), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.finished is False

    scene.handle([EndTurn()])  # 任意輸入：快轉動畫
    assert scene.fx.enemy_death_active is False
    assert scene.finished is False  # 要下一次 update() 才會真的把 finished 設成 True

    scene.update(0.0)
    assert scene.finished is True


def test_terminal_mode_finishes_immediately_without_death_animation():
    card = _card(damage=10)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=5), supports_animation=False)
    scene.handle([PlayCard(0)])
    assert scene.fx.enemy_death_active is False
    assert scene.finished is True


def test_draw_uses_shrinking_death_art_instead_of_full_art():
    enemy = _enemy(hp=5, actions=[{"type": "attack", "value": 1}])
    enemy["art"] = ["aaaa", "bbbb", "cccc", "dddd"]
    card = _card(damage=10)
    scene = BattleScene(_bridge(), _player([card]), enemy, supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.enemy_death_art == enemy["art"]  # 剛觸發，還沒開始消失

    scene.update(scene.fx._enemy_death.duration / 2)
    assert scene.fx.enemy_death_art == enemy["art"][:2]

    grid = Grid()
    scene.draw(grid)
    lines = plain_lines(grid)
    assert not any("dddd" in line for line in lines)


# ---------------------------------------------------------------------------
# 頭目大招整面晃動：敵人單次攻擊傷害達到門檻才整面晃，一般攻擊維持只晃受擊方
# ---------------------------------------------------------------------------


def test_enemy_attack_at_threshold_triggers_screen_shake():
    scene = BattleScene(
        _bridge(),
        _player([]),
        _enemy(actions=[{"type": "attack", "value": SCREEN_SHAKE_THRESHOLD}]),
        supports_animation=True,
    )
    scene.handle([EndTurn()])
    assert scene.fx.is_active(SCREEN_SHAKE) is True


def test_enemy_attack_below_threshold_does_not_trigger_screen_shake():
    scene = BattleScene(
        _bridge(),
        _player([]),
        _enemy(actions=[{"type": "attack", "value": SCREEN_SHAKE_THRESHOLD - 1}]),
        supports_animation=True,
    )
    scene.handle([EndTurn()])
    assert scene.fx.is_active(SCREEN_SHAKE) is False
    assert scene.fx.is_active(PLAYER_HIT) is True  # 一般攻擊還是有受擊反應，只是不整面晃


def test_screen_shake_counts_block_absorbed_damage_too():
    """門檻算的是這次攻擊造成的總傷害（打進 hp 的 + 被護盾吸收的），不是只看扣血量。"""
    scene = BattleScene(
        _bridge(),
        _player([]),
        _enemy(actions=[{"type": "attack", "value": SCREEN_SHAKE_THRESHOLD}]),
        supports_animation=True,
    )
    scene.player["block"] = 15  # 15 點被護盾吸收 + 5 點打進 hp，合計等於門檻
    scene.handle([EndTurn()])
    assert scene.fx.is_active(SCREEN_SHAKE) is True


def test_terminal_mode_never_triggers_screen_shake():
    scene = BattleScene(
        _bridge(),
        _player([]),
        _enemy(actions=[{"type": "attack", "value": SCREEN_SHAKE_THRESHOLD}]),
        supports_animation=False,
    )
    scene.handle([EndTurn()])
    assert scene.fx.is_active(SCREEN_SHAKE) is False


def test_playing_card_against_enemy_never_triggers_screen_shake():
    """整面晃動只限敵人攻擊玩家；玩家出牌打敵人不管傷害多高都不觸發。"""
    card = _card(damage=SCREEN_SHAKE_THRESHOLD + 10)
    scene = BattleScene(_bridge(), _player([card]), _enemy(hp=999), supports_animation=True)
    scene.handle([PlayCard(0)])
    assert scene.fx.is_active(SCREEN_SHAKE) is False


def test_draw_shifts_whole_frame_when_screen_shake_active():
    scene = BattleScene(
        _bridge(),
        _player([]),
        _enemy(actions=[{"type": "attack", "value": SCREEN_SHAKE_THRESHOLD}]),
        supports_animation=True,
    )
    scene.handle([EndTurn()])
    dx = scene.fx.shake_offset(SCREEN_SHAKE)
    assert dx == -1  # 剛觸發，抖動序列的第一格

    grid = Grid()
    scene.draw(grid)
    lines = plain_lines(grid)
    # 上框線中間的 ╦ 本來畫在 PANEL_DIVIDER_COL，整面晃動時應該連同其他內容一起位移 dx 格。
    assert lines[layout.FRAME_TOP][layout.PANEL_DIVIDER_COL + dx] == "╦"


# ---------------------------------------------------------------------------
# 意圖變化：敵人切換到下一個行動時，意圖那一行閃一下
# ---------------------------------------------------------------------------


def test_ending_turn_flashes_intent_when_action_changes():
    scene = BattleScene(
        _bridge(),
        _player([]),
        _enemy(actions=[{"type": "attack", "value": 3}, {"type": "block", "value": 4}]),
        supports_animation=True,
    )
    assert scene.fx.is_active(INTENT_CHANGE) is False  # 開場第一次顯示意圖不算「切換」
    scene.handle([EndTurn()])
    assert scene.fx.is_active(INTENT_CHANGE) is True


def test_intent_flash_does_not_trigger_when_action_cycle_has_only_one_action():
    scene = BattleScene(
        _bridge(),
        _player([]),
        _enemy(actions=[{"type": "attack", "value": 3}]),
        supports_animation=True,
    )
    scene.handle([EndTurn()])
    # 只有一種行動，action_index 繞一圈又回到同一格，等於沒有真的「切換」。
    assert scene.fx.is_active(INTENT_CHANGE) is False


def test_terminal_mode_never_flashes_intent():
    scene = BattleScene(
        _bridge(),
        _player([]),
        _enemy(actions=[{"type": "attack", "value": 3}, {"type": "block", "value": 4}]),
        supports_animation=False,
    )
    scene.handle([EndTurn()])
    assert scene.fx.is_active(INTENT_CHANGE) is False


def test_draw_uses_highlight_color_for_intent_while_flashing():
    scene = BattleScene(
        _bridge(),
        _player([]),
        _enemy(actions=[{"type": "attack", "value": 3}, {"type": "block", "value": 4}]),
        supports_animation=True,
    )
    scene.handle([EndTurn()])
    assert scene.fx.flash_on(INTENT_CHANGE) is True

    grid = Grid()
    scene.draw(grid)
    row = layout.ENEMY_INTENT_ROW
    # 只在左面板內容範圍找，避免抓到欄 0/63 的外框字元（跟意圖文字無關，顏色固定是 frame）。
    first_char_x = next(
        x
        for x in range(layout.LEFT_CONTENT_START, layout.LEFT_CONTENT_END + 1)
        if grid.get(x, row).char not in (" ", "")
    )
    assert grid.get(first_char_x, row).fg == "highlight"
