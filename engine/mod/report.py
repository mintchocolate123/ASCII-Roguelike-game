"""載入報告與中文化錯誤訊息。"""
from __future__ import annotations

from dataclasses import dataclass, field

# pydantic v2 錯誤 type 字串 -> 中文說明。沒有對應的類型會顯示 pydantic 原文。
_ERROR_TYPE_MESSAGES = {
    "missing": "缺少欄位",
    "string_type": "型別錯誤，應該是文字",
    "int_type": "型別錯誤，應該是整數",
    "int_parsing": "型別錯誤，應該是整數",
    "float_type": "型別錯誤，應該是數字",
    "bool_type": "型別錯誤，應該是布林值（true/false）",
    "bool_parsing": "型別錯誤，應該是布林值（true/false）",
    "list_type": "型別錯誤，應該是清單",
    "dict_type": "型別錯誤，應該是物件",
    "string_too_long": "字串太長",
    "string_too_short": "字串太短",
    "string_pattern_mismatch": "格式不正確",
    "greater_than_equal": "數值超出範圍",
    "less_than_equal": "數值超出範圍",
    "greater_than": "數值超出範圍",
    "less_than": "數值超出範圍",
    "too_short": "數量超出範圍",
    "too_long": "數量超出範圍",
    "literal_error": "不在允許選項中",
    "enum": "不在允許選項中",
    "value_error": "數值不合法",
    "extra_forbidden": "有不認識的多餘欄位",
}


def translate_error_type(error_type: str, fallback_msg: str) -> str:
    """把 pydantic 的錯誤類型代碼轉成中文說明；沒有對應時顯示原文。"""
    return _ERROR_TYPE_MESSAGES.get(error_type, fallback_msg)


def _describe(error: dict) -> str:
    """取得錯誤的中文說明。自訂 field_validator 丟出的 ValueError（type=value_error）
    訊息本身已經是中文，去掉 pydantic 加上的「Value error, 」前綴直接使用；
    其他已知類型查表翻譯，沒有對應的顯示 pydantic 原文。"""
    msg = error.get("msg", "")
    if error["type"] == "value_error" and msg.startswith("Value error, "):
        return msg[len("Value error, "):]
    return translate_error_type(error["type"], msg)


def format_field_error(mod_id: str, filename: str, index: int | None, error: dict) -> str:
    """把單一 pydantic 錯誤轉成「mod id：檔案名稱，第 N 筆，欄位 X：說明，收到的值」格式。"""
    field_name = ".".join(str(p) for p in error["loc"]) or "(整筆資料)"
    desc = _describe(error)
    value = error.get("input", None)
    location = f"，第 {index + 1} 筆" if index is not None else ""
    return f"{mod_id}：{filename}{location}，欄位 {field_name}：{desc}，收到的值：{value!r}"


@dataclass
class ReportEntry:
    level: str  # "warning" | "error" | "fatal"
    message: str


@dataclass
class LoadReport:
    entries: list[ReportEntry] = field(default_factory=list)

    def warning(self, message: str) -> None:
        self.entries.append(ReportEntry("warning", message))

    def error(self, message: str) -> None:
        self.entries.append(ReportEntry("error", message))

    def fatal(self, message: str) -> None:
        self.entries.append(ReportEntry("fatal", message))

    @property
    def has_fatal(self) -> bool:
        return any(e.level == "fatal" for e in self.entries)

    @property
    def has_error(self) -> bool:
        return any(e.level in ("error", "fatal") for e in self.entries)

    def by_level(self, level: str) -> list[str]:
        return [e.message for e in self.entries if e.level == level]

    def format_text(self) -> str:
        labels = {"fatal": "【致命錯誤】", "error": "【錯誤】", "warning": "【警告】"}
        lines = [f"{labels.get(e.level, '')} {e.message}" for e in self.entries]
        if not lines:
            lines.append("載入完成，沒有任何問題。")
        return "\n".join(lines)
