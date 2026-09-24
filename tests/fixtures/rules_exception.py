"""測試用的假 rules.py：故意讓 play_card 透過巢狀函式拋出例外，
用來驗證 bridge 能找到 mod 檔案裡「最深」的那個 frame，而不是隨便顯示引擎內部的 frame。
"""


def _apply_damage(enemy, card):
    enemy["hp"] = enemy["hp"] - card["damage_that_does_not_exist"]


def play_card(player, enemy, hand_index):
    card = player["hand"][hand_index]
    _apply_damage(enemy, card)
    return "造成傷害"
