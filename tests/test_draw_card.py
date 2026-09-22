from engine.draw import draw_card, draw_keyword_text
from engine.grid import Grid, plain_lines


def test_draw_card_double_line_border():
    grid = Grid(width=20, height=12)
    draw_card(grid, 0, 0, name="斬擊", cost=1, card_type="attack", description="造成 6 點傷害。")
    assert grid.get(0, 0).char == "╔"
    assert grid.get(11, 0).char == "╗"
    assert grid.get(0, 9).char == "╚"
    assert grid.get(11, 9).char == "╝"


def test_draw_card_cost_embedded_top_left():
    grid = Grid(width=20, height=12)
    draw_card(grid, 0, 0, name="斬擊", cost=1, card_type="attack", description="造成 6 點傷害。")
    assert grid.get(1, 0).char == "◆"
    assert grid.get(2, 0).char == "1"


def test_draw_card_divider_row_uses_mixed_junctions():
    grid = Grid(width=20, height=12)
    draw_card(grid, 0, 0, name="斬擊", cost=1, card_type="attack", description="造成 6 點傷害。")
    assert grid.get(0, 2).char == "╟"
    assert grid.get(11, 2).char == "╢"
    assert grid.get(5, 2).char == "─"


def test_draw_card_bottom_type_label():
    grid = Grid(width=20, height=12)
    draw_card(grid, 0, 0, name="斬擊", cost=1, card_type="attack", description="造成 6 點傷害。")
    line = plain_lines(grid)[9]
    assert "攻擊" in line


def test_draw_card_unplayable_uses_dim_color_everywhere():
    grid = Grid(width=20, height=12)
    draw_card(
        grid, 0, 0, name="斬擊", cost=1, card_type="attack",
        description="造成 6 點傷害。", playable=False,
    )
    assert grid.get(0, 0).fg == "dim"
    assert grid.get(2, 0).fg == "dim"  # 費用數字
    assert grid.get(1, 3).fg == "dim"  # 描述文字


def test_draw_card_highlighted_only_affects_border_and_type_label():
    grid = Grid(width=20, height=12)
    draw_card(
        grid, 0, 0, name="斬擊", cost=1, card_type="attack",
        description="造成 6 點傷害。", highlighted=True,
    )
    assert grid.get(0, 0).fg == "highlight"
    assert grid.get(2, 0).fg == "energy"  # 費用仍是 energy 色
    assert grid.get(1, 3).fg == "text"  # 描述文字不受 highlight 影響


def test_draw_card_description_fits_within_six_lines_for_long_text():
    grid = Grid(width=20, height=12)
    long_desc = "造成 3 點傷害，重複 3 次。獲得 5 點護盾。回復 4 點生命。"
    draw_card(grid, 0, 0, name="連斬", cost=1, card_type="attack", description=long_desc)
    lines = plain_lines(grid)
    # 描述應該只佔第 3 到 8 列（共 6 行），不會蓋掉第 9 列的下框線
    assert "╚" in lines[9]


def test_draw_card_truncated_description_shows_ellipsis_on_last_line():
    """截斷保護保留：被截斷時最後一行要顯示「…」。"""
    grid = Grid(width=20, height=12)
    long_desc = "造成 3 點傷害，重複 3 次。獲得 5 點護盾。回復 4 點生命。抽 2 張牌。獲得 2 點能量。失去 3 點生命。"
    draw_card(grid, 0, 0, name="連斬", cost=1, card_type="attack", description=long_desc)
    lines = plain_lines(grid)
    last_desc_row = lines[8]  # 第 3 到 8 列是描述，第 8 列是最後一行
    assert "…" in last_desc_row
    assert "╚" in lines[9]  # 下框線沒有被蓋掉


def test_draw_card_short_description_has_no_ellipsis():
    grid = Grid(width=20, height=12)
    draw_card(grid, 0, 0, name="斬擊", cost=1, card_type="attack", description="造成 6 點傷害。")
    lines = plain_lines(grid)
    assert "…" not in "".join(lines)


def test_draw_keyword_text_strips_brackets_and_colors_inside():
    grid = Grid(width=20, height=1)
    draw_keyword_text(grid, 0, 0, "造成【中毒】3", base_fg="text", keyword_fg="keyword")
    line = plain_lines(grid)[0]
    assert "【" not in line and "】" not in line
    assert "中毒" in line
    # 直接掃描 grid 找到「中」的格子（plain_lines 的字串索引因寬字元而不等於欄座標）
    zhong_x = next(x for x in range(grid.width) if grid.get(x, 0).char == "中")
    assert grid.get(zhong_x, 0).fg == "keyword"
    assert grid.get(0, 0).fg == "text"
