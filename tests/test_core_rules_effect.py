"""mods/core/rules.py 的 effect 欄位處理：play_card() 依卡牌的 effect 完整 id 從
engine.mod.registry 找回註冊的 class，呼叫 apply(player, enemy, card) 併入訊息，
跟 damage/block/heal 等欄位的效果一起執行（第二階段：registry、mod 腳本與 class 介面）。
"""
from pathlib import Path

import pytest

from engine.bridge import Bridge
from engine.mod.loader import load_mods
from engine.mod.registry import registry

REAL_RULES_PATH = Path(__file__).resolve().parent.parent / "mods" / "core" / "rules.py"
MODS_DIR = Path(__file__).resolve().parent.parent / "mods"


@pytest.fixture(autouse=True)
def _clean_registry():
    """registry 是全域單例：手動呼叫 begin_mod()/register_effect() 的測試要自己收拾，
    避免殘留的註冊影響到其他測試檔案。"""
    registry.clear()
    yield
    registry.clear()


def _player(hand, *, block=0):
    return {
        "name": "測試玩家",
        "hp": 50,
        "max_hp": 50,
        "block": block,
        "energy": 3,
        "draw_pile": [],
        "hand": list(hand),
        "discard": [],
    }


def _enemy(hp=40):
    return {
        "id": "core:test_dummy",
        "name": "測試假人",
        "hp": hp,
        "max_hp": hp,
        "block": 0,
        "actions": [{"type": "attack", "value": 3}],
        "action_index": 0,
        "art": ["( x )"],
        "color": "white",
    }


def test_play_card_dispatches_registered_effect_and_uses_its_message():
    registry.begin_mod("core")

    @registry.register_effect("double_block_damage")
    class DoubleBlockDamage:
        def apply(self, player, enemy, card):
            dealt = player.get("block", 0) * 2
            enemy["hp"] = max(0, enemy["hp"] - dealt)
            return f"造成 {dealt} 點傷害（護盾雙倍）"

    registry.end_mod()

    bridge = Bridge(REAL_RULES_PATH)
    card = {
        "id": "test_effect_card",
        "name": "測試",
        "cost": 1,
        "type": "attack",
        "effect": "core:double_block_damage",
        "description": "測試。",
    }
    player = _player([card], block=5)
    enemy = _enemy(hp=40)

    message = bridge.play_card(player, enemy, 0)

    assert enemy["hp"] == 30  # 40 - 5*2
    assert "造成 10 點傷害" in message


def test_play_card_combines_effect_message_with_damage_field():
    registry.begin_mod("core")

    @registry.register_effect("extra_note")
    class ExtraNote:
        def apply(self, player, enemy, card):
            return "附加效果"

    registry.end_mod()

    bridge = Bridge(REAL_RULES_PATH)
    card = {
        "id": "test_combo_card",
        "name": "測試",
        "cost": 1,
        "type": "attack",
        "damage": 5,
        "effect": "core:extra_note",
        "description": "測試。",
    }
    player = _player([card])
    enemy = _enemy(hp=40)

    message = bridge.play_card(player, enemy, 0)

    assert enemy["hp"] == 35
    assert "附加效果" in message
    assert "造成 5 點傷害" in message


def test_play_card_with_unregistered_effect_id_does_not_crash():
    """loader 正常情況下已經會擋掉沒註冊的 effect，但 rules.py 本身也不該假設一定有註冊，
    要能優雅地跳過、不崩潰，符合「引擎不能因為 mod 內容錯誤而崩潰」的硬性原則。"""
    bridge = Bridge(REAL_RULES_PATH)
    card = {
        "id": "test_bad_card",
        "name": "測試",
        "cost": 1,
        "type": "attack",
        "effect": "core:not_registered",
        "description": "測試。",
    }
    player = _player([card])
    enemy = _enemy(hp=40)

    message = bridge.play_card(player, enemy, 0)

    assert enemy["hp"] == 40  # 沒有任何效果套用
    assert "沒有效果" in message


def test_real_example_mod_shield_slam_effect_works_end_to_end():
    """驗收條件：example_mod 用一個 class 實作特殊卡牌效果，要能透過完整流程（load_mods 載入
    mod 腳本、cards.json 用完整 id 引用、bridge 呼叫 play_card）真的產生效果。"""
    db, report = load_mods(MODS_DIR)
    assert not report.has_fatal, report.format_text()

    card = db.cards["example_mod:shield_slam"]
    bridge = Bridge(REAL_RULES_PATH)
    player = _player([card], block=12)
    enemy = _enemy(hp=40)

    message = bridge.play_card(player, enemy, 0)

    assert enemy["hp"] == 28  # 40 - 12
    assert "造成等同護盾值的 12 點傷害" in message
