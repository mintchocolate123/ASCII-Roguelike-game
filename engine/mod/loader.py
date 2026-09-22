"""掃描、排序、驗證、合併所有 mod 的內容。"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ..cardtext import CardTextError, resolve_description
from ..draw import wrap_text
from .models import CardDef, EnemyDef, ModManifest, RunStage
from .report import LoadReport, format_field_error

ART_MAX_WIDTH = 24
ART_MAX_HEIGHT = 10
DESCRIPTION_WIDTH = 10
DESCRIPTION_MAX_LINES = 6
FORBIDDEN_LEADING = "，。、；：！？）」』…"


class ModDatabase:
    def __init__(self) -> None:
        self.cards: dict[str, dict] = {}
        self.enemies: dict[str, dict] = {}
        self.run_stages: list[dict] = []
        self.enabled_mods: list[str] = []


def load_mods(mods_dir: str | Path) -> tuple[ModDatabase, LoadReport]:
    mods_dir = Path(mods_dir)
    report = LoadReport()
    db = ModDatabase()

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
            report.error(f"{entry.name}：找不到 mod.json，已停用整個 mod。")
            continue

        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.error(f"{entry.name}：mod.json 不是合法的 JSON（{exc}），已停用整個 mod。")
            continue

        try:
            manifest = ModManifest(**raw)
        except ValidationError as exc:
            for err in exc.errors():
                report.error(format_field_error(entry.name, "mod.json", None, err))
            report.error(f"{entry.name}：mod.json 驗證失敗，已停用整個 mod。")
            continue

        if manifest.id != entry.name:
            report.error(
                f"{entry.name}：mod.json 的 id「{manifest.id}」與資料夾名稱不一致，已停用整個 mod。"
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
        report.error(f"{mod_id}：{reason}，已停用整個 mod。")

    return order


# ---------------------------------------------------------------------------
# 內容載入
# ---------------------------------------------------------------------------


def _load_json_list(path: Path, mod_id: str, filename: str, report: LoadReport) -> list:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.error(f"{mod_id}：{filename} 不是合法的 JSON（{exc}）。")
        return []
    if not isinstance(raw, list):
        report.error(f"{mod_id}：{filename} 的內容應該是一個清單。")
        return []
    return raw


def _validate_records(model_cls, raw_list: list, mod_id: str, filename: str, report: LoadReport) -> list:
    valid = []
    for idx, raw in enumerate(raw_list):
        if not isinstance(raw, dict):
            report.warning(f"{mod_id}：{filename}，第 {idx + 1} 筆：不是合法的物件，已跳過。")
            continue
        try:
            model = model_cls(**raw)
        except ValidationError as exc:
            for err in exc.errors():
                report.warning(format_field_error(mod_id, filename, idx, err))
            continue
        valid.append(model)
    return valid


def _validate_card_description(card: CardDef, mod_id: str, filename: str, report: LoadReport) -> bool:
    """回傳 True 表示這張卡的描述有效。"""
    data = card.model_dump(exclude_none=True)

    if card.effect and not card.description:
        report.warning(
            f"{mod_id}：{filename}，卡牌 {card.id}：有 effect 的卡牌必須填寫 description，因為引擎無法從程式推測效果。"
        )
        return False

    try:
        text = resolve_description(data)
    except CardTextError as exc:
        report.warning(f"{mod_id}：{filename}，卡牌 {card.id}：{exc}")
        return False

    lines = wrap_text(text, DESCRIPTION_WIDTH)
    if len(lines) > DESCRIPTION_MAX_LINES:
        report.warning(
            f"{mod_id}：{filename}，卡牌 {card.id}：描述超過卡片空間，"
            f"換行後共 {len(lines)} 行，上限 {DESCRIPTION_MAX_LINES} 行。"
        )
        return False
    return True


def _validate_art(enemy: EnemyDef, mod_dir: Path, mod_id: str, filename: str, report: LoadReport) -> list[str] | None:
    art_path = mod_dir / "art" / enemy.art
    if not art_path.exists():
        report.warning(f"{mod_id}：{filename}，敵人 {enemy.id}：找不到 ASCII 圖檔「{enemy.art}」，已停用。")
        return None

    try:
        text = art_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        report.warning(f"{mod_id}：{filename}，敵人 {enemy.id}：ASCII 圖檔無法以 UTF-8 讀取，已停用。")
        return None

    lines = text.splitlines()
    while lines and lines[-1] == "":
        lines.pop()

    for row, line in enumerate(lines):
        for ch in line:
            code = ord(ch)
            if code < 32 or code > 126:
                report.warning(
                    f"{mod_id}：{filename}，敵人 {enemy.id}：ASCII 圖檔第 {row + 1} 行含有不允許的字元"
                    f"（{ch!r}，字元碼 {code}），只允許字元碼 32 到 126，已停用。"
                )
                return None

    if len(lines) > ART_MAX_HEIGHT or any(len(line) > ART_MAX_WIDTH for line in lines):
        report.warning(
            f"{mod_id}：{filename}，敵人 {enemy.id}：ASCII 圖檔超出最大尺寸 "
            f"{ART_MAX_WIDTH}×{ART_MAX_HEIGHT}，已裁切。"
        )
        lines = [line[:ART_MAX_WIDTH] for line in lines[:ART_MAX_HEIGHT]]

    return lines


def _full_id(mod_id: str, content_id: str) -> str:
    return f"{mod_id}:{content_id}"


def _merge_record(
    db_dict: dict[str, dict],
    mod_id: str,
    filename: str,
    content_id: str,
    data: dict,
    overrides: str | None,
    report: LoadReport,
) -> None:
    if overrides:
        if ":" not in overrides:
            report.warning(
                f"{mod_id}：{filename}，覆寫目標「{overrides}」格式不正確，應該是 mod_id:content_id，已跳過。"
            )
            return
        if overrides not in db_dict:
            report.warning(f"{mod_id}：{filename}，找不到要覆寫的目標「{overrides}」，已跳過。")
            return
        db_dict[overrides] = data
        report.warning(f"{mod_id}：{filename}，已覆寫「{overrides}」。")
        return

    full_id = _full_id(mod_id, content_id)
    if full_id in db_dict:
        report.warning(f"{mod_id}：{filename}，重複的 id「{full_id}」，已跳過這一筆。")
        return
    db_dict[full_id] = data


def _load_mod_content(mod_id: str, mod_dir: Path, db: ModDatabase, report: LoadReport) -> None:
    cards_raw = _load_json_list(mod_dir / "cards.json", mod_id, "cards.json", report)
    cards = _validate_records(CardDef, cards_raw, mod_id, "cards.json", report)
    for card in cards:
        if not _validate_card_description(card, mod_id, "cards.json", report):
            continue
        data = card.model_dump(exclude_none=True)
        data["full_id"] = _full_id(mod_id, card.id)
        _merge_record(db.cards, mod_id, "cards.json", card.id, data, card.overrides, report)

    enemies_raw = _load_json_list(mod_dir / "enemies.json", mod_id, "enemies.json", report)
    enemies = _validate_records(EnemyDef, enemies_raw, mod_id, "enemies.json", report)
    for enemy in enemies:
        art_lines = _validate_art(enemy, mod_dir, mod_id, "enemies.json", report)
        if art_lines is None:
            continue
        data = enemy.model_dump(exclude_none=True)
        data["art"] = art_lines
        data["full_id"] = _full_id(mod_id, enemy.id)
        _merge_record(db.enemies, mod_id, "enemies.json", enemy.id, data, enemy.overrides, report)

    run_path = mod_dir / "run.json"
    if run_path.exists():
        if mod_id != "core":
            report.warning(f"{mod_id}：只有 core 可以提供 run.json，這個檔案會被忽略。")
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
                report.error(f"core：run.json，第 {idx + 1} 筆：tier「{tier}」沒有任何敵人可用。")
