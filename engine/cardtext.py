"""卡牌描述：佔位符代入與自動產生。不處理換行（換行由 draw.wrap_text 負責）。"""
from __future__ import annotations

import re

PLACEHOLDER_FIELDS = ("damage", "hits", "block", "heal", "draw", "energy", "self_damage")

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_]+)\}")

# 依序自動產生描述時使用的欄位與模板；damage 依是否有 hits 分成兩種模板。
_AUTO_TEMPLATES = (
    ("block", "獲得 {block} 點護盾。"),
    ("heal", "回復 {heal} 點生命。"),
    ("draw", "抽 {draw} 張牌。"),
    ("energy", "獲得 {energy} 點能量。"),
    ("self_damage", "失去 {self_damage} 點生命。"),
)


class CardTextError(ValueError):
    """描述佔位符引用了不存在或沒有值的欄位。"""


def _numeric_fields(card: dict, values: dict | None) -> dict:
    available = {k: card[k] for k in PLACEHOLDER_FIELDS if k in card}
    if values:
        for k, v in values.items():
            if k in available:
                available[k] = v
    return available


def _auto_generate(card: dict, numeric: dict) -> str:
    parts: list[str] = []
    if "damage" in card:
        if "hits" in card:
            parts.append(f"造成 {numeric['damage']} 點傷害，重複 {numeric['hits']} 次。")
        else:
            parts.append(f"造成 {numeric['damage']} 點傷害。")
    for field, template in _AUTO_TEMPLATES:
        if field in card:
            parts.append(template.format(**{field: numeric[field]}))
    return "".join(parts)


def resolve_description(card: dict, values: dict | None = None) -> str:
    """回傳卡牌最終顯示的描述文字。

    card 是卡牌資料（至少含有已設定數值的欄位），values 可傳入修正後的數值
    （例如力量加成），只會覆寫 card 中已存在的欄位，不會讓原本沒有值的欄位變成可用。
    """
    numeric = _numeric_fields(card, values)
    template = card.get("description")
    if not template:
        return _auto_generate(card, numeric)

    for match in _PLACEHOLDER_RE.finditer(template):
        name = match.group(1)
        if name not in PLACEHOLDER_FIELDS or name not in numeric:
            raise CardTextError(
                f"描述使用了無法代入的佔位符 {{{name}}}：這張卡沒有 {name} 的數值。"
            )
    try:
        return template.format(**numeric)
    except (KeyError, IndexError, ValueError) as exc:
        raise CardTextError(f"描述格式錯誤，無法代入數值：{exc}") from exc
