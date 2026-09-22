from engine.draw import (
    char_width,
    draw_box,
    draw_hp_bar,
    draw_text,
    text_width,
)
from engine.grid import Grid


def test_char_width_ascii_and_cjk():
    assert char_width("a") == 1
    assert char_width("1") == 1
    assert char_width("哈") == 2
    assert char_width("　") == 2  # 全形空白


def test_text_width_pure_ascii():
    assert text_width("Hello") == 5


def test_text_width_pure_cjk():
    assert text_width("哈囉世界") == 8


def test_text_width_mixed():
    assert text_width("Hi哈囉") == 6


def test_draw_text_marks_wide_tail_for_cjk():
    grid = Grid(width=10, height=1)
    draw_text(grid, 0, 0, "哈i")
    assert grid.get(0, 0).char == "哈"
    assert grid.get(1, 0).wide_tail is True
    assert grid.get(2, 0).char == "i"


def test_draw_text_returns_next_x():
    grid = Grid(width=10, height=1)
    end_x = draw_text(grid, 0, 0, "哈i")
    assert end_x == 3  # 哈 佔 2 格 + i 佔 1 格


def test_draw_text_clips_at_edge_without_raising():
    grid = Grid(width=3, height=1)
    draw_text(grid, 2, 0, "哈")  # 寬字元尾格會超出邊界
    assert grid.get(2, 0).char == "哈"


def test_draw_box_corners_and_edges():
    grid = Grid(width=10, height=5)
    draw_box(grid, 0, 0, 6, 4)
    assert grid.get(0, 0).char == "┌"
    assert grid.get(5, 0).char == "┐"
    assert grid.get(0, 3).char == "└"
    assert grid.get(5, 3).char == "┘"
    assert grid.get(2, 0).char == "─"
    assert grid.get(0, 1).char == "│"


def test_draw_box_mixed_cjk_english_alignment():
    """中英文混排的框線要對齊：不論該行文字寬字元多少個，左右邊框都落在同一欄（x=0 與 x=19）。"""
    grid = Grid(width=30, height=6)
    draw_box(grid, 0, 0, 20, 5, title="標題 Title")
    draw_text(grid, 1, 2, "血量 HP: 10/10")
    draw_text(grid, 1, 3, "Attack 攻擊: 5")

    for y in range(5):
        left = grid.get(0, y).char
        right = grid.get(19, y).char
        if y == 0:
            assert (left, right) == ("┌", "┐")
        elif y == 4:
            assert (left, right) == ("└", "┘")
        else:
            assert (left, right) == ("│", "│")


def test_draw_hp_bar_full_and_empty():
    grid = Grid(width=10, height=1)
    draw_hp_bar(grid, 0, 0, 10, 10, 10)
    assert all(grid.get(i, 0).char == "█" for i in range(10))

    grid2 = Grid(width=10, height=1)
    draw_hp_bar(grid2, 0, 0, 10, 0, 10)
    assert all(grid2.get(i, 0).char == "░" for i in range(10))


def test_draw_hp_bar_half():
    grid = Grid(width=10, height=1)
    draw_hp_bar(grid, 0, 0, 10, 5, 10)
    chars = [grid.get(i, 0).char for i in range(10)]
    assert chars.count("█") == 5
    assert chars.count("░") == 5
