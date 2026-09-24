from pathlib import Path

import pytest

from engine.bridge import Bridge, ModCallError, RulesReloadError

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _bridge(name: str) -> Bridge:
    return Bridge(FIXTURES / name)


# ---------------------------------------------------------------------------
# 函式拋出例外：要能從 traceback 裡找到 mod 檔案中「最深」的那個 frame
# ---------------------------------------------------------------------------


def test_exception_reports_function_name_and_type():
    bridge = _bridge("rules_exception.py")
    player = {"hand": [{"damage": 6}]}
    enemy = {"hp": 10}
    with pytest.raises(ModCallError) as exc_info:
        bridge.play_card(player, enemy, 0)
    err = exc_info.value
    assert err.function_name == "play_card"
    assert err.exc is not None
    assert type(err.exc).__name__ == "KeyError"


def test_exception_reports_deepest_mod_frame_not_engine_frame():
    """例外是在巢狀函式 _apply_damage 裡拋出的，面板要顯示那一行，不是 play_card 呼叫它的那一行。"""
    bridge = _bridge("rules_exception.py")
    player = {"hand": [{"damage": 6}]}
    enemy = {"hp": 10}
    with pytest.raises(ModCallError) as exc_info:
        bridge.play_card(player, enemy, 0)
    err = exc_info.value
    assert err.file_path is not None
    assert "tests/fixtures/rules_exception.py" in err.file_path
    assert err.line_number == 7  # enemy["hp"] = enemy["hp"] - card["damage_that_does_not_exist"]
    assert 'card["damage_that_does_not_exist"]' in err.source_line


def test_exception_panel_lines_are_readable_chinese():
    bridge = _bridge("rules_exception.py")
    player = {"hand": [{"damage": 6}]}
    enemy = {"hp": 10}
    with pytest.raises(ModCallError) as exc_info:
        bridge.play_card(player, enemy, 0)
    lines = exc_info.value.panel_lines()
    joined = "\n".join(lines)
    assert "函式：play_card" in joined
    assert "例外類型：KeyError" in joined
    assert "位置：tests/fixtures/rules_exception.py，第 7 行" in joined
    assert "程式碼：" in joined
    assert "play_card 執行時發生錯誤" in joined


# ---------------------------------------------------------------------------
# 回傳錯誤型別
# ---------------------------------------------------------------------------


def test_can_play_wrong_return_type():
    bridge = _bridge("rules_wrong_types.py")
    with pytest.raises(ModCallError) as exc_info:
        bridge.can_play({}, 0)
    assert "can_play 應該回傳布林值" in str(exc_info.value)
    assert "'yes'" in str(exc_info.value)


def test_play_card_wrong_return_type():
    bridge = _bridge("rules_wrong_types.py")
    with pytest.raises(ModCallError) as exc_info:
        bridge.play_card({}, {}, 0)
    assert "play_card 應該回傳字串，但回傳了 None" in str(exc_info.value)


def test_enemy_act_wrong_return_type():
    bridge = _bridge("rules_wrong_types.py")
    with pytest.raises(ModCallError) as exc_info:
        bridge.enemy_act({}, {})
    assert "enemy_act 應該回傳字串" in str(exc_info.value)


def test_check_result_wrong_return_type():
    bridge = _bridge("rules_wrong_types.py")
    with pytest.raises(ModCallError) as exc_info:
        bridge.check_result({}, {})
    assert 'check_result 應該回傳 "win"、"lose" 或 None' in str(exc_info.value)
    assert "'draw'" in str(exc_info.value)


def test_get_enemy_intent_wrong_return_type():
    bridge = _bridge("rules_wrong_types.py")
    with pytest.raises(ModCallError) as exc_info:
        bridge.get_enemy_intent({})
    assert "get_enemy_intent 應該回傳 dict" in str(exc_info.value)


def test_create_player_wrong_return_type():
    bridge = _bridge("rules_wrong_types.py")
    with pytest.raises(ModCallError) as exc_info:
        bridge.create_player([])
    assert "create_player 應該回傳 dict" in str(exc_info.value)


def test_create_enemy_wrong_return_type():
    bridge = _bridge("rules_wrong_types.py")
    with pytest.raises(ModCallError) as exc_info:
        bridge.create_enemy({})
    assert "create_enemy 應該回傳 dict" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 缺少必要函式
# ---------------------------------------------------------------------------


def test_missing_required_function_raises_clear_error():
    bridge = _bridge("rules_missing_functions.py")
    with pytest.raises(ModCallError) as exc_info:
        bridge.play_card({}, {}, 0)
    err = exc_info.value
    assert err.function_name == "play_card"
    assert "沒有實作 play_card" in err.explanation
    assert err.file_path is not None
    assert "tests/fixtures/rules_missing_functions.py" in err.file_path


def test_missing_function_does_not_crash_the_process():
    """引擎絕對不能因為 mod 缺函式而崩潰，只會拋出可以攔截的 ModCallError。"""
    bridge = _bridge("rules_missing_functions.py")
    try:
        bridge.play_card({}, {}, 0)
    except ModCallError:
        pass
    else:
        pytest.fail("應該要拋出 ModCallError")


# ---------------------------------------------------------------------------
# 回傳的 dict 缺少必要欄位
# ---------------------------------------------------------------------------


def test_create_player_missing_fields():
    bridge = _bridge("rules_missing_fields.py")
    with pytest.raises(ModCallError) as exc_info:
        bridge.create_player([])
    msg = str(exc_info.value)
    assert "create_player 回傳的資料缺少必要欄位" in msg
    for field in ("max_hp", "block", "energy", "draw_pile", "hand", "discard"):
        assert field in msg
    assert "name" not in msg.split("：")[-1].split("、")  # name 有給，不該被列為缺少


def test_create_enemy_missing_fields():
    bridge = _bridge("rules_missing_fields.py")
    with pytest.raises(ModCallError) as exc_info:
        bridge.create_enemy({"full_id": "core:slime", "hp": 25})
    msg = str(exc_info.value)
    assert "create_enemy 回傳的資料缺少必要欄位" in msg
    assert "name" in msg
    assert "actions" in msg


# ---------------------------------------------------------------------------
# hook（on_battle_start 等）沒實作時直接跳過，不是錯誤
# ---------------------------------------------------------------------------


def test_call_hook_skips_silently_when_not_implemented():
    bridge = _bridge("rules_missing_functions.py")
    bridge.call_hook("on_battle_start", {}, {})  # 不應該拋出例外


def test_call_hook_wraps_exception_like_other_calls(tmp_path):
    rules_file = tmp_path / "rules.py"
    rules_file.write_text(
        "def on_turn_start(player):\n"
        "    raise RuntimeError('钩子壞了')\n",
        encoding="utf-8",
    )
    bridge = Bridge(rules_file)
    with pytest.raises(ModCallError) as exc_info:
        bridge.call_hook("on_turn_start", {})
    assert exc_info.value.function_name == "on_turn_start"


# ---------------------------------------------------------------------------
# player_view / enemy_view：dict 與 to_dict() 兩種介面
# ---------------------------------------------------------------------------


def test_player_view_returns_dict_directly():
    bridge = _bridge("rules_missing_functions.py")
    player = {"name": "x", "hp": 1}
    assert bridge.player_view(player) is player


class _FakeObjectPlayer:
    def to_dict(self):
        return {"name": "class 介面玩家", "hp": 10}


def test_player_view_supports_to_dict_interface():
    bridge = _bridge("rules_missing_functions.py")
    view = bridge.player_view(_FakeObjectPlayer())
    assert view == {"name": "class 介面玩家", "hp": 10}


def test_enemy_view_returns_dict_directly():
    bridge = _bridge("rules_missing_functions.py")
    enemy = {"name": "x", "hp": 1}
    assert bridge.enemy_view(enemy) is enemy


class _FakeObjectEnemy:
    def to_dict(self):
        return {"name": "class 介面敵人", "hp": 20}


def test_enemy_view_supports_to_dict_interface():
    bridge = _bridge("rules_missing_functions.py")
    view = bridge.enemy_view(_FakeObjectEnemy())
    assert view == {"name": "class 介面敵人", "hp": 20}


# ---------------------------------------------------------------------------
# reload()：重新從磁碟載入 rules.py
# ---------------------------------------------------------------------------


def test_reload_picks_up_file_changes(tmp_path):
    rules_file = tmp_path / "rules.py"
    rules_file.write_text("def can_play(player, hand_index):\n    return True\n", encoding="utf-8")
    bridge = Bridge(rules_file)
    assert bridge.can_play({}, 0) is True

    rules_file.write_text("def can_play(player, hand_index):\n    return False\n", encoding="utf-8")
    bridge.reload()
    assert bridge.can_play({}, 0) is False


def test_reload_with_syntax_error_raises_and_keeps_old_rules(tmp_path):
    rules_file = tmp_path / "rules.py"
    rules_file.write_text("def can_play(player, hand_index):\n    return True\n", encoding="utf-8")
    bridge = Bridge(rules_file)
    assert bridge.can_play({}, 0) is True

    rules_file.write_text("def can_play(player, hand_index):\n    return (((\n", encoding="utf-8")
    with pytest.raises(RulesReloadError):
        bridge.reload()

    # 重載失敗，繼續用重載前那個還能正常運作的版本
    assert bridge.can_play({}, 0) is True


def test_reload_with_import_error_raises_and_keeps_old_rules(tmp_path):
    rules_file = tmp_path / "rules.py"
    rules_file.write_text("def can_play(player, hand_index):\n    return True\n", encoding="utf-8")
    bridge = Bridge(rules_file)

    rules_file.write_text("import this_module_does_not_exist\n", encoding="utf-8")
    with pytest.raises(RulesReloadError) as exc_info:
        bridge.reload()
    assert "重新載入 rules.py 失敗" in str(exc_info.value)
    assert bridge.can_play({}, 0) is True


def test_reload_failure_message_does_not_crash_process(tmp_path):
    """引擎不能因為熱重載失敗而崩潰：例外要能被攔截，不會是未處理的例外。"""
    rules_file = tmp_path / "rules.py"
    rules_file.write_text("def can_play(player, hand_index):\n    return True\n", encoding="utf-8")
    bridge = Bridge(rules_file)
    rules_file.write_text("raise RuntimeError('壞掉了')\n", encoding="utf-8")
    try:
        bridge.reload()
    except RulesReloadError:
        pass
    else:
        pytest.fail("應該要拋出 RulesReloadError")
    assert bridge.can_play({}, 0) is True
