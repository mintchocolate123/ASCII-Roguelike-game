import pytest

from engine.cardtext import CardTextError, resolve_description


def test_auto_generate_damage_only():
    card = {"damage": 6}
    assert resolve_description(card) == "造成 6 點傷害。"


def test_auto_generate_damage_with_hits():
    card = {"damage": 3, "hits": 3}
    assert resolve_description(card) == "造成 3 點傷害，重複 3 次。"


def test_auto_generate_damage_and_block():
    card = {"damage": 5, "block": 5}
    assert resolve_description(card) == "造成 5 點傷害。獲得 5 點護盾。"


def test_auto_generate_all_fields_in_order():
    card = {
        "damage": 1,
        "hits": 2,
        "block": 3,
        "heal": 4,
        "draw": 5,
        "energy": 6,
        "self_damage": 7,
    }
    assert resolve_description(card) == (
        "造成 1 點傷害，重複 2 次。"
        "獲得 3 點護盾。"
        "回復 4 點生命。"
        "抽 5 張牌。"
        "獲得 6 點能量。"
        "失去 7 點生命。"
    )


def test_auto_generate_no_numeric_fields_gives_empty_string():
    assert resolve_description({}) == ""


def test_placeholder_substitution():
    card = {"description": "造成 {damage} 點傷害，獲得【護盾】{block} 點。", "damage": 6, "block": 5}
    assert resolve_description(card) == "造成 6 點傷害，獲得【護盾】5 點。"


def test_placeholder_referencing_missing_field_raises():
    card = {"description": "造成 {damage} 點傷害。", "block": 5}
    with pytest.raises(CardTextError):
        resolve_description(card)


def test_placeholder_referencing_unknown_name_raises():
    card = {"description": "造成 {power} 點傷害。", "damage": 6}
    with pytest.raises(CardTextError):
        resolve_description(card)


def test_values_override_only_applies_to_existing_fields():
    card = {"damage": 6}
    assert resolve_description(card, values={"damage": 9}) == "造成 9 點傷害。"
    # block 這張卡原本沒有值，就算 values 帶了也不會被 auto-generate 用到
    assert resolve_description(card, values={"block": 3}) == "造成 6 點傷害。"
