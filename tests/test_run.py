from engine.run import Run, build_starting_deck, pick_enemy

STAGES = [
    {"type": "battle", "tier": "normal"},
    {"type": "battle", "tier": "normal"},
    {"type": "battle", "tier": "elite"},
    {"type": "rest"},
    {"type": "battle", "tier": "boss"},
]


def test_current_stage_and_advance():
    run = Run(stages=STAGES, deck=[])
    assert run.current_stage == {"type": "battle", "tier": "normal"}
    assert run.is_finished is False
    assert run.floor == 1
    run.advance()
    assert run.current_stage == {"type": "battle", "tier": "normal"}
    assert run.floor == 2


def test_is_finished_after_last_stage():
    run = Run(stages=STAGES, deck=[])
    for _ in range(len(STAGES)):
        run.advance()
    assert run.current_stage is None
    assert run.is_finished is True


def test_record_hp_sets_hp_and_max_hp():
    run = Run(stages=STAGES, deck=[])
    assert run.hp is None
    run.record_hp(42, 50)
    assert run.hp == 42
    assert run.max_hp == 50


def test_rest_heal_restores_30_percent_of_max_hp():
    run = Run(stages=STAGES, deck=[])
    run.record_hp(20, 50)
    healed = run.rest_heal()
    assert healed == 15  # int(50 * 0.3)
    assert run.hp == 35


def test_rest_heal_caps_at_max_hp():
    run = Run(stages=STAGES, deck=[])
    run.record_hp(45, 50)
    healed = run.rest_heal()
    assert healed == 5
    assert run.hp == 50


def test_rest_heal_before_hp_known_is_noop():
    run = Run(stages=STAGES, deck=[])
    assert run.rest_heal() == 0
    assert run.hp is None


def test_deck_persists_across_advance():
    deck = [{"id": "strike"}]
    run = Run(stages=STAGES, deck=deck)
    run.deck.append({"id": "new_card"})
    run.advance()
    assert len(run.deck) == 2


def test_build_starting_deck_expands_by_count():
    cards = {
        "core:strike": {"id": "strike", "count": 2},
        "core:defend": {"id": "defend", "count": 1},
        "core:shield_bash": {"id": "shield_bash", "count": 0},
    }
    deck = build_starting_deck(cards)
    ids = [c["id"] for c in deck]
    assert ids.count("strike") == 2
    assert ids.count("defend") == 1
    assert "shield_bash" not in ids


def test_pick_enemy_by_tier():
    enemies = {
        "core:slime": {"tier": "normal"},
        "core:goblin": {"tier": "normal"},
        "core:boss": {"tier": "boss"},
    }
    picked = pick_enemy(enemies, tier="boss")
    assert picked == {"tier": "boss"}


def test_pick_enemy_missing_tier_raises_value_error():
    import pytest

    with pytest.raises(ValueError):
        pick_enemy({"core:slime": {"tier": "normal"}}, tier="boss")


def test_pick_enemy_unknown_full_id_raises_key_error():
    import pytest

    with pytest.raises(KeyError):
        pick_enemy({}, full_id="core:does_not_exist")
