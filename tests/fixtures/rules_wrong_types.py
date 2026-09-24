"""測試用的假 rules.py：每個函式都故意回傳錯誤的型別。"""


def can_play(player, hand_index):
    return "yes"  # 應該回傳 bool


def play_card(player, enemy, hand_index):
    return None  # 應該回傳字串


def enemy_act(enemy, player):
    return 123  # 應該回傳字串


def check_result(player, enemy):
    return "draw"  # 只能是 "win"、"lose" 或 None


def get_enemy_intent(enemy):
    return "attack"  # 應該回傳 dict


def create_player(card_list):
    return "not a dict"  # 應該回傳 dict


def create_enemy(enemy_data):
    return ["not", "a", "dict"]  # 應該回傳 dict
