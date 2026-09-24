"""F5 熱重載：重新載入所有 mod 資料與 rules.py，重開目前這場戰鬥；
失敗時要顯示錯誤但不能讓遊戲崩潰，必須能繼續用重新載入前的版本玩下去。
"""
import json
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
    """只留一隻 normal tier 敵人，並把血量灌高。這裡只是要測 reload 的行為（不是戰鬥平衡），
    cards.json 目前可能正被拿來手動測試熱重載（傷害值會變動），血量灌高才不會被一張牌秒殺，
    導致還沒打到想測的那幾步戰鬥就已經結束。
    """
    db, report = load_mods(MODS_DIR)
    normal = {k: v for k, v in db.enemies.items() if v["tier"] == "normal"}
    weakest = min(normal, key=lambda k: normal[k]["hp"])
    tanky = dict(db.enemies[weakest])
    tanky["hp"] = tanky["max_hp"] = 999_999
    db.enemies = {
        k: (tanky if k == weakest else v) for k, v in db.enemies.items() if v["tier"] != "normal" or k == weakest
    }
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


def _controller_with_temp_mods(tmp_path, monkeypatch):
    """複製一份 mods/ 到暫存資料夾，讓測試可以自由竄改磁碟上的 JSON 內容而不影響真正的專案檔案。"""
    temp_mods = tmp_path / "mods"
    shutil.copytree(MODS_DIR, temp_mods)
    monkeypatch.setattr(main_module, "MODS_DIR", temp_mods)
    monkeypatch.setattr(main_module, "RULES_PATH", temp_mods / "core" / "rules.py")

    db, report = load_mods(temp_mods)
    normal = {k: v for k, v in db.enemies.items() if v["tier"] == "normal"}
    weakest = min(normal, key=lambda k: normal[k]["hp"])
    db.enemies = {k: v for k, v in db.enemies.items() if v["tier"] != "normal" or k == weakest}
    db.run_stages = [{"type": "battle", "tier": "normal"}]

    controller = GameController(db, report, supports_animation=False)
    controller.handle([Confirm()])  # loading -> title
    controller.handle([Confirm()])  # title -> 第一場戰鬥
    return controller, temp_mods


def test_reload_picks_up_changed_card_damage_and_description_from_disk(tmp_path, monkeypatch):
    """重現回報的 bug：改磁碟上的 cards.json 後按 F5，新戰鬥裡的卡牌應該要用新的數值與描述。

    不假設磁碟上目前的原始傷害值是多少（cards.json 目前可能正被拿來手動重現這個 bug，
    已經被改過），一律動態算出一個跟目前不一樣的新數值，測試才不會跟著環境狀態浮動。
    """
    controller, temp_mods = _controller_with_temp_mods(tmp_path, monkeypatch)

    original_strike = next(c for c in controller.run.deck if c["id"] == "strike")
    original_damage = original_strike["damage"]
    new_damage = original_damage + 1000

    cards_path = temp_mods / "core" / "cards.json"
    data = json.loads(cards_path.read_text(encoding="utf-8"))
    for card in data:
        if card["id"] == "strike":
            card["damage"] = new_damage
    cards_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    controller.handle([Reload()])

    new_scene = controller.scene
    assert isinstance(new_scene, BattleScene)

    updated_strike = next(c for c in controller.run.deck if c["id"] == "strike")
    assert updated_strike["damage"] == new_damage
    assert str(new_damage) in updated_strike["description"]

    player_view = controller.bridge.player_view(new_scene.player)
    cards_in_play = player_view["hand"] + player_view["draw_pile"]
    strikes_in_play = [c for c in cards_in_play if c["id"] == "strike"]
    assert strikes_in_play, "牌組裡應該還有 strike 這張卡"
    for card in strikes_in_play:
        assert card["damage"] == new_damage
        assert str(new_damage) in card["description"]


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
# F5 也要重新載入 mod 的 scripts/*.py（第二階段：registry、效果 class）
# ---------------------------------------------------------------------------


def test_reload_recompiles_mod_scripts_and_updates_registered_effect_behavior(tmp_path, monkeypatch):
    """改 mod 的 scripts/*.py（不是 cards.json）也要能靠 F5 立即生效：修改 effect class 的行為
    後重新載入，新打出的卡要用新版的 class，不能殘留舊版本。"""
    controller, temp_mods = _controller_with_temp_mods(tmp_path, monkeypatch)

    effects_path = temp_mods / "example_mod" / "scripts" / "effects.py"
    original_source = effects_path.read_text(encoding="utf-8")
    assert 'player.get("block", 0)' in original_source
    effects_path.write_text(
        original_source.replace(
            'dealt = player.get("block", 0)',
            'dealt = player.get("block", 0) * 2',
        ),
        encoding="utf-8",
    )

    controller.handle([Reload()])
    new_scene = controller.scene
    assert isinstance(new_scene, BattleScene)
    assert any("已重新載入" in m for m in new_scene.battle_log)

    card = next(c for c in controller.db.cards.values() if c["id"] == "shield_slam")
    player = {
        "name": "測試",
        "hp": 50,
        "max_hp": 50,
        "block": 7,
        "energy": 3,
        "draw_pile": [],
        "hand": [dict(card)],
        "discard": [],
    }
    enemy = dict(new_scene.enemy)
    enemy["hp"] = enemy["max_hp"] = 999

    message = controller.bridge.play_card(player, enemy, 0)

    assert enemy["hp"] == 999 - 14  # 改成護盾雙倍傷害後應該是 7*2=14，不是舊版的 7
    assert "造成等同護盾值的 14 點傷害" in message


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
