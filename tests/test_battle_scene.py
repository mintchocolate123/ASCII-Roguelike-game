from pathlib import Path

from engine.actions import Back, Confirm, EndTurn, Inspect, PlayCard, Reload
from engine.bridge import Bridge
from engine.fx import ENEMY_HIT, PLAYER_BLOCK_GAIN, PLAYER_HIT
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
