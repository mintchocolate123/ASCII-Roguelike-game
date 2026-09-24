import pytest

from engine.mod.registry import EffectRegistry, RegistryError


def test_register_effect_requires_begin_mod_first():
    registry = EffectRegistry()
    with pytest.raises(RegistryError):
        registry.register_effect("shield_slam")


def test_register_effect_builds_full_id_from_mod_id_and_local_id():
    registry = EffectRegistry()
    registry.begin_mod("example_mod")

    @registry.register_effect("shield_slam")
    class ShieldSlam:
        pass

    registry.end_mod()
    assert registry.has_effect("example_mod:shield_slam") is True
    assert registry.get_effect("example_mod:shield_slam") is ShieldSlam


def test_get_effect_returns_none_for_unregistered_id():
    registry = EffectRegistry()
    assert registry.get_effect("nope:nope") is None
    assert registry.has_effect("nope:nope") is False


def test_register_effect_rejects_invalid_local_id_format():
    registry = EffectRegistry()
    registry.begin_mod("example_mod")
    with pytest.raises(RegistryError, match="格式不正確"):
        registry.register_effect("NotValid")
    registry.end_mod()


def test_register_effect_rejects_id_starting_with_digit():
    registry = EffectRegistry()
    registry.begin_mod("example_mod")
    with pytest.raises(RegistryError):
        registry.register_effect("1abc")
    registry.end_mod()


def test_register_effect_rejects_duplicate_full_id():
    registry = EffectRegistry()
    registry.begin_mod("example_mod")

    @registry.register_effect("shield_slam")
    class A:
        pass

    with pytest.raises(RegistryError, match="重複註冊"):

        @registry.register_effect("shield_slam")
        class B:
            pass

    registry.end_mod()


def test_same_local_id_from_different_mods_does_not_collide():
    registry = EffectRegistry()
    registry.begin_mod("mod_a")

    @registry.register_effect("slam")
    class A:
        pass

    registry.end_mod()
    registry.begin_mod("mod_b")

    @registry.register_effect("slam")
    class B:
        pass

    registry.end_mod()
    assert registry.get_effect("mod_a:slam") is A
    assert registry.get_effect("mod_b:slam") is B


def test_clear_removes_all_effects_and_resets_current_mod():
    registry = EffectRegistry()
    registry.begin_mod("example_mod")

    @registry.register_effect("shield_slam")
    class ShieldSlam:
        pass

    registry.end_mod()
    registry.clear()
    assert registry.has_effect("example_mod:shield_slam") is False
    # clear() 之後如果沒有重新 begin_mod() 就呼叫 register_effect()，一樣要報錯，
    # 確認 clear() 有把「目前是哪個 mod」也一併重設。
    with pytest.raises(RegistryError):
        registry.register_effect("anything")


def test_end_mod_prevents_further_registration_until_begin_mod_again():
    registry = EffectRegistry()
    registry.begin_mod("example_mod")
    registry.end_mod()
    with pytest.raises(RegistryError):
        registry.register_effect("shield_slam")


def test_decorator_returns_the_original_class_unchanged():
    registry = EffectRegistry()
    registry.begin_mod("example_mod")

    @registry.register_effect("shield_slam")
    class ShieldSlam:
        marker = True

    registry.end_mod()
    assert ShieldSlam.marker is True
