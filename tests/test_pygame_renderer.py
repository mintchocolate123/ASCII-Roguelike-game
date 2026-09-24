"""pygame 渲染器測試：用 SDL 的 dummy video driver 在無畫面環境下也能跑。"""
import os
import sys

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402  需要先設好 dummy driver 再 import

from engine.actions import Back, Confirm, EndTurn, Inspect, PlayCard, Quit, Reload  # noqa: E402
from engine.grid import Grid  # noqa: E402
from engine.render.pygame_renderer import FontLoadError, PygameRenderer  # noqa: E402


@pytest.fixture
def renderer():
    r = PygameRenderer()
    yield r
    r.close()


# ---------------------------------------------------------------------------
# 字型
# ---------------------------------------------------------------------------


def test_missing_font_raises_clear_chinese_error(tmp_path):
    missing = tmp_path / "not_a_real_font.ttf"
    with pytest.raises(FontLoadError) as exc_info:
        PygameRenderer(font_path=missing)
    message = str(exc_info.value)
    assert "找不到字型檔" in message
    assert str(missing) in message


def test_real_font_loads_without_raising(renderer):
    assert renderer._font is not None


# ---------------------------------------------------------------------------
# present()：(char, fg, bg) 快取、只有 dirty 時重畫
# ---------------------------------------------------------------------------


def test_present_caches_glyph_surfaces_by_char_fg_bg(renderer):
    grid = Grid(width=2, height=1)
    grid.set_cell(0, 0, "A", fg="text")
    grid.set_cell(1, 0, "A", fg="text")
    renderer.present(grid)
    assert len(renderer._glyph_cache) == 1  # 兩格是同一個 (char, fg, bg)，只快取一次


def test_present_skips_when_not_dirty(renderer):
    grid = Grid(width=3, height=1)
    renderer.present(grid)
    renderer._glyph_cache.clear()
    grid.dirty = False
    renderer.present(grid)
    assert renderer._glyph_cache == {}  # 完全沒有重畫，快取也不會被填回去


def test_present_clears_dirty_flag(renderer):
    grid = Grid(width=3, height=1)
    assert grid.dirty is True
    renderer.present(grid)
    assert grid.dirty is False


# ---------------------------------------------------------------------------
# 鍵盤輸入
# ---------------------------------------------------------------------------


def _post(event_type, **kwargs):
    pygame.event.post(pygame.event.Event(event_type, **kwargs))


def test_number_keys_map_to_play_card(renderer):
    _post(pygame.KEYDOWN, key=pygame.K_1)
    _post(pygame.KEYDOWN, key=pygame.K_7)
    actions = renderer.poll_actions()
    assert actions == [PlayCard(0), PlayCard(6)]


def test_e_key_maps_to_end_turn(renderer):
    _post(pygame.KEYDOWN, key=pygame.K_e)
    assert renderer.poll_actions() == [EndTurn()]


def test_enter_key_maps_to_confirm(renderer):
    _post(pygame.KEYDOWN, key=pygame.K_RETURN)
    assert renderer.poll_actions() == [Confirm()]


def test_f5_maps_to_reload(renderer):
    _post(pygame.KEYDOWN, key=pygame.K_F5)
    assert renderer.poll_actions() == [Reload()]


def test_escape_maps_to_back(renderer):
    _post(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    assert renderer.poll_actions() == [Back()]


def test_quit_event_maps_to_quit(renderer):
    _post(pygame.QUIT)
    assert renderer.poll_actions() == [Quit()]


def test_supports_animation_is_true(renderer):
    assert renderer.supports_animation() is True


# ---------------------------------------------------------------------------
# 滑鼠：點擊卡牌出牌、移入/移出送出 Inspect
# ---------------------------------------------------------------------------


def _card_pixel(index: int) -> tuple[int, int]:
    from engine import layout
    from engine.grid import CELL_PIXEL_HEIGHT, CELL_PIXEL_WIDTH

    col = layout.card_slot_x(index) + 1
    row = layout.HAND_ROW_TOP + 1
    return col * CELL_PIXEL_WIDTH, row * CELL_PIXEL_HEIGHT


def test_click_on_card_emits_play_card(renderer):
    pos = _card_pixel(2)
    _post(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)
    assert renderer.poll_actions() == [PlayCard(2)]


def test_right_click_on_card_does_nothing(renderer):
    pos = _card_pixel(0)
    _post(pygame.MOUSEBUTTONDOWN, pos=pos, button=3)
    assert renderer.poll_actions() == []


def test_click_outside_hand_area_does_nothing(renderer):
    _post(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1)
    assert renderer.poll_actions() == []


def test_mouse_move_into_card_emits_inspect(renderer):
    pos = _card_pixel(1)
    _post(pygame.MOUSEMOTION, pos=pos)
    assert renderer.poll_actions() == [Inspect(1)]


def test_mouse_move_out_of_cards_emits_inspect_none(renderer):
    _post(pygame.MOUSEMOTION, pos=_card_pixel(1))
    renderer.poll_actions()
    _post(pygame.MOUSEMOTION, pos=(5, 5))
    assert renderer.poll_actions() == [Inspect(None)]


def test_mouse_move_within_same_card_does_not_repeat_inspect(renderer):
    pos_a = _card_pixel(1)
    pos_b = (pos_a[0] + 1, pos_a[1] + 1)
    _post(pygame.MOUSEMOTION, pos=pos_a)
    first = renderer.poll_actions()
    _post(pygame.MOUSEMOTION, pos=pos_b)
    second = renderer.poll_actions()
    assert first == [Inspect(1)]
    assert second == []  # 還在同一張卡片上，不用重複送出
