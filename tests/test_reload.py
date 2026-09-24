"""F5 熱重載：重新載入所有 mod 資料與 rules.py，重開目前這場戰鬥；
失敗時要顯示錯誤但不能讓遊戲崩潰，必須能繼續用重新載入前的版本玩下去。
"""
import shutil
from pathlib import Path

import main as main_module
from engine.actions import Confirm, EndTurn, PlayCard, Reload
from engine.mod.loader import load_mods
from engine.scenes.battle import STATE_SHOWING_ERROR, BattleScene
from main import GameController

MODS_DIR = Path(__file__).resolve().parent.parent / "mods"
REAL_RULES_PATH = MODS_DIR / "core" / "rules.py"


def _weak_normal_only_db():
    db, report = load_mods(MODS_DIR)
    normal = {k: v for k, v in db.enemies.items() if v["tier"] == "normal"}
    weakest = min(normal, key=lambda k: normal[k]["hp"])
    db.enemies = {k: v for k, v in db.enemies.items() if v["tier"] != "normal" or k == weakest}
    db.run_stages = [{"type": "battle", "tier": "normal"}]
    return db, report


def _controller():
    db, report = _weak_normal_only_db()
    controller = GameController(db, report, supports_animation=False)
    controller.handle([Confirm()])  # loading -> title
    controller.handle([Confirm()])  # title -> 第一場戰鬥
    return controller


# ---------------------------------------------------------------------------
# 成功重載：重開目前這場戰鬥，不保留舊狀態
# ---------------------------------------------------------------------------


def test_reload_success_creates_fresh_battle_scene():
    controller = _controller()
    old_scene = controller.scene
    assert isinstance(old_scene, BattleScene)

    # 先打一張牌、結束回合，讓狀態跟剛開戰時不一樣
    controller.handle([PlayCard(0)])
    controller.handle([EndTurn()])

    controller.handle([Reload()])

    new_scene = controller.scene
    assert isinstance(new_scene, BattleScene)
    assert new_scene is not old_scene
    assert new_scene.state != STATE_SHOWING_ERROR
    assert new_scene.turn == 1  # 不保留舊的戰鬥狀態，重新從第 1 回合開始
    assert any("已重新載入" in m for m in new_scene.battle_log)


def test_reload_rebuilds_hand_from_deck():
    controller = _controller()
    controller.handle([PlayCard(0)])  # 打掉一張牌，手牌數量改變
    hand_len_before_reload = len(controller.bridge.player_view(controller.scene.player)["hand"])

    controller.handle([Reload()])

    new_hand_len = len(controller.bridge.player_view(controller.scene.player)["hand"])
    assert new_hand_len >= hand_len_before_reload  # 重新抽牌，不會維持打完牌之後的手牌數


# ---------------------------------------------------------------------------
# 重載失敗：mod 資料本身壞掉，繼續用舊版本玩
# ---------------------------------------------------------------------------


def test_reload_with_broken_mods_dir_keeps_old_scene_and_bridge(tmp_path, monkeypatch):
    controller = _controller()
    old_scene = controller.scene
    old_bridge = controller.bridge

    monkeypatch.setattr(main_module, "MODS_DIR", tmp_path)  # 一個沒有 core 的空資料夾
    controller.handle([Reload()])

    assert controller.scene is old_scene
    assert controller.bridge is old_bridge
    assert any("重新載入失敗" in m for m in old_scene.battle_log)

    # 舊版本仍然能正常繼續玩
    assert controller.bridge.can_play(old_scene.player, 0) in (True, False)


# ---------------------------------------------------------------------------
# 重載失敗：rules.py 語法錯誤，繼續用舊版本玩
# ---------------------------------------------------------------------------


def test_reload_with_syntax_error_in_rules_keeps_old_scene_and_bridge(tmp_path, monkeypatch):
    temp_rules = tmp_path / "rules.py"
    shutil.copy(REAL_RULES_PATH, temp_rules)
    monkeypatch.setattr(main_module, "RULES_PATH", temp_rules)

    controller = _controller()
    old_scene = controller.scene
    old_bridge = controller.bridge
    assert old_bridge.rules_path == temp_rules

    temp_rules.write_text("def play_card(player, enemy, hand_index:\n    pass\n", encoding="utf-8")  # 語法錯誤

    controller.handle([Reload()])

    assert controller.scene is old_scene
    assert controller.bridge is old_bridge
    assert any("重新載入失敗" in m for m in old_scene.battle_log)
    # 舊版本（語法還沒壞掉時載入的那份）仍然能正常運作
    assert controller.bridge.can_play(old_scene.player, 0) in (True, False)
    assert controller.bridge.rules.__name__  # 模組還在，沒有變成壞掉的那份


# ---------------------------------------------------------------------------
# 重載隨時可以按：fx 播放中、錯誤畫面顯示中都不會被擋住
# ---------------------------------------------------------------------------


def test_reload_works_even_during_error_panel():
    controller = _controller()
    controller.bridge.rules.play_card = lambda player, enemy, hand_index: (_ for _ in ()).throw(
        ValueError("壞掉的卡牌效果")
    )
    controller.handle([PlayCard(0)])
    assert controller.scene.state == STATE_SHOWING_ERROR

    controller.handle([Reload()])

    assert controller.scene.state != STATE_SHOWING_ERROR
    assert any("已重新載入" in m for m in controller.scene.battle_log)
