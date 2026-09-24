"""測試用的假 rules.py：故意不實作 play_card，用來測試「缺少必要函式」的錯誤訊息。"""


def create_player(card_list):
    return {
        "name": "冒險者",
        "hp": 50,
        "max_hp": 50,
        "block": 0,
        "energy": 3,
        "draw_pile": [],
        "hand": [],
        "discard": [],
    }


def can_play(player, hand_index):
    return True


# 故意沒有實作 play_card
