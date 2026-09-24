"""測試用的假 rules.py：create_player / create_enemy 回傳的 dict 缺少必要欄位。"""


def create_player(card_list):
    return {"name": "冒險者", "hp": 50}  # 缺少 max_hp、block、energy、draw_pile、hand、discard


def create_enemy(enemy_data):
    return {"id": enemy_data["full_id"], "hp": enemy_data["hp"]}  # 缺少大部分欄位
