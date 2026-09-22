from engine.grid import Grid, plain_lines


def test_default_size():
    grid = Grid()
    assert grid.width == 96
    assert grid.height == 32


def test_set_cell_marks_dirty():
    grid = Grid()
    grid.dirty = False
    grid.set_cell(1, 1, "x")
    assert grid.dirty is True
    assert grid.get(1, 1).char == "x"


def test_set_cell_out_of_bounds_is_clipped_without_error():
    grid = Grid(width=10, height=5)
    grid.set_cell(-1, 0, "x")
    grid.set_cell(0, -1, "x")
    grid.set_cell(10, 0, "x")
    grid.set_cell(0, 5, "x")
    grid.set_cell(999, 999, "x")
    for y in range(grid.height):
        for x in range(grid.width):
            assert grid.get(x, y).char == " "


def test_clear_resets_cells_and_sets_dirty():
    grid = Grid()
    grid.set_cell(0, 0, "x", fg="red", bg="blue")
    grid.dirty = False
    grid.clear()
    cell = grid.get(0, 0)
    assert cell.char == " "
    assert cell.fg == "text"
    assert cell.bg is None
    assert grid.dirty is True


def test_overwriting_wide_char_head_clears_tail():
    grid = Grid(width=5, height=1)
    grid.set_cell(0, 0, "哈", wide_tail=False)
    grid.set_cell(1, 0, "", wide_tail=True)
    grid.set_cell(0, 0, "a")  # 覆寫前半格
    assert grid.get(0, 0).char == "a"
    assert grid.get(1, 0).char == " "
    assert grid.get(1, 0).wide_tail is False


def test_overwriting_wide_char_tail_clears_head():
    grid = Grid(width=5, height=1)
    grid.set_cell(0, 0, "哈", wide_tail=False)
    grid.set_cell(1, 0, "", wide_tail=True)
    grid.set_cell(1, 0, "b")  # 覆寫後半格
    assert grid.get(1, 0).char == "b"
    assert grid.get(0, 0).char == " "


def test_plain_lines_skips_wide_tail_cells():
    grid = Grid(width=5, height=1)
    grid.set_cell(0, 0, "哈", wide_tail=False)
    grid.set_cell(1, 0, "", wide_tail=True)
    grid.set_cell(2, 0, "i")
    lines = plain_lines(grid)
    assert lines[0] == "哈i  "
