"""啟動點：解析參數（--terminal）、載入 mod、進入主迴圈。"""
from __future__ import annotations

import argparse
from pathlib import Path

from engine.actions import Quit
from engine.bridge import Bridge, ModCallError
from engine.grid import Grid
from engine.mod.loader import load_mods
from engine.render.terminal_renderer import TerminalRenderer
from engine.run import build_starting_deck, pick_enemy
from engine.scenes.battle import BattleScene

REPO_ROOT = Path(__file__).resolve().parent
MODS_DIR = REPO_ROOT / "mods"
RULES_PATH = MODS_DIR / "core" / "rules.py"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ASCII 卡牌遊戲")
    parser.add_argument("--terminal", action="store_true", help="使用終端機渲染器")
    parser.add_argument("--enemy", default=None, help="指定要對戰的敵人完整 id，例如 core:goblin")
    return parser.parse_args(argv)


def run_terminal(enemy_full_id: str | None) -> int:
    db, report = load_mods(MODS_DIR)
    print(report.format_text())
    print()

    if report.has_fatal:
        print("載入失敗，無法開始遊戲。")
        return 1

    input("按 Enter 開始戰鬥...")

    bridge = Bridge(RULES_PATH)
    try:
        deck = build_starting_deck(db.cards)
        player = bridge.create_player(deck)
        enemy_data = pick_enemy(db.enemies, full_id=enemy_full_id, tier="normal")
        enemy = bridge.create_enemy(enemy_data)
    except ModCallError as exc:
        print("無法開始戰鬥：")
        print("\n".join(exc.panel_lines()))
        return 1
    except (KeyError, ValueError) as exc:
        print(f"無法開始戰鬥：{exc}")
        return 1

    scene = BattleScene(bridge, player, enemy)
    renderer = TerminalRenderer()

    grid = Grid()
    scene.draw(grid)
    renderer.present(grid)

    while not scene.finished:
        actions = renderer.poll_actions()
        if any(isinstance(a, Quit) for a in actions):
            print("已離開遊戲。")
            return 0
        scene.handle(actions)
        scene.update(0.0)
        grid = Grid()
        scene.draw(grid)
        renderer.present(grid)

    if scene.fatal_error is not None:
        print("戰鬥因為錯誤而中止，已經安全回到停止狀態。")
        return 1
    if scene.result == "win":
        print("恭喜獲勝！")
    else:
        print("你被擊敗了。")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.terminal:
        return run_terminal(args.enemy)
    print("目前只支援 --terminal，pygame 版尚未實作。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
