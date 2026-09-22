"""具名色表：語意名稱對應 RGB，兩種渲染器各自轉換成自己需要的格式。"""
from __future__ import annotations

# 主要語意色，pygame 渲染器直接使用這裡的 RGB。
PALETTE: dict[str, tuple[int, int, int]] = {
    "bg": (0x0E, 0x0C, 0x0A),
    "frame": (0xB0, 0x8D, 0x57),
    "frame_dim": (0x5C, 0x4A, 0x2E),
    "text": (0xD8, 0xD2, 0xC4),
    "dim": (0x6E, 0x66, 0x58),
    "highlight": (0xFF, 0xF4, 0xD6),
    "hp": (0xC0, 0x39, 0x2B),
    "hp_empty": (0x3A, 0x2A, 0x26),
    "block": (0x4A, 0x90, 0xC2),
    "energy": (0xE0, 0xB2, 0x3C),
    "attack": (0xC8, 0x55, 0x3D),
    "skill": (0x4A, 0x7F, 0xB5),
    "power": (0xC9, 0xA2, 0x27),
    "status_good": (0x6F, 0xAF, 0x5F),
    "status_bad": (0x9B, 0x59, 0xB6),
    "keyword": (0xE8, 0xC1, 0x70),
}

# 敵人 ASCII 圖 color 欄位使用的另一組基本色名稱。
ART_COLORS: dict[str, tuple[int, int, int]] = {
    "white": (0xE8, 0xE4, 0xDA),
    "red": (0xC0, 0x39, 0x2B),
    "green": (0x6F, 0xAF, 0x5F),
    "cyan": (0x4A, 0xB5, 0xB0),
    "yellow": (0xC9, 0xA2, 0x27),
    "blue": (0x4A, 0x7F, 0xB5),
    "gray": (0x6E, 0x66, 0x58),
    "magenta": (0x9B, 0x59, 0xB6),
}

COLOR_NAMES = tuple(PALETTE) + tuple(ART_COLORS)


def resolve(name: str) -> tuple[int, int, int]:
    """依語意名稱取得 RGB；找不到對應名稱時退回 text 色，避免顏色打錯字讓引擎崩潰。"""
    if name in PALETTE:
        return PALETTE[name]
    if name in ART_COLORS:
        return ART_COLORS[name]
    return PALETTE["text"]


def rgb_to_ansi256(rgb: tuple[int, int, int]) -> int:
    """把 RGB 轉成最接近的 ANSI 256 色代碼。"""
    r, g, b = rgb

    def to6(v: int) -> int:
        return round(v / 255 * 5)

    r6, g6, b6 = to6(r), to6(g), to6(b)
    cube_index = 16 + 36 * r6 + 6 * g6 + b6
    cube_rgb = (
        0 if r6 == 0 else 55 + r6 * 40,
        0 if g6 == 0 else 55 + g6 * 40,
        0 if b6 == 0 else 55 + b6 * 40,
    )

    gray_level = max(0, min(23, round((r + g + b) / 3 / 255 * 23)))
    gray_index = 232 + gray_level
    gray_value = 8 + gray_level * 10
    gray_rgb = (gray_value, gray_value, gray_value)

    def dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
        return sum((p - q) ** 2 for p, q in zip(a, b))

    return cube_index if dist(cube_rgb, rgb) <= dist(gray_rgb, rgb) else gray_index


def ansi256(name: str) -> int:
    """依語意名稱直接取得 ANSI 256 色代碼，終端機渲染器使用。"""
    return rgb_to_ansi256(resolve(name))
