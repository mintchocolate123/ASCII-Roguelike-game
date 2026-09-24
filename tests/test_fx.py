from engine.fx import (
    DAMAGE_NUMBER_DURATION,
    DAMAGE_NUMBER_FADE_AT,
    DAMAGE_NUMBER_RISE,
    ENEMY_BLOCK_GAIN,
    ENEMY_HIT,
    FLASH_INTERVAL,
    HP_LAG_DURATION,
    PLAYER_BLOCK_GAIN,
    PLAYER_HIT,
    FxQueue,
    diff_damage_numbers,
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


# ---------------------------------------------------------------------------
# diff_damage_numbers：扣血用 hp 色，被護盾吸收的量用 block 色
# ---------------------------------------------------------------------------


def test_diff_damage_numbers_plain_hp_loss():
    before_p, after_p = {"hp": 50, "block": 0}, {"hp": 50, "block": 0}
    before_e, after_e = {"hp": 20, "block": 0}, {"hp": 14, "block": 0}
    assert diff_damage_numbers(before_p, after_p, before_e, after_e) == [("enemy", 6, "hp")]


def test_diff_damage_numbers_block_absorbs_some_damage():
    # 玩家有 5 點護盾，這次被打 8 點：5 點被護盾吸收、3 點扣血
    before_p, after_p = {"hp": 50, "block": 5}, {"hp": 47, "block": 0}
    before_e, after_e = {"hp": 20, "block": 0}, {"hp": 20, "block": 0}
    numbers = diff_damage_numbers(before_p, after_p, before_e, after_e)
    assert ("player", 3, "hp") in numbers
    assert ("player", 5, "block") in numbers
    assert len(numbers) == 2


def test_diff_damage_numbers_block_fully_absorbs_no_hp_number():
    before_p, after_p = {"hp": 50, "block": 10}, {"hp": 50, "block": 4}
    before_e, after_e = {"hp": 20, "block": 0}, {"hp": 20, "block": 0}
    assert diff_damage_numbers(before_p, after_p, before_e, after_e) == [("player", 6, "block")]


def test_diff_damage_numbers_heal_produces_nothing():
    before_p, after_p = {"hp": 40, "block": 0}, {"hp": 46, "block": 0}
    before_e, after_e = {"hp": 20, "block": 0}, {"hp": 20, "block": 0}
    assert diff_damage_numbers(before_p, after_p, before_e, after_e) == []


def test_diff_damage_numbers_block_gain_produces_nothing():
    before_p, after_p = {"hp": 50, "block": 0}, {"hp": 50, "block": 5}
    before_e, after_e = {"hp": 20, "block": 0}, {"hp": 20, "block": 0}
    assert diff_damage_numbers(before_p, after_p, before_e, after_e) == []


def test_diff_damage_numbers_both_sides_at_once():
    before_p, after_p = {"hp": 50, "block": 0}, {"hp": 44, "block": 0}
    before_e, after_e = {"hp": 20, "block": 0}, {"hp": 14, "block": 0}
    numbers = diff_damage_numbers(before_p, after_p, before_e, after_e)
    assert ("player", 6, "hp") in numbers
    assert ("enemy", 6, "hp") in numbers


# ---------------------------------------------------------------------------
# FxQueue：傷害數字彈出（往上飄、淡出）
# ---------------------------------------------------------------------------


def test_spawn_number_is_returned_by_numbers_for():
    fx = FxQueue()
    fx.spawn_number(6, "hp", "enemy")
    numbers = fx.numbers_for("enemy")
    assert len(numbers) == 1
    assert numbers[0].amount == 6
    assert numbers[0].color == "hp"


def test_numbers_for_filters_by_origin():
    fx = FxQueue()
    fx.spawn_number(6, "hp", "enemy")
    fx.spawn_number(3, "block", "player")
    assert len(fx.numbers_for("enemy")) == 1
    assert len(fx.numbers_for("player")) == 1


def test_spawn_number_makes_is_playing_true():
    fx = FxQueue()
    assert fx.is_playing is False
    fx.spawn_number(6, "hp", "enemy")
    assert fx.is_playing is True


def test_number_expires_after_duration():
    fx = FxQueue()
    fx.spawn_number(6, "hp", "enemy", duration=0.2)
    fx.update(0.1)
    assert len(fx.numbers_for("enemy")) == 1
    fx.update(0.15)
    assert len(fx.numbers_for("enemy")) == 0
    assert fx.is_playing is False


def test_number_rises_over_time():
    fx = FxQueue()
    fx.spawn_number(6, "hp", "enemy", duration=1.0)
    number = fx.numbers_for("enemy")[0]
    assert number.row_offset == 0
    fx.update(1.0)  # 播完，進度 100%
    assert number.row_offset == -DAMAGE_NUMBER_RISE


def test_number_fades_to_dim_color_near_the_end():
    fx = FxQueue()
    fx.spawn_number(6, "hp", "enemy", duration=1.0)
    number = fx.numbers_for("enemy")[0]
    assert number.display_color == "hp"
    fx.update(DAMAGE_NUMBER_FADE_AT + 0.05)
    assert number.display_color == "dim"


def test_multiple_numbers_can_coexist_at_same_origin():
    fx = FxQueue()
    fx.spawn_number(3, "hp", "enemy")
    fx.spawn_number(5, "block", "enemy")
    assert len(fx.numbers_for("enemy")) == 2


def test_default_damage_number_duration_constant_is_used():
    fx = FxQueue()
    fx.spawn_number(6, "hp", "enemy")
    number = fx.numbers_for("enemy")[0]
    assert number.duration == DAMAGE_NUMBER_DURATION


# ---------------------------------------------------------------------------
# FxQueue：延遲血條
# ---------------------------------------------------------------------------


def test_start_hp_lag_only_when_dropping():
    fx = FxQueue()
    fx.start_hp_lag("enemy", 20, 25)  # 回血，不需要殘影
    assert fx.hp_lag_value("enemy") is None


def test_hp_lag_starts_at_old_value_and_catches_up_to_new_value():
    fx = FxQueue()
    fx.start_hp_lag("enemy", 20, 14, duration=1.0)
    assert fx.hp_lag_value("enemy") == 20
    fx.update(0.5)
    value = fx.hp_lag_value("enemy")
    assert 14 < value < 20
    fx.update(0.49)  # 還沒到 duration，殘影應該幾乎追上但還在
    assert fx.hp_lag_value("enemy") == 14


def test_hp_lag_disappears_after_duration():
    fx = FxQueue()
    fx.start_hp_lag("enemy", 20, 14, duration=0.2)
    fx.update(0.3)
    assert fx.hp_lag_value("enemy") is None  # 追上了，不用再畫殘影


def test_hp_lag_is_independent_per_target():
    fx = FxQueue()
    fx.start_hp_lag("enemy", 20, 14, duration=1.0)
    assert fx.hp_lag_value("player") is None
    assert fx.hp_lag_value("enemy") == 20


def test_hp_lag_makes_is_playing_true():
    fx = FxQueue()
    assert fx.is_playing is False
    fx.start_hp_lag("enemy", 20, 14)
    assert fx.is_playing is True


def test_default_hp_lag_duration_constant_is_used():
    fx = FxQueue()
    fx.start_hp_lag("enemy", 20, 14)
    assert fx._hp_lag["enemy"].duration == HP_LAG_DURATION


# ---------------------------------------------------------------------------
# FxQueue.skip()：快轉到結果狀態，不是取消
# ---------------------------------------------------------------------------


def test_skip_clears_flash_and_shake_effects():
    fx = FxQueue()
    fx.trigger(ENEMY_HIT, duration=5.0)
    fx.skip()
    assert fx.is_playing is False
    assert fx.is_active(ENEMY_HIT) is False
    assert fx.shake_offset() == 0


def test_skip_clears_floating_numbers():
    fx = FxQueue()
    fx.spawn_number(6, "hp", "enemy", duration=5.0)
    fx.skip()
    assert fx.numbers_for("enemy") == []
    assert fx.is_playing is False


def test_skip_clears_hp_lag():
    fx = FxQueue()
    fx.start_hp_lag("enemy", 20, 14, duration=5.0)
    fx.skip()
    assert fx.hp_lag_value("enemy") is None
    assert fx.is_playing is False


def test_skip_on_fully_idle_queue_is_a_safe_noop():
    fx = FxQueue()
    fx.skip()
    assert fx.is_playing is False
