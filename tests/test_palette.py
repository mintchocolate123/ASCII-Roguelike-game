from engine import palette


def test_resolve_known_semantic_name():
    assert palette.resolve("hp") == palette.PALETTE["hp"]


def test_resolve_art_color_name():
    assert palette.resolve("cyan") == palette.ART_COLORS["cyan"]


def test_resolve_unknown_name_falls_back_to_text():
    assert palette.resolve("not_a_color") == palette.PALETTE["text"]


def test_ansi256_returns_int_in_range():
    for name in palette.COLOR_NAMES:
        code = palette.ansi256(name)
        assert isinstance(code, int)
        assert 0 <= code <= 255


def test_ansi256_black_and_white_are_distinguishable():
    assert palette.ansi256("bg") != palette.ansi256("white")
