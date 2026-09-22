from engine.draw import text_width, wrap_text


def test_wrap_text_empty_string():
    assert wrap_text("", 10) == []


def test_wrap_text_exactly_equal_to_width():
    assert wrap_text("1234567890", 10) == ["1234567890"]


def test_wrap_text_ascii_number_unit_not_broken():
    """連續英數字視為一個單位，寬度不夠時整個單位移到下一行，不會從中間切開。"""
    lines = wrap_text("AB HP10", 5)
    assert lines == ["AB ", "HP10"]
    for line in lines:
        assert text_width(line) <= 5


def test_wrap_text_ascii_unit_force_split_when_longer_than_width():
    """單位本身超過 width 時才強制切斷。"""
    lines = wrap_text("1234567890", 4)
    assert lines == ["1234", "5678", "90"]


def test_wrap_text_cjk_can_break_between_chars():
    lines = wrap_text("造成傷害", 4)  # 每字寬 2，寬度 4 剛好放 2 字
    assert lines == ["造成", "傷害"]


def test_wrap_text_forced_newline():
    assert wrap_text("AAA\nBBB", 10) == ["AAA", "BBB"]


def test_wrap_text_forced_newline_with_empty_segment():
    assert wrap_text("AAA\n\nBBB", 10) == ["AAA", "", "BBB"]


def test_wrap_text_leading_punctuation_pushed_to_next_unit():
    """行首禁則：標點連同上一行最後一個字一起被推到下一行，且不超出 width。"""
    lines = wrap_text("造成傷害，佳", 4)
    for line in lines:
        assert text_width(line) <= 4
    for line in lines[1:]:
        assert line[0] not in "，。、；：！？）」『…"
    assert "".join(lines) == "造成傷害，佳"


def test_wrap_text_leading_punctuation_real_card_case():
    """對應 cards.json 的盾擊卡片描述：換行後不能有標點開頭，也不能超出寬度 10。"""
    text = "造成 5 點傷害。獲得 5 點護盾。"
    lines = wrap_text(text, 10)
    for line in lines:
        assert text_width(line) <= 10
    for line in lines[1:]:
        if line:
            assert line[0] not in "，。、；：！？）」『…"
