"""example_mod 的特殊卡牌效果：資料欄位組合不出來的效果，用 class 實作。

教學重點：用 @register_effect("本地 id") 把 class 註冊進引擎的效果註冊表，cards.json 用
「mod_id:本地id」的完整 id 引用（這裡是 example_mod:shield_slam）。mods/core/rules.py 的
play_card() 看到卡牌有 effect 欄位時，會從註冊表找到這個 class，呼叫 apply(player, enemy,
card) 拿到要顯示的訊息，跟 damage、block、heal 等欄位的效果一起疊加執行。
"""
from engine.mod.registry import register_effect


@register_effect("shield_slam")
class ShieldSlam:
    """護盾猛擊：造成等同目前護盾值的傷害。這種「引用玩家另一個數值」的效果，
    光靠 cards.json 的 damage/block/heal 欄位組合不出來，所以用 class 實作。"""

    def apply(self, player, enemy, card):
        dealt = player.get("block", 0)
        enemy["hp"] = max(0, enemy["hp"] - dealt)
        return f"造成等同護盾值的 {dealt} 點傷害"
