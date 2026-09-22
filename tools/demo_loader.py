"""2 階段驗收 demo：

1. 載入目前 repo 裡的 mods/（core + example_mod），印出載入報告。
2. 把預設停用的 mods/_example_override/ 複製成不帶底線的資料夾，示範覆寫 core:strike。
3. 在暫時的資料夾裡建立幾個故意寫錯的 mod，示範各種錯誤訊息長什麼樣子，
   結束後暫時資料夾會自動刪除，不會留在 repo 裡。
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.mod.loader import load_mods

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_mod(mods_dir: Path, mod_id: str, *, depends=None, cards=None, enemies=None, run=None, art=None) -> None:
    mod_dir = mods_dir / mod_id
    mod_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"id": mod_id, "name": mod_id, "version": "1.0.0", "author": "demo", "depends": depends or []}
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


def demo_real_mods() -> None:
    print("=" * 70)
    print("Part 1：載入目前 repo 的 mods/（core + example_mod，不含覆寫）")
    print("=" * 70)
    db, report = load_mods(REPO_ROOT / "mods")
    print(report.format_text())
    print()
    print(f"啟用的 mod：{db.enabled_mods}")
    print(f"卡牌數量：{len(db.cards)}　敵人數量：{len(db.enemies)}　關卡數量：{len(db.run_stages)}")
    print(f"core:strike 傷害（example_mod 這次不會動它）：{db.cards['core:strike']['damage']}")
    print()


def demo_override_mod() -> None:
    print("=" * 70)
    print("Part 2：mods/_example_override/ 預設停用，複製成不帶底線的資料夾後示範覆寫")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp)
        shutil.copytree(REPO_ROOT / "mods" / "core", sandbox / "core")
        shutil.copytree(REPO_ROOT / "mods" / "_example_override", sandbox / "example_override")

        db, report = load_mods(sandbox)
        print(report.format_text())
        print()
        print(f"core:strike 傷害（已被覆寫成 8）：{db.cards['core:strike']['damage']}")
        print()


def demo_broken_mods() -> None:
    print("=" * 70)
    print("Part 3：故意寫錯的暫時 mod，示範各種錯誤訊息")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp)

        # 一個內容正常的 core，讓依賴解析能夠成立
        _write_mod(
            sandbox,
            "core",
            cards=[{"id": "strike", "name": "斬擊", "type": "attack", "cost": 1, "damage": 6}],
            enemies=[
                {
                    "id": "slime",
                    "name": "史萊姆",
                    "tier": "normal",
                    "hp": 10,
                    "art": "slime.txt",
                    "actions": [{"type": "attack", "value": 3}],
                }
            ],
            art={"slime.txt": "( o o )\n"},
        )

        # broken_content：依賴解析會成功，但裡面塞了各種單筆資料錯誤
        _write_mod(
            sandbox,
            "broken_content",
            depends=["core"],
            cards=[
                # 欄位錯誤：cost 超出 0-5 的範圍
                {"id": "too_expensive", "name": "天價卡", "type": "attack", "cost": 99, "damage": 1},
                # 欄位錯誤：type 不在允許的選項中
                {"id": "bad_type", "name": "壞類型", "type": "magic", "cost": 1, "damage": 1},
                # 卡名太長
                {"id": "long_name", "name": "這是一個超過十格寬的卡牌名稱", "type": "attack", "cost": 1, "damage": 1},
                # 描述超過 6 行
                {"id": "wordy", "name": "囉唆", "type": "skill", "cost": 1, "block": 1, "description": "字" * 60},
                # 佔位符引用了這張卡沒有值的欄位
                {
                    "id": "bad_placeholder",
                    "name": "壞卡",
                    "type": "attack",
                    "cost": 1,
                    "damage": 5,
                    "description": "造成 {damage} 點傷害，還會 {poison} 中毒。",
                },
                # 重複 id（跟下面同一個 id）
                {"id": "dup", "name": "重複", "type": "attack", "cost": 1, "damage": 3},
                {"id": "dup", "name": "重複二", "type": "attack", "cost": 1, "damage": 9},
                # 覆寫一個不存在的目標
                {"id": "ghost", "name": "幽靈", "type": "attack", "cost": 1, "damage": 1, "overrides": "core:does_not_exist"},
                # 這張是完全正常的卡，對照組：有問題的被跳過，正常的照樣載入
                {"id": "fine", "name": "正常卡", "type": "attack", "cost": 1, "damage": 4},
            ],
            enemies=[
                # 非法 ASCII 字元
                {
                    "id": "illegal_char",
                    "name": "非法字元怪",
                    "tier": "normal",
                    "hp": 10,
                    "art": "illegal.txt",
                    "actions": [{"type": "attack", "value": 1}],
                },
                # 圖檔過大（會被裁切但敵人仍然有效）
                {
                    "id": "oversized",
                    "name": "過大怪",
                    "tier": "normal",
                    "hp": 10,
                    "art": "oversized.txt",
                    "actions": [{"type": "attack", "value": 1}],
                },
            ],
            art={
                "illegal.txt": "abc\n中文不合法\n",
                "oversized.txt": "\n".join("x" * 30 for _ in range(15)),
            },
        )

        # 缺少依賴
        _write_mod(sandbox, "orphan_mod", depends=["ghost_mod_that_does_not_exist"])

        # 循環依賴
        _write_mod(sandbox, "cycle_a", depends=["cycle_b"])
        _write_mod(sandbox, "cycle_b", depends=["cycle_a"])

        db, report = load_mods(sandbox)
        print(report.format_text())
        print()
        print(f"啟用的 mod：{db.enabled_mods}")
        print(f"成功載入的卡牌 id：{sorted(db.cards.keys())}")
        print(f"成功載入的敵人 id：{sorted(db.enemies.keys())}")


def main() -> None:
    demo_real_mods()
    demo_override_mod()
    demo_broken_mods()


if __name__ == "__main__":
    main()
