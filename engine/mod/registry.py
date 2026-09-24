"""效果、狀態、遺物註冊表（第二階段）。

mod 在 scripts/*.py 裡用 @register_effect("本地 id") 把 class 註冊進引擎的全域效果註冊表；
loader 在執行某個 mod 的 scripts/*.py 期間會呼叫 begin_mod()/end_mod()，讓裝飾器知道要用哪個
mod id 組成完整 id「mod_id:本地id」存進去（跟卡牌、敵人的完整 id 規則一樣）。cards.json 的
effect 欄位用完整 id 引用這裡註冊的 class；loader 會檢查引用的完整 id 是否真的有註冊，
沒有就報錯並跳過那張卡（見 engine/mod/loader.py）。

這個模組只負責「完整 id -> class」的對應，不假設 class 要長什麼樣子；rules.py 用
get_effect(full_id) 找回 class 後自己決定怎麼實例化、呼叫（例如呼叫一個 apply(player, enemy,
card) 方法拿回顯示訊息，跟 damage、block、heal 等欄位的效果一起疊加執行）。

registry 是全域單例：每次呼叫 load_mods() 都會先 clear()，重新執行所有 mod 的 scripts/*.py，
確保熱重載（F5）之後拿到的都是最新版本的 class，不會有舊的殘留造成「重複註冊」的誤判。
"""
from __future__ import annotations

import re

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class RegistryError(Exception):
    """註冊過程中的錯誤：不是在 begin_mod()/end_mod() 之間呼叫、id 格式不對、重複註冊。
    loader 會接住並轉成中文報告，只停用來源的那個 mod，不會讓遊戲崩潰。"""


class EffectRegistry:
    def __init__(self) -> None:
        self._effects: dict[str, type] = {}
        self._current_mod_id: str | None = None

    # -- loader 專用：標記目前正在執行哪個 mod 的腳本 -----------------------

    def begin_mod(self, mod_id: str) -> None:
        """loader 在執行某個 mod 的 scripts/*.py 之前呼叫，讓這段期間的 register_effect()
        知道要用哪個 mod id 組成完整 id。"""
        self._current_mod_id = mod_id

    def end_mod(self) -> None:
        self._current_mod_id = None

    # -- mod 腳本用：註冊 class -------------------------------------------

    def register_effect(self, local_id: str):
        """裝飾器：@register_effect("本地 id")。只能在 mod 的 scripts/*.py 被 loader 執行期間
        使用（也就是 begin_mod()/end_mod() 之間），正常遊玩流程一定符合這個條件。"""
        if self._current_mod_id is None:
            raise RegistryError("register_effect() 只能在 mod 的 scripts/*.py 載入期間使用。")
        if not ID_PATTERN.match(local_id):
            raise RegistryError(
                f"效果 id「{local_id}」格式不正確：只能用小寫英文字母開頭，"
                "之後接小寫英文字母、數字或底線。"
            )
        full_id = f"{self._current_mod_id}:{local_id}"

        def decorator(cls: type) -> type:
            if full_id in self._effects:
                raise RegistryError(f"效果 id「{full_id}」重複註冊。")
            self._effects[full_id] = cls
            return cls

        return decorator

    # -- 查詢 ---------------------------------------------------------------

    def get_effect(self, full_id: str) -> type | None:
        return self._effects.get(full_id)

    def has_effect(self, full_id: str) -> bool:
        return full_id in self._effects

    # -- 每次 load_mods() 開始前呼叫，清空舊的註冊 ---------------------------

    def clear(self) -> None:
        self._effects = {}
        self._current_mod_id = None


registry = EffectRegistry()
register_effect = registry.register_effect
