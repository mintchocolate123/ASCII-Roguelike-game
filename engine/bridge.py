"""呼叫 mod 程式碼的唯一出入口。scene 不得直接 import mod 模組，只能透過這裡。

任何一次呼叫 rules.py 的函式都包在 try/except 中：出錯時不會讓引擎崩潰，而是
包成 ModCallError，附上函式名稱、例外類型、mod 檔案裡的行號與那一行程式碼，
交給呼叫端（battle scene）決定怎麼安全地繼續下去。
"""
from __future__ import annotations

import importlib.util
import inspect
import linecache
import os
from pathlib import Path
from types import ModuleType

REQUIRED_PLAYER_FIELDS = ("name", "hp", "max_hp", "block", "energy", "draw_pile", "hand", "discard")
REQUIRED_ENEMY_FIELDS = ("id", "name", "hp", "max_hp", "block", "actions", "action_index", "art", "color")

HOOK_NAMES = (
    "on_battle_start",
    "on_turn_start",
    "before_play",
    "after_play",
    "on_turn_end",
    "on_battle_end",
)


def _display_path(path: Path) -> str:
    try:
        return os.path.relpath(path, start=Path.cwd())
    except ValueError:
        return str(path)


class RulesReloadError(Exception):
    """F5 熱重載 rules.py 失敗時使用；bridge.rules 這時仍然是重載前那個還能用的版本。"""


class ModCallError(Exception):
    """呼叫 mod 函式失敗時的統一例外，帶著可以直接顯示給學生看的中文說明。"""

    def __init__(
        self,
        function_name: str,
        explanation: str,
        *,
        exc: BaseException | None = None,
        file_path: str | None = None,
        line_number: int | None = None,
        source_line: str | None = None,
    ) -> None:
        self.function_name = function_name
        self.explanation = explanation
        self.exc = exc
        self.file_path = file_path
        self.line_number = line_number
        self.source_line = source_line
        super().__init__(explanation)

    def panel_lines(self) -> list[str]:
        """把這個錯誤排成錯誤面板要顯示的每一行文字。"""
        lines = [f"函式：{self.function_name}"]
        if self.exc is not None:
            lines.append(f"例外類型：{type(self.exc).__name__}")
        if self.file_path is not None:
            location = self.file_path
            if self.line_number is not None:
                location += f"，第 {self.line_number} 行"
            lines.append(f"位置：{location}")
        if self.source_line is not None and self.source_line.strip():
            lines.append(f"程式碼：{self.source_line.strip()}")
        lines.append(self.explanation)
        return lines


class Bridge:
    def __init__(self, rules_path: str | Path) -> None:
        self.rules_path = Path(rules_path)
        self.rules: ModuleType = self._load_rules_module()

    # ------------------------------------------------------------------
    # 載入與熱重載
    # ------------------------------------------------------------------

    def _load_rules_module(self) -> ModuleType:
        spec = importlib.util.spec_from_file_location("mods.core.rules", self.rules_path)
        if spec is None or spec.loader is None:
            raise FileNotFoundError(f"找不到 rules.py：{self.rules_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        linecache.checkcache(str(self.rules_path))
        return module

    def reload(self) -> None:
        """F5：重新從磁碟載入 rules.py，讓學生的修改立即生效。

        載入失敗時（例如語法錯誤、匯入失敗）會拋出 RulesReloadError，
        並保留原本還能用的 rules 模組，不會讓遊戲因此壞掉。
        """
        try:
            new_rules = self._load_rules_module()
        except Exception as exc:  # 刻意攔截所有例外，載入失敗不能讓引擎崩潰
            raise RulesReloadError(
                f"重新載入 rules.py 失敗，已繼續使用原本的版本。\n{type(exc).__name__}：{exc}"
            ) from exc
        self.rules = new_rules

    # ------------------------------------------------------------------
    # 錯誤面板組裝
    # ------------------------------------------------------------------

    def _mod_root(self) -> Path:
        return self.rules_path.resolve().parent

    def _find_mod_frame(self, exc: BaseException) -> tuple[str, int, str] | None:
        """從 traceback 找出屬於 mod 檔案的那個 frame（取最深的一個），
        不要只顯示引擎內部呼叫鏈的最後一個 frame。"""
        mod_root = self._mod_root()
        found: tuple[str, int, str] | None = None
        tb = exc.__traceback__
        while tb is not None:
            filename = Path(tb.tb_frame.f_code.co_filename)
            try:
                resolved = filename.resolve()
            except OSError:
                resolved = filename
            if mod_root in resolved.parents or resolved == mod_root:
                lineno = tb.tb_lineno
                source_line = linecache.getline(str(filename), lineno)
                found = (_display_path(resolved), lineno, source_line)
            tb = tb.tb_next
        return found

    def _exception_error(self, function_name: str, exc: Exception) -> ModCallError:
        frame_info = self._find_mod_frame(exc)
        file_path = line_number = source_line = None
        if frame_info is not None:
            file_path, line_number, source_line = frame_info
        return ModCallError(
            function_name,
            f"{function_name} 執行時發生錯誤：{exc}",
            exc=exc,
            file_path=file_path,
            line_number=line_number,
            source_line=source_line,
        )

    def _missing_function_error(self, function_name: str) -> ModCallError:
        return ModCallError(
            function_name,
            f"rules.py 沒有實作 {function_name}，這是遊戲必須的函式。",
            file_path=_display_path(self.rules_path),
        )

    def _format_error(self, function_name: str, explanation: str) -> ModCallError:
        file_path = line_number = None
        func = getattr(self.rules, function_name, None)
        if func is not None:
            try:
                _, line_number = inspect.getsourcelines(func)
                file_path = _display_path(Path(inspect.getsourcefile(func)))
            except (OSError, TypeError):
                pass
        return ModCallError(function_name, explanation, file_path=file_path, line_number=line_number)

    # ------------------------------------------------------------------
    # 通用呼叫
    # ------------------------------------------------------------------

    def _invoke(self, function_name: str, *args):
        func = getattr(self.rules, function_name, None)
        if func is None:
            raise self._missing_function_error(function_name)
        try:
            return func(*args)
        except Exception as exc:  # 刻意攔截所有例外，避免 mod 的錯誤讓引擎崩潰
            raise self._exception_error(function_name, exc) from exc

    def call_hook(self, name: str, *args) -> None:
        """呼叫 on_battle_start 等選用的時機點；沒有實作就直接跳過，不算錯誤。"""
        if name not in HOOK_NAMES:
            raise ValueError(f"不是合法的呼叫時機：{name}")
        func = getattr(self.rules, name, None)
        if func is None:
            return
        try:
            func(*args)
        except Exception as exc:
            raise self._exception_error(name, exc) from exc

    # ------------------------------------------------------------------
    # dict / to_dict() 相容層
    # ------------------------------------------------------------------

    @staticmethod
    def _as_dict(obj) -> dict | None:
        if isinstance(obj, dict):
            return obj
        to_dict = getattr(obj, "to_dict", None)
        if callable(to_dict):
            result = to_dict()
            return result if isinstance(result, dict) else None
        return None

    def _require_fields(self, function_name: str, result, fields: tuple[str, ...]) -> None:
        view = self._as_dict(result)
        if view is None:
            raise self._format_error(
                function_name,
                f"{function_name} 應該回傳 dict（或有 to_dict() 方法的物件），"
                f"但回傳了 {result!r}。",
            )
        missing = [f for f in fields if f not in view]
        if missing:
            raise self._format_error(
                function_name,
                f"{function_name} 回傳的資料缺少必要欄位：{'、'.join(missing)}。",
            )

    def player_view(self, player) -> dict:
        view = self._as_dict(player)
        if view is None:
            raise self._format_error("player_view", f"player 不是 dict 也沒有 to_dict()：{player!r}。")
        return view

    def enemy_view(self, enemy) -> dict:
        view = self._as_dict(enemy)
        if view is None:
            raise self._format_error("enemy_view", f"enemy 不是 dict 也沒有 to_dict()：{enemy!r}。")
        return view

    # ------------------------------------------------------------------
    # rules.py 介面：型別固定的呼叫點
    # ------------------------------------------------------------------

    def create_player(self, card_list: list[dict]):
        result = self._invoke("create_player", card_list)
        self._require_fields("create_player", result, REQUIRED_PLAYER_FIELDS)
        return result

    def create_enemy(self, enemy_data: dict):
        result = self._invoke("create_enemy", enemy_data)
        self._require_fields("create_enemy", result, REQUIRED_ENEMY_FIELDS)
        return result

    def start_turn(self, player) -> None:
        self._invoke("start_turn", player)

    def can_play(self, player, hand_index: int) -> bool:
        result = self._invoke("can_play", player, hand_index)
        if not isinstance(result, bool):
            raise self._format_error("can_play", f"can_play 應該回傳布林值（True 或 False），但回傳了 {result!r}。")
        return result

    def play_card(self, player, enemy, hand_index: int) -> str:
        result = self._invoke("play_card", player, enemy, hand_index)
        if not isinstance(result, str):
            raise self._format_error("play_card", f"play_card 應該回傳字串，但回傳了 {result!r}。")
        return result

    def end_turn(self, player) -> None:
        self._invoke("end_turn", player)

    def get_enemy_intent(self, enemy) -> dict:
        result = self._invoke("get_enemy_intent", enemy)
        if not isinstance(result, dict):
            raise self._format_error("get_enemy_intent", f"get_enemy_intent 應該回傳 dict，但回傳了 {result!r}。")
        return result

    def enemy_act(self, enemy, player) -> str:
        result = self._invoke("enemy_act", enemy, player)
        if not isinstance(result, str):
            raise self._format_error("enemy_act", f"enemy_act 應該回傳字串，但回傳了 {result!r}。")
        return result

    def check_result(self, player, enemy) -> str | None:
        result = self._invoke("check_result", player, enemy)
        if result not in ("win", "lose", None):
            raise self._format_error(
                "check_result", f'check_result 應該回傳 "win"、"lose" 或 None，但回傳了 {result!r}。'
            )
        return result
