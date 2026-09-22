import json
from pathlib import Path

from pydantic import ValidationError

from engine.mod.loader import load_mods
from engine.mod.models import CardDef
from engine.mod.report import LoadReport, format_field_error

REPO_MODS_DIR = Path(__file__).resolve().parent.parent / "mods"


def _write_mod(
    mods_dir: Path,
    mod_id: str,
    *,
    depends: list[str] | None = None,
    cards: list[dict] | None = None,
    enemies: list[dict] | None = None,
    run: list[dict] | None = None,
    art: dict[str, str] | None = None,
    manifest_overrides: dict | None = None,
) -> Path:
    mod_dir = mods_dir / mod_id
    mod_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": mod_id,
        "name": mod_id,
        "version": "1.0.0",
        "author": "test",
        "depends": depends or [],
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    (mod_dir / "mod.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    if cards is not None:
        (mod_dir / "cards.json").write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")
    if enemies is not None:
        (mod_dir / "enemies.json").write_text(json.dumps(enemies, ensure_ascii=False), encoding="utf-8")
    if run is not None:
        (mod_dir / "run.json").write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    if art:
        art_dir = mod_dir / "art"
        art_dir.mkdir(exist_ok=True)
        for filename, content in art.items():
            (art_dir / filename).write_text(content, encoding="utf-8")
    return mod_dir


# ---------------------------------------------------------------------------
# 真正的 core 可以正常載入
# ---------------------------------------------------------------------------


def test_real_core_and_example_mod_load_successfully():
    db, report = load_mods(REPO_MODS_DIR)
    assert not report.has_fatal, report.format_text()
    assert "core" in db.enabled_mods
    assert "example_mod" in db.enabled_mods
    assert len(db.cards) >= 10
    assert len(db.enemies) == 4
    # example_mod 只新增卡牌，不覆寫核心內容
    assert db.cards["core:strike"]["damage"] == 6
    assert "example_mod:quick_stab" in db.cards
    # 沒有任何警告或錯誤，只允許完全乾淨的載入
    assert not report.by_level("warning")
    assert not report.by_level("error")


def test_example_override_demo_mod_overrides_strike_when_enabled(tmp_path):
    """mods/_example_override/ 預設停用（底線開頭）；把它複製成不帶底線的資料夾就能示範覆寫。"""
    import shutil

    shutil.copytree(REPO_MODS_DIR / "core", tmp_path / "core")
    shutil.copytree(REPO_MODS_DIR / "_example_override", tmp_path / "example_override")

    db, report = load_mods(tmp_path)
    assert not report.has_fatal, report.format_text()
    assert db.cards["core:strike"]["damage"] == 8
    infos = report.by_level("info")
    assert any("已覆寫「core:strike」" in i for i in infos)


# ---------------------------------------------------------------------------
# 欄位錯誤
# ---------------------------------------------------------------------------


def test_field_out_of_range_skips_record_and_reports_chinese_message(tmp_path):
    _write_mod(
        tmp_path,
        "core",
        cards=[{"id": "bad_cost", "name": "壞卡", "type": "attack", "cost": 99, "damage": 1}],
    )
    db, report = load_mods(tmp_path)
    warnings = report.by_level("warning")
    assert any(
        "core" in w and "cards.json" in w and "第 1 筆" in w and "欄位 cost" in w and "數值超出範圍" in w and "99" in w
        for w in warnings
    ), report.format_text()
    assert db.cards == {}


def test_field_missing_required_field_reports_chinese_message(tmp_path):
    _write_mod(
        tmp_path,
        "core",
        cards=[{"id": "no_name", "type": "attack", "cost": 1, "damage": 1}],
    )
    db, report = load_mods(tmp_path)
    warnings = report.by_level("warning")
    assert any("欄位 name" in w and "缺少欄位" in w for w in warnings), report.format_text()
    assert db.cards == {}


# ---------------------------------------------------------------------------
# 重複 id
# ---------------------------------------------------------------------------


def test_duplicate_id_skips_second_record_and_warns(tmp_path):
    _write_mod(
        tmp_path,
        "core",
        cards=[
            {"id": "dup", "name": "重複", "type": "attack", "cost": 1, "damage": 3},
            {"id": "dup", "name": "重複二", "type": "attack", "cost": 1, "damage": 5},
        ],
    )
    db, report = load_mods(tmp_path)
    warnings = report.by_level("warning")
    assert any("重複的 id" in w and "core:dup" in w for w in warnings), report.format_text()
    assert db.cards["core:dup"]["damage"] == 3  # 保留第一筆，不默默覆蓋


# ---------------------------------------------------------------------------
# 缺少依賴
# ---------------------------------------------------------------------------


def test_missing_dependency_disables_mod(tmp_path):
    _write_mod(tmp_path, "core")
    _write_mod(tmp_path, "orphan", depends=["ghost"])
    db, report = load_mods(tmp_path)
    errors = report.by_level("error")
    assert any("orphan" in e and "缺少依賴" in e and "ghost" in e for e in errors), report.format_text()
    assert "orphan" not in db.enabled_mods


# ---------------------------------------------------------------------------
# 循環依賴
# ---------------------------------------------------------------------------


def test_circular_dependency_disables_both_mods(tmp_path):
    _write_mod(tmp_path, "core")
    _write_mod(tmp_path, "cycle_a", depends=["cycle_b"])
    _write_mod(tmp_path, "cycle_b", depends=["cycle_a"])
    db, report = load_mods(tmp_path)
    errors = report.by_level("error")
    assert any("循環依賴" in e for e in errors), report.format_text()
    assert "cycle_a" not in db.enabled_mods
    assert "cycle_b" not in db.enabled_mods
    # core 沒有牽連，應該正常啟用
    assert "core" in db.enabled_mods


# ---------------------------------------------------------------------------
# 覆寫
# ---------------------------------------------------------------------------


def test_override_replaces_target_and_reports(tmp_path):
    _write_mod(
        tmp_path,
        "core",
        cards=[{"id": "strike", "name": "斬擊", "type": "attack", "cost": 1, "damage": 6}],
    )
    _write_mod(
        tmp_path,
        "addon",
        depends=["core"],
        cards=[
            {
                "id": "strike_plus",
                "name": "斬擊＋",
                "type": "attack",
                "cost": 1,
                "damage": 9,
                "overrides": "core:strike",
            }
        ],
    )
    db, report = load_mods(tmp_path)
    assert db.cards["core:strike"]["damage"] == 9
    assert "addon:strike_plus" not in db.cards  # 覆寫會完整取代原資料，不會新增一筆
    # 覆寫成功是資訊等級，不是警告
    assert not any("已覆寫" in w for w in report.by_level("warning"))
    infos = report.by_level("info")
    assert any("已覆寫「core:strike」" in i and "mods/addon/cards.json" in i for i in infos), report.format_text()


def test_override_missing_target_is_skipped_with_warning(tmp_path):
    _write_mod(tmp_path, "core")
    _write_mod(
        tmp_path,
        "addon",
        depends=["core"],
        cards=[
            {
                "id": "ghost",
                "name": "幽靈",
                "type": "attack",
                "cost": 1,
                "damage": 1,
                "overrides": "core:does_not_exist",
            }
        ],
    )
    db, report = load_mods(tmp_path)
    warnings = report.by_level("warning")
    assert any("找不到要覆寫的目標" in w and "core:does_not_exist" in w for w in warnings), report.format_text()
    assert "core:does_not_exist" not in db.cards


# ---------------------------------------------------------------------------
# 非法 ASCII 字元
# ---------------------------------------------------------------------------


def test_illegal_ascii_char_in_art_disables_enemy(tmp_path):
    _write_mod(
        tmp_path,
        "core",
        enemies=[
            {
                "id": "ghost",
                "name": "鬼魂",
                "tier": "normal",
                "hp": 10,
                "art": "ghost.txt",
                "actions": [{"type": "attack", "value": 1}],
            }
        ],
        art={"ghost.txt": "abc\n中文不合法\n"},
    )
    db, report = load_mods(tmp_path)
    warnings = report.by_level("warning")
    assert any(
        "core:ghost".split(":")[0] in w and "ghost" in w and "不允許的字元" in w and "字元碼" in w
        for w in warnings
    ), report.format_text()
    assert "core:ghost" not in db.enemies


# ---------------------------------------------------------------------------
# 圖檔過大
# ---------------------------------------------------------------------------


def test_oversized_art_is_cropped_with_warning_but_enemy_still_loads(tmp_path):
    big_art = "\n".join("x" * 30 for _ in range(15))
    _write_mod(
        tmp_path,
        "core",
        enemies=[
            {
                "id": "giant",
                "name": "巨人",
                "tier": "boss",
                "hp": 100,
                "art": "giant.txt",
                "actions": [{"type": "attack", "value": 1}],
            }
        ],
        art={"giant.txt": big_art},
    )
    db, report = load_mods(tmp_path)
    warnings = report.by_level("warning")
    assert any("超出最大尺寸" in w and "已裁切" in w for w in warnings), report.format_text()
    assert "core:giant" in db.enemies
    art_lines = db.enemies["core:giant"]["art"]
    assert len(art_lines) <= 10
    assert all(len(line) <= 24 for line in art_lines)


# ---------------------------------------------------------------------------
# 卡名太長
# ---------------------------------------------------------------------------


def test_card_name_too_long_reports_chinese_message(tmp_path):
    _write_mod(
        tmp_path,
        "core",
        cards=[
            {
                "id": "long_name",
                "name": "這是一個超過十格寬的卡牌名稱",
                "type": "attack",
                "cost": 1,
                "damage": 1,
            }
        ],
    )
    db, report = load_mods(tmp_path)
    warnings = report.by_level("warning")
    assert any("卡名太長" in w for w in warnings), report.format_text()
    assert db.cards == {}


# ---------------------------------------------------------------------------
# 描述超過 6 行
# ---------------------------------------------------------------------------


def test_description_too_many_lines_disables_card(tmp_path):
    long_desc = "字" * 60
    _write_mod(
        tmp_path,
        "core",
        cards=[
            {
                "id": "wordy",
                "name": "囉唆",
                "type": "skill",
                "cost": 1,
                "block": 1,
                "description": long_desc,
            }
        ],
    )
    db, report = load_mods(tmp_path)
    warnings = report.by_level("warning")
    assert any(
        "wordy" in w and "描述超過卡片空間" in w and "上限 6 行" in w for w in warnings
    ), report.format_text()
    assert db.cards == {}


# ---------------------------------------------------------------------------
# 佔位符錯誤
# ---------------------------------------------------------------------------


def test_placeholder_referencing_missing_field_disables_card(tmp_path):
    _write_mod(
        tmp_path,
        "core",
        cards=[
            {
                "id": "bad_ph",
                "name": "壞卡",
                "type": "attack",
                "cost": 1,
                "damage": 5,
                "description": "造成 {damage} 點傷害，還會 {poison} 中毒。",
            }
        ],
    )
    db, report = load_mods(tmp_path)
    warnings = report.by_level("warning")
    assert any("bad_ph" in w and "poison" in w for w in warnings), report.format_text()
    assert db.cards == {}


# ---------------------------------------------------------------------------
# 其他：跨檔參照、停用資料夾、manifest 錯誤
# ---------------------------------------------------------------------------


def test_run_stage_tier_without_enemies_reports_error(tmp_path):
    _write_mod(tmp_path, "core", enemies=[], run=[{"type": "battle", "tier": "boss"}])
    db, report = load_mods(tmp_path)
    errors = report.by_level("error")
    assert any("boss" in e and "沒有任何敵人可用" in e for e in errors), report.format_text()


def test_disabled_mod_folder_starting_with_underscore_is_skipped(tmp_path):
    _write_mod(tmp_path, "core")
    _write_mod(tmp_path, "_disabled_addon", depends=["core"])
    db, report = load_mods(tmp_path)
    assert "_disabled_addon" not in db.enabled_mods
    assert not any("_disabled_addon" in e.message for e in report.entries)


def test_missing_manifest_disables_mod(tmp_path):
    (tmp_path / "broken").mkdir()
    db, report = load_mods(tmp_path)
    errors = report.by_level("error")
    assert any("mods/broken/mod.json" in e and "找不到這個檔案" in e for e in errors)


def test_malformed_manifest_json_disables_mod(tmp_path):
    mod_dir = tmp_path / "broken"
    mod_dir.mkdir()
    (mod_dir / "mod.json").write_text("{not valid json", encoding="utf-8")
    db, report = load_mods(tmp_path)
    errors = report.by_level("error")
    assert any("broken" in e and "不是合法的 JSON" in e for e in errors)


def test_no_core_is_fatal(tmp_path):
    _write_mod(tmp_path, "example_mod", depends=[])
    db, report = load_mods(tmp_path)
    assert report.has_fatal
    assert any("core" in e for e in report.by_level("fatal"))


# ---------------------------------------------------------------------------
# report.py：pydantic 錯誤轉中文、報告格式
# ---------------------------------------------------------------------------


def test_format_field_error_translates_range_error_with_constraint():
    try:
        CardDef(id="x", name="x", type="attack", cost=99)
    except ValidationError as exc:
        errors = exc.errors()
    msg = format_field_error("core", "cards.json", 0, errors[0], record_id="x", model_cls=CardDef)
    assert msg == (
        "mods/core/cards.json，第 1 筆（id：x），欄位 cost：數值超出範圍，必須介於 0 到 5，"
        "收到的值：99，這筆資料已跳過。"
    )


def test_format_field_error_translates_missing_field():
    try:
        CardDef(id="x", type="attack", cost=1)  # 缺少 name
    except ValidationError as exc:
        errors = exc.errors()
    msg = format_field_error("core", "cards.json", 2, errors[0], model_cls=CardDef)
    assert "第 3 筆" in msg
    assert "欄位 name：缺少欄位" in msg
    assert "這筆資料已跳過。" in msg


def test_format_field_error_translates_literal_enum_with_options():
    try:
        CardDef(id="x", name="x", type="not_a_type", cost=1)
    except ValidationError as exc:
        errors = exc.errors()
    msg = format_field_error("core", "cards.json", 0, errors[0], model_cls=CardDef)
    assert "只能是 attack、skill、power 其中之一" in msg


def test_format_field_error_without_record_id_omits_parentheses():
    try:
        CardDef(id="x", type="attack", cost=1)
    except ValidationError as exc:
        errors = exc.errors()
    msg = format_field_error("core", "cards.json", 0, errors[0], model_cls=CardDef)
    assert "（id：" not in msg
    assert "mods/core/cards.json，第 1 筆，欄位" in msg


def test_load_report_format_text_includes_level_labels():
    report = LoadReport()
    report.info("i1")
    report.warning("w1")
    report.error("e1")
    report.fatal("f1")
    text = report.format_text()
    assert "【資訊】 i1" in text
    assert "【警告】 w1" in text
    assert "【錯誤】 e1" in text
    assert "【致命錯誤】 f1" in text


def test_load_report_empty_has_friendly_text():
    report = LoadReport()
    assert "沒有任何問題" in report.format_text()
