"""掃描、排序、驗證、合併所有 mod 的內容。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from pydantic import ValidationError

from ..cardtext import CardTextError, resolve_description
from ..draw import wrap_text
from .models import CardDef, EnemyDef, ModManifest, RunStage
from .registry import registry
from .report import LoadReport, format_field_error, format_location

ART_MAX_WIDTH = 24
ART_MAX_HEIGHT = 10
DESCRIPTION_WIDTH = 10
DESCRIPTION_MAX_LINES = 6


class ModDatabase:
    def __init__(self) -> None:
        self.cards: dict[str, dict] = {}
        self.enemies: dict[str, dict] = {}
        self.run_stages: list[dict] = []
        self.enabled_mods: list[str] = []
        # full_id -> (mod_id, filename, index)，用來在重複 id 時指出原本保留的那筆在哪裡
        self._card_origins: dict[str, tuple[str, str, int]] = {}
        self._enemy_origins: dict[str, tuple[str, str, int]] = {}


def load_mods(mods_dir: str | Path) -> tuple[ModDatabase, LoadReport]:
    mods_dir = Path(mods_dir)
    report = LoadReport()
    db = ModDatabase()
    registry.clear()  # 每次重新載入（含 F5 熱重載）都要清空舊的效果註冊，避免誤判成重複註冊

    manifests, mod_paths = _scan_manifests(mods_dir, report)
    order = _topo_sort(manifests, report)

    for mod_id in order:
        _load_mod_content(mod_id, mod_paths[mod_id], db, report)

    _check_cross_references(db, report)

    if "core" not in db.enabled_mods:
        report.fatal("core 沒有成功載入，遊戲無法啟動。")
    elif not db.cards and not db.enemies:
        report.fatal("core 沒有提供任何可用內容，遊戲無法啟動。")

    return db, report


# ---------------------------------------------------------------------------
# 掃描與 manifest 驗證
# ---------------------------------------------------------------------------


def _scan_manifests(mods_dir: Path, report: LoadReport) -> tuple[dict[str, ModManifest], dict[str, Path]]:
    manifests: dict[str, ModManifest] = {}
    mod_paths: dict[str, Path] = {}

    if not mods_dir.exists():
        report.fatal(f"找不到 mods 資料夾：{mods_dir}")
        return manifests, mod_paths

    for entry in sorted(mods_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue

        manifest_path = entry / "mod.json"
        if not manifest_path.exists():
            report.error(f"{format_location(entry.name, 'mod.json')}：找不到這個檔案，已停用整個 mod。")
            continue

        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.error(f"{format_location(entry.name, 'mod.json')} 不是合法的 JSON（{exc}），已停用整個 mod。")
            continue

        try:
            manifest = ModManifest(**raw)
        except ValidationError as exc:
            for err in exc.errors():
                report.error(
                    format_field_error(
                        entry.name, "mod.json", None, err,
                        model_cls=ModManifest, consequence="已停用整個 mod。",
                    )
                )
            continue

        if manifest.id != entry.name:
            report.error(
                f"{format_location(entry.name, 'mod.json')}：id「{manifest.id}」與資料夾名稱不一致，已停用整個 mod。"
            )
            continue

        manifests[manifest.id] = manifest
        mod_paths[manifest.id] = entry

    return manifests, mod_paths


# ---------------------------------------------------------------------------
# 拓撲排序：依 depends 排序，缺少依賴或循環依賴時停用相關 mod
# ---------------------------------------------------------------------------


def _topo_sort(manifests: dict[str, ModManifest], report: LoadReport) -> list[str]:
    disabled_reason: dict[str, str] = {}

    for mod_id, manifest in manifests.items():
        for dep in manifest.depends:
            if dep not in manifests:
                disabled_reason[mod_id] = f"缺少依賴：找不到 mod「{dep}」"
                break

    order: list[str] = []
    state: dict[str, str] = {}  # "temp" | "done"

    def visit(mod_id: str, stack: list[str]) -> bool:
        if mod_id in disabled_reason:
            return False
        if state.get(mod_id) == "done":
            return True
        if state.get(mod_id) == "temp":
            cycle = stack[stack.index(mod_id):] + [mod_id]
            for cid in cycle:
                disabled_reason.setdefault(cid, f"循環依賴：{' → '.join(cycle)}")
            return False

        state[mod_id] = "temp"
        ok = True
        for dep in manifests[mod_id].depends:
            if not visit(dep, stack + [mod_id]):
                ok = False
        if not ok:
            disabled_reason.setdefault(mod_id, "依賴的 mod 未能啟用")
            state[mod_id] = "done"
            return False
        state[mod_id] = "done"
        order.append(mod_id)
        return True

    for mod_id in manifests:
        visit(mod_id, [])

    for mod_id, reason in disabled_reason.items():
        report.error(f"{format_location(mod_id, 'mod.json')}：{reason}，已停用整個 mod。")

    return order


# ---------------------------------------------------------------------------
# 內容載入
# ---------------------------------------------------------------------------


def _record_id(raw: dict) -> str | None:
    value = raw.get("id")
    return str(value) if isinstance(value, str) else None


def _load_json_list(path: Path, mod_id: str, filename: str, report: LoadReport) -> list:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.error(f"{format_location(mod_id, filename)} 不是合法的 JSON（{exc}）。")
        return []
    if not isinstance(raw, list):
        report.error(f"{format_location(mod_id, filename)} 的內容應該是一個清單。")
        return []
    return raw


def _validate_records(model_cls, raw_list: list, mod_id: str, filename: str, report: LoadReport) -> list:
    valid = []
    for idx, raw in enumerate(raw_list):
        if not isinstance(raw, dict):
            report.warning(f"{format_location(mod_id, filename, idx)}：不是合法的物件，這筆資料已跳過。")
            continue
        try:
            model = model_cls(**raw)
        except ValidationError as exc:
            record_id = _record_id(raw)
            for err in exc.errors():
                report.warning(
                    format_field_error(
                        mod_id, filename, idx, err,
                        record_id=record_id, model_cls=model_cls,
                    )
                )
            continue
        valid.append(model)
    return valid


def _validate_card_description(card: CardDef, idx: int, mod_id: str, filename: str, report: LoadReport) -> str | None:
    """驗證並回傳代入數值後的描述文字；描述無效時回傳 None。"""
    data = card.model_dump(exclude_none=True)
    location = format_location(mod_id, filename, idx, card.id)

    if card.effect and not card.description:
        report.warning(
            f"{location}：有 effect 的卡牌必須填寫 description，因為引擎無法從程式推測效果，這筆資料已跳過。"
        )
        return None

    try:
        text = resolve_description(data)
    except CardTextError as exc:
        report.warning(f"{location}：{exc}這筆資料已跳過。")
        return None

    lines = wrap_text(text, DESCRIPTION_WIDTH)
    if len(lines) > DESCRIPTION_MAX_LINES:
        report.warning(
            f"{location}：描述超過卡片空間，換行後共 {len(lines)} 行，"
            f"上限 {DESCRIPTION_MAX_LINES} 行，這筆資料已跳過。"
        )
        return None
    return text


def _validate_art(
    enemy: EnemyDef, idx: int, mod_dir: Path, mod_id: str, filename: str, report: LoadReport
) -> list[str] | None:
    location = format_location(mod_id, filename, idx, enemy.id)
    art_path = mod_dir / "art" / enemy.art

    if not art_path.exists():
        report.warning(f"{location}：找不到 ASCII 圖檔「{enemy.art}」，已停用。")
        return None

    try:
        text = art_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        report.warning(f"{location}：ASCII 圖檔無法以 UTF-8 讀取，已停用。")
        return None

    lines = text.splitlines()
    while lines and lines[-1] == "":
        lines.pop()

    for row, line in enumerate(lines):
        for ch in line:
            code = ord(ch)
            if code < 32 or code > 126:
                report.warning(
                    f"{location}：ASCII 圖檔第 {row + 1} 行含有不允許的字元"
                    f"（{ch!r}，字元碼 {code}），只允許字元碼 32 到 126，已停用。"
                )
                return None

    if len(lines) > ART_MAX_HEIGHT or any(len(line) > ART_MAX_WIDTH for line in lines):
        report.warning(f"{location}：ASCII 圖檔超出最大尺寸 {ART_MAX_WIDTH}×{ART_MAX_HEIGHT}，已裁切。")
        lines = [line[:ART_MAX_WIDTH] for line in lines[:ART_MAX_HEIGHT]]

    return lines


def _full_id(mod_id: str, content_id: str) -> str:
    return f"{mod_id}:{content_id}"


def _merge_record(
    db_dict: dict[str, dict],
    origins: dict[str, tuple[str, str, int]],
    mod_id: str,
    filename: str,
    index: int,
    content_id: str,
    data: dict,
    overrides: str | None,
    report: LoadReport,
) -> None:
    location = format_location(mod_id, filename, index, content_id)

    if overrides:
        if ":" not in overrides:
            report.warning(
                f"{location}：覆寫目標「{overrides}」格式不正確，應該是 mod_id:content_id，這筆資料已跳過。"
            )
            return
        if overrides not in db_dict:
            report.warning(f"{location}：找不到要覆寫的目標「{overrides}」，這筆資料已跳過。")
            return
        db_dict[overrides] = data
        report.info(f"{location}：已覆寫「{overrides}」。")
        return

    full_id = _full_id(mod_id, content_id)
    if full_id in db_dict:
        kept_mod, kept_file, kept_idx = origins[full_id]
        kept_location = format_location(kept_mod, kept_file, kept_idx, content_id)
        report.warning(
            f"重複的 id「{full_id}」：保留 {kept_location}，跳過 {location}，這筆資料已跳過。"
        )
        return
    db_dict[full_id] = data
    origins[full_id] = (mod_id, filename, index)


# ---------------------------------------------------------------------------
# mod 腳本（第二階段）：scripts/*.py 用 @register_effect() 把 class 註冊進全域效果註冊表
# ---------------------------------------------------------------------------


def _exec_script(script_path: Path, mod_id: str) -> None:
    """用 importlib 執行一個 mod 腳本。腳本裡任何等級的例外（含 SyntaxError）都會往外拋，
    交給呼叫端接住，不在這裡吞掉。"""
    module_name = f"mods.{mod_id}.scripts.{script_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"無法載入腳本：{script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def _load_scripts(mod_id: str, mod_dir: Path, report: LoadReport) -> bool:
    """載入這個 mod 的 scripts/*.py，讓裡面用 @register_effect() 註冊的 class 進到全域註冊表。
    mod 腳本執行任意 Python：語法錯誤、註冊重複、註冊 id 格式錯誤，或腳本裡其他任何例外，
    都會停用整個 mod（回傳 False），呼叫端要跳過這個 mod 剩下的內容，不能讓遊戲崩潰。"""
    scripts_dir = mod_dir / "scripts"
    if not scripts_dir.exists():
        return True
    for script_path in sorted(scripts_dir.glob("*.py")):
        registry.begin_mod(mod_id)
        try:
            _exec_script(script_path, mod_id)
        except Exception as exc:  # 刻意攔截所有例外：mod 腳本可能寫出任何錯誤，不能讓引擎崩潰
            report.error(
                f"{format_location(mod_id, f'scripts/{script_path.name}')}："
                f"載入腳本失敗（{type(exc).__name__}：{exc}），已停用整個 mod。"
            )
            return False
        finally:
            registry.end_mod()
    return True


def _load_mod_content(mod_id: str, mod_dir: Path, db: ModDatabase, report: LoadReport) -> None:
    if not _load_scripts(mod_id, mod_dir, report):
        return  # 腳本載入失敗，整個 mod 停用，不合併這個 mod 的任何內容

    cards_raw = _load_json_list(mod_dir / "cards.json", mod_id, "cards.json", report)
    cards = _validate_records(CardDef, cards_raw, mod_id, "cards.json", report)
    for idx, card in enumerate(cards):
        description = _validate_card_description(card, idx, mod_id, "cards.json", report)
        if description is None:
            continue
        if card.effect is not None and not registry.has_effect(card.effect):
            report.warning(
                f"{format_location(mod_id, 'cards.json', idx, card.id)}："
                f"effect「{card.effect}」沒有對應的已註冊 class，這筆資料已跳過。"
            )
            continue
        data = card.model_dump(exclude_none=True)
        data["description"] = description
        data["full_id"] = _full_id(mod_id, card.id)
        _merge_record(db.cards, db._card_origins, mod_id, "cards.json", idx, card.id, data, card.overrides, report)

    enemies_raw = _load_json_list(mod_dir / "enemies.json", mod_id, "enemies.json", report)
    enemies = _validate_records(EnemyDef, enemies_raw, mod_id, "enemies.json", report)
    for idx, enemy in enumerate(enemies):
        art_lines = _validate_art(enemy, idx, mod_dir, mod_id, "enemies.json", report)
        if art_lines is None:
            continue
        data = enemy.model_dump(exclude_none=True)
        data["art"] = art_lines
        data["full_id"] = _full_id(mod_id, enemy.id)
        _merge_record(
            db.enemies, db._enemy_origins, mod_id, "enemies.json", idx, enemy.id, data, enemy.overrides, report
        )

    run_path = mod_dir / "run.json"
    if run_path.exists():
        if mod_id != "core":
            report.warning(f"{format_location(mod_id, 'run.json')}：只有 core 可以提供 run.json，這個檔案會被忽略。")
        else:
            run_raw = _load_json_list(run_path, mod_id, "run.json", report)
            stages = _validate_records(RunStage, run_raw, mod_id, "run.json", report)
            db.run_stages = [s.model_dump(exclude_none=True) for s in stages]

    db.enabled_mods.append(mod_id)


def _check_cross_references(db: ModDatabase, report: LoadReport) -> None:
    tiers_available = {e["tier"] for e in db.enemies.values()}
    for idx, stage in enumerate(db.run_stages):
        if stage["type"] == "battle":
            tier = stage.get("tier")
            if tier not in tiers_available:
                report.error(
                    f"{format_location('core', 'run.json', idx)}：tier「{tier}」沒有任何敵人可用。"
                )
