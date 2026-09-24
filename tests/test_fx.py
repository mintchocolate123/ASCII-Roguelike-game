from engine.fx import (
    ENEMY_BLOCK_GAIN,
    ENEMY_HIT,
    FLASH_INTERVAL,
    PLAYER_BLOCK_GAIN,
    PLAYER_HIT,
    FxQueue,
    diff_triggers,
)

# ---------------------------------------------------------------------------
# diff_triggers：比較 before/after 的 view 差異
# ---------------------------------------------------------------------------


def test_enemy_hp_drop_triggers_enemy_hit():
    before_p, after_p = {"hp": 50}, {"hp": 50}
    before_e, after_e = {"hp": 20}, {"hp": 14}
    assert diff_triggers(before_p, after_p, before_e, after_e) == [ENEMY_HIT]


def test_player_hp_drop_triggers_player_hit():
    before_p, after_p = {"hp": 50}, {"hp": 45}
    before_e, after_e = {"hp": 20}, {"hp": 20}
    assert diff_triggers(before_p, after_p, before_e, after_e) == [PLAYER_HIT]


def test_player_block_increase_triggers_player_block_gain():
    before_p, after_p = {"hp": 50, "block": 0}, {"hp": 50, "block": 5}
    before_e, after_e = {"hp": 20, "block": 0}, {"hp": 20, "block": 0}
    assert diff_triggers(before_p, after_p, before_e, after_e) == [PLAYER_BLOCK_GAIN]


def test_enemy_block_increase_triggers_enemy_block_gain():
    before_p, after_p = {"hp": 50, "block": 0}, {"hp": 50, "block": 0}
    before_e, after_e = {"hp": 20, "block": 0}, {"hp": 20, "block": 6}
    assert diff_triggers(before_p, after_p, before_e, after_e) == [ENEMY_BLOCK_GAIN]


def test_damage_and_block_in_same_call_triggers_both():
    # 例如「造成 5 點傷害，獲得 5 點護盾」的卡
    before_p, after_p = {"hp": 50, "block": 0}, {"hp": 50, "block": 5}
    before_e, after_e = {"hp": 20, "block": 0}, {"hp": 15, "block": 0}
    triggers = diff_triggers(before_p, after_p, before_e, after_e)
    assert set(triggers) == {ENEMY_HIT, PLAYER_BLOCK_GAIN}


def test_heal_does_not_trigger_anything():
    before_p, after_p = {"hp": 40, "block": 0}, {"hp": 46, "block": 0}
    before_e, after_e = {"hp": 20, "block": 0}, {"hp": 20, "block": 0}
    assert diff_triggers(before_p, after_p, before_e, after_e) == []


def test_no_change_triggers_nothing():
    view = {"hp": 20, "block": 3}
    assert diff_triggers(dict(view), dict(view), dict(view), dict(view)) == []


def test_block_decrease_does_not_trigger_gain():
    before_p, after_p = {"hp": 50, "block": 5}, {"hp": 50, "block": 0}
    before_e, after_e = {"hp": 20, "block": 0}, {"hp": 20, "block": 0}
    assert diff_triggers(before_p, after_p, before_e, after_e) == []


# ---------------------------------------------------------------------------
# FxQueue：計時、同時播放多種效果、閃爍與抖動
# ---------------------------------------------------------------------------


def test_trigger_makes_is_playing_true():
    fx = FxQueue()
    assert fx.is_playing is False
    fx.trigger(ENEMY_HIT)
    assert fx.is_playing is True
    assert fx.is_active(ENEMY_HIT) is True


def test_effect_expires_after_duration():
    fx = FxQueue()
    fx.trigger(ENEMY_HIT, duration=0.2)
    fx.update(0.1)
    assert fx.is_active(ENEMY_HIT) is True
    fx.update(0.15)
    assert fx.is_active(ENEMY_HIT) is False
    assert fx.is_playing is False


def test_multiple_effects_play_simultaneously():
    fx = FxQueue()
    fx.trigger(ENEMY_HIT, duration=0.5)
    fx.trigger(PLAYER_BLOCK_GAIN, duration=0.1)
    fx.update(0.15)
    assert fx.is_active(ENEMY_HIT) is True
    assert fx.is_active(PLAYER_BLOCK_GAIN) is False  # 比較短的已經播完，另一個還在播
    assert fx.is_playing is True  # 只要還有任何一個在播，就算 is_playing


def test_flash_on_alternates_over_time():
    fx = FxQueue()
    fx.trigger(PLAYER_HIT, duration=10.0)
    assert fx.flash_on(PLAYER_HIT) is True  # elapsed=0 一開始算「亮」
    fx.update(FLASH_INTERVAL * 0.5)
    assert fx.flash_on(PLAYER_HIT) is True  # 還沒到下一個切換點
    fx.update(FLASH_INTERVAL)
    assert fx.flash_on(PLAYER_HIT) is False  # 切到「暗」


def test_flash_on_false_when_effect_not_active():
    fx = FxQueue()
    assert fx.flash_on(PLAYER_HIT) is False


def test_shake_offset_only_applies_to_enemy_hit():
    fx = FxQueue()
    fx.trigger(PLAYER_HIT, duration=1.0)
    assert fx.shake_offset() == 0  # 不是 enemy_hit，不會抖動


def test_shake_offset_returns_zero_when_not_active():
    fx = FxQueue()
    assert fx.shake_offset() == 0


def test_shake_offset_changes_over_time_and_settles_to_zero():
    fx = FxQueue()
    fx.trigger(ENEMY_HIT, duration=0.5)
    offsets = []
    for _ in range(6):
        offsets.append(fx.shake_offset())
        fx.update(0.5 / 5)
    # 一開始應該有非零的偏移（抖動），最後一格會回到 0
    assert any(o != 0 for o in offsets[:-1])
    assert offsets[-1] == 0


def test_clear_removes_all_effects():
    fx = FxQueue()
    fx.trigger(ENEMY_HIT)
    fx.trigger(PLAYER_HIT)
    fx.clear()
    assert fx.is_playing is False
