import io

from engine.actions import Back, Confirm, EndTurn, PlayCard, Quit, Reload
from engine.draw import draw_box, draw_text, text_width
from engine.grid import Grid
from engine.render.terminal_renderer import TerminalRenderer, parse_action


def test_parse_action_numbers_map_to_play_card():
    assert parse_action("1") == PlayCard(0)
    assert parse_action("7") == PlayCard(6)


def test_parse_action_commands():
    assert parse_action("e") == EndTurn()
    assert parse_action("") == Confirm()
    assert parse_action("b") == Back()
    assert parse_action("r") == Reload()
    assert parse_action("q") == Quit()


def test_parse_action_unknown_returns_none():
    assert parse_action("asdf") is None
    assert parse_action("8") is None


def test_render_to_string_has_one_line_per_row():
    grid = Grid(width=10, height=4)
    renderer = TerminalRenderer(out=io.StringIO())
    output = renderer.render_to_string(grid)
    assert len(output.split("\n")) == 4


def test_render_to_string_mixed_cjk_english_box_alignment():
    grid = Grid(width=20, height=3)
    draw_box(grid, 0, 0, 20, 3)
    draw_text(grid, 1, 1, "血量 HP 10")
    renderer = TerminalRenderer(out=io.StringIO())
    output = renderer.render_to_string(grid)
    lines = output.split("\n")
    assert len(lines) == 3
    # 去除 ANSI 色碼後，每行結尾應該是右邊框
    import re

    plain = [re.sub(r"\x1b\[[0-9;]*m", "", line) for line in lines]
    assert plain[0].endswith("┐")
    assert plain[1].endswith("│")
    assert plain[2].endswith("┘")


def test_present_writes_to_out_and_clears_dirty():
    grid = Grid(width=5, height=2)
    out = io.StringIO()
    renderer = TerminalRenderer(out=out)
    renderer.present(grid)
    assert grid.dirty is False
    assert out.getvalue() != ""


def test_present_skips_when_not_dirty():
    grid = Grid(width=5, height=2)
    grid.dirty = False
    out = io.StringIO()
    renderer = TerminalRenderer(out=out)
    renderer.present(grid)
    assert out.getvalue() == ""
