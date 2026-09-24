"""core 的遊戲規則：第一堂課的練習目標。

這是一個普通的 Python 檔案，引擎會呼叫這裡的函式，名稱與回傳格式固定（見 CLAUDE.md）。
第一版只處理 damage、block、heal 三個欄位；hits、draw、energy、self_damage
留給學生當課後作業自己補上。

effect 欄位（第二階段）：資料組合不出來的效果，mod 會在自己的 scripts/*.py 裡用一個 class
實作，並用 @register_effect() 註冊進 engine.mod.registry。這裡只需要依卡牌的 effect 完整 id
找回那個 class、呼叫它的 apply(player, enemy, card) 方法，把回傳的訊息跟其他欄位的效果一起
顯示，不需要知道效果實際做了什麼。
"""
import random

from engine.mod.registry import registry

STARTING_HP = 50
STARTING_ENERGY = 3
HAND_SIZE = 5
MAX_HAND_SIZE = 7


def create_player(card_list):
    draw_pile = list(card_list)
    random.shuffle(draw_pile)
    return {
        "name": "冒險者",
        "hp": STARTING_HP,
        "max_hp": STARTING_HP,
        "block": 0,
        "energy": STARTING_ENERGY,
        "draw_pile": draw_pile,
        "hand": [],
        "discard": [],
    }


def create_enemy(enemy_data):
    return {
        "id": enemy_data["full_id"],
        "name": enemy_data["name"],
        "hp": enemy_data["hp"],
        "max_hp": enemy_data["hp"],
        "block": 0,
        "actions": enemy_data["actions"],
        "action_index": 0,
        "art": enemy_data["art"],
        "color": enemy_data["color"],
    }


def _draw_cards(player, count):
    for _ in range(count):
        if len(player["hand"]) >= MAX_HAND_SIZE:
            return
        if not player["draw_pile"]:
            if not player["discard"]:
                return
            player["draw_pile"] = player["discard"]
            player["discard"] = []
            random.shuffle(player["draw_pile"])
        player["hand"].append(player["draw_pile"].pop())


def start_turn(player):
    player["block"] = 0
    player["energy"] = STARTING_ENERGY
    player["discard"].extend(player["hand"])
    player["hand"] = []
    _draw_cards(player, HAND_SIZE)


def can_play(player, hand_index):
    if hand_index < 0 or hand_index >= len(player["hand"]):
        return False
    card = player["hand"][hand_index]
    return player["energy"] >= card["cost"]


def play_card(player, enemy, hand_index):
    card = player["hand"].pop(hand_index)
    player["energy"] -= card["cost"]

    messages = []
    if "effect" in card:
        effect_cls = registry.get_effect(card["effect"])
        if effect_cls is not None:
            messages.append(effect_cls().apply(player, enemy, card))
    if "damage" in card:
        dealt = card["damage"]
        absorbed = min(enemy["block"], dealt)
        enemy["block"] -= absorbed
        enemy["hp"] = max(0, enemy["hp"] - (dealt - absorbed))
        messages.append(f"造成 {dealt} 點傷害")
    if "block" in card:
        player["block"] += card["block"]
        messages.append(f"獲得 {card['block']} 點護盾")
    if "heal" in card:
        player["hp"] = min(player["max_hp"], player["hp"] + card["heal"])
        messages.append(f"回復 {card['heal']} 點生命")

    player["discard"].append(card)
    if not messages:
        messages.append("沒有效果")
    return f"你使用了{card['name']}，{'，'.join(messages)}。"


def end_turn(player):
    pass


def get_enemy_intent(enemy):
    return enemy["actions"][enemy["action_index"]]


def enemy_act(enemy, player):
    action = enemy["actions"][enemy["action_index"]]
    enemy["action_index"] = (enemy["action_index"] + 1) % len(enemy["actions"])

    if action["type"] == "attack":
        dealt = action["value"]
        absorbed = min(player["block"], dealt)
        player["block"] -= absorbed
        player["hp"] = max(0, player["hp"] - (dealt - absorbed))
        return f"{enemy['name']} 攻擊，造成 {dealt} 點傷害。"
    enemy["block"] += action["value"]
    return f"{enemy['name']} 獲得 {action['value']} 點護盾。"


def check_result(player, enemy):
    if enemy["hp"] <= 0:
        return "win"
    if player["hp"] <= 0:
        return "lose"
    return None
