"""啟動點：解析參數（--terminal）、載入 mod、進入主迴圈。預設使用 pygame 視窗。"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from engine.actions import Quit
from engine.bridge import Bridge, ModCallError
from engine.grid import Grid
from engine.mod.loader import load_mods
from engine.render.base import Renderer
from engine.run import build_starting_deck, pick_enemy
from engine.scenes.battle import BattleScene

REPO_ROOT = Path(__file__).resolve().parent
MODS_DIR = REPO_ROOT / "mods"
RULES_PATH = MODS_DIR / "core" / "rules.py"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ASCII 卡牌遊戲")
    parser.add_argument("--terminal", action="store_true", help="使用終端機渲染器（預設使用 pygame 視窗）")
    parser.add_argument("--enemy", default=None, help="指定要對戰的敵人完整 id，例如 core:goblin")
    return parser.parse_args(argv)


def _create_renderer(use_terminal: bool) -> Renderer | None:
    if use_terminal:
        from engine.render.terminal_renderer import TerminalRenderer

        return TerminalRenderer()

    from engine.render.pygame_renderer import FontLoadError, PygameRenderer

    try:
        return PygameRenderer()
    except FontLoadError as exc:
        print(f"無法啟動 pygame 視窗：{exc}")
        print("可以改用 python main.py --terminal 執行終端機版。")
        return None


def run_battle(use_terminal: bool, enemy_full_id: str | None) -> int:
    db, report = load_mods(MODS_DIR)
    print(report.format_text())
    print()

    if report.has_fatal:
        print("載入失敗，無法開始遊戲。")
        return 1

    input("按 Enter 開始戰鬥...")

    renderer = _create_renderer(use_terminal)
    if renderer is None:
        return 1

    bridge = Bridge(RULES_PATH)
    try:
        deck = build_starting_deck(db.cards)
        player = bridge.create_player(deck)
        enemy_data = pick_enemy(db.enemies, full_id=enemy_full_id, tier="normal")
        enemy = bridge.create_enemy(enemy_data)
    except ModCallError as exc:
        print("無法開始戰鬥：")
        print("\n".join(exc.panel_lines()))
        renderer.close()
        return 1
    except (KeyError, ValueError) as exc:
        print(f"無法開始戰鬥：{exc}")
        renderer.close()
        return 1

    scene = BattleScene(bridge, player, enemy)

    grid = Grid()
    scene.draw(grid)
    renderer.present(grid)

    last_time = time.perf_counter()
    while not scene.finished:
        actions = renderer.poll_actions()
        if any(isinstance(a, Quit) for a in actions):
            print("已離開遊戲。")
            renderer.close()
            return 0
        now = time.perf_counter()
        dt, last_time = now - last_time, now
        scene.handle(actions)
        scene.update(dt)
        grid = Grid()
        scene.draw(grid)
        renderer.present(grid)

    renderer.close()

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
    return run_battle(args.terminal, args.enemy)


if __name__ == "__main__":
    raise SystemExit(main())
