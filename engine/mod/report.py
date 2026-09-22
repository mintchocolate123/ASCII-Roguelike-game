"""載入報告與中文化錯誤訊息。"""
from __future__ import annotations

import typing
from dataclasses import dataclass, field

from .models import ID_PATTERN

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


def _literal_options(annotation) -> tuple | None:
    """如果欄位型別是 Literal（或 Optional[Literal]），回傳允許的選項。"""
    origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        return typing.get_args(annotation)
    if origin is typing.Union:
        for arg in typing.get_args(annotation):
            if typing.get_origin(arg) is typing.Literal:
                return typing.get_args(arg)
    return None


def describe_constraint(model_cls, field_name: str) -> str | None:
    """依 pydantic 模型的欄位定義組出限制條件說明，例如「必須介於 0 到 5」「只能是
    attack、skill、power 其中之一」。只處理最上層欄位，巢狀欄位（例如 actions 底下的
    type）不會有這段說明。"""
    if model_cls is None or not hasattr(model_cls, "model_fields"):
        return None
    info = model_cls.model_fields.get(field_name)
    if info is None:
        return None

    ge = le = gt = lt = min_len = max_len = pattern = None
    for m in info.metadata:
        if hasattr(m, "ge"):
            ge = m.ge
        if hasattr(m, "le"):
            le = m.le
        if hasattr(m, "gt"):
            gt = m.gt
        if hasattr(m, "lt"):
            lt = m.lt
        if hasattr(m, "min_length"):
            min_len = m.min_length
        if hasattr(m, "max_length"):
            max_len = m.max_length
        if hasattr(m, "pattern"):
            pattern = m.pattern

    if ge is not None and le is not None:
        return f"必須介於 {ge} 到 {le}"
    if ge is not None:
        return f"必須大於等於 {ge}"
    if le is not None:
        return f"必須小於等於 {le}"
    if gt is not None:
        return f"必須大於 {gt}"
    if lt is not None:
        return f"必須小於 {lt}"
    if min_len is not None and max_len is not None:
        return f"長度必須介於 {min_len} 到 {max_len}"
    if min_len is not None:
        return f"至少需要 {min_len} 個"
    if max_len is not None:
        return f"長度最多 {max_len}"
    if pattern == ID_PATTERN:
        return "只能使用小寫英文字母、數字與底線，且開頭必須是英文字母"
    if pattern:
        return f"格式必須符合「{pattern}」"

    options = _literal_options(info.annotation)
    if options:
        return "只能是 " + "、".join(str(o) for o in options) + " 其中之一"

    return None


def _describe(error: dict, model_cls) -> str:
    """取得錯誤的中文說明。自訂 field_validator 丟出的 ValueError（type=value_error）
    訊息本身已經是中文，去掉 pydantic 加上的「Value error, 」前綴直接使用，維持原樣；
    其他類型查表翻譯後，盡量再補上這個欄位的限制條件。"""
    msg = error.get("msg", "")
    if error["type"] == "value_error" and msg.startswith("Value error, "):
        return msg[len("Value error, "):]

    base = translate_error_type(error["type"], msg)
    if len(error["loc"]) == 1:
        constraint = describe_constraint(model_cls, str(error["loc"][0]))
        if constraint:
            return f"{base}，{constraint}"
    return base


def format_location(mod_id: str, filename: str, index: int | None = None, record_id: str | None = None) -> str:
    """統一的位置格式：mods/<資料夾>/<檔名>，第 N 筆（id：xxx）。id 讀不到時省略括號。"""
    location = f"mods/{mod_id}/{filename}"
    if index is not None:
        location += f"，第 {index + 1} 筆"
        if record_id is not None:
            location += f"（id：{record_id}）"
    return location


def format_field_error(
    mod_id: str,
    filename: str,
    index: int | None,
    error: dict,
    *,
    record_id: str | None = None,
    model_cls=None,
    consequence: str = "這筆資料已跳過。",
) -> str:
    """把單一 pydantic 錯誤轉成統一格式的中文訊息，結尾附上這筆資料的下場。"""
    field_name = ".".join(str(p) for p in error["loc"]) or "(整筆資料)"
    desc = _describe(error, model_cls)
    value = error.get("input", None)
    location = format_location(mod_id, filename, index, record_id)
    return f"{location}，欄位 {field_name}：{desc}，收到的值：{value!r}，{consequence}"


@dataclass
class ReportEntry:
    level: str  # "info" | "warning" | "error" | "fatal"
    message: str


@dataclass
class LoadReport:
    entries: list[ReportEntry] = field(default_factory=list)

    def info(self, message: str) -> None:
        self.entries.append(ReportEntry("info", message))

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
        labels = {"fatal": "【致命錯誤】", "error": "【錯誤】", "warning": "【警告】", "info": "【資訊】"}
        lines = [f"{labels.get(e.level, '')} {e.message}" for e in self.entries]
        if not lines:
            lines.append("載入完成，沒有任何問題。")
        return "\n".join(lines)
