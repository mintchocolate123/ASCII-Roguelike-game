"""啟動點：解析參數（--terminal）、載入 mod、進入主迴圈。預設使用 pygame 視窗。

一般玩法從 loading 進場：loading -> title -> (battle -> reward 或 rest -> 下一關...) -> result，
result 可以重新開始（回到 title）或離開。

--enemy 保留給開發測試用：指定敵人完整 id 時跳過整個流程，直接打一場單場戰鬥。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from engine.actions import Quit
from engine.bridge import Bridge, ModCallError
from engine.grid import Grid
from engine.mod.loader import load_mods
from engine.mod.report import LoadReport
from engine.render.base import Renderer
from engine.run import Run, build_starting_deck, pick_enemy
from engine.scenes.battle import BattleScene
from engine.scenes.loading import LoadingScene
from engine.scenes.reward import RewardScene
from engine.scenes.rest import RestScene
from engine.scenes.result import ResultScene
from engine.scenes.scene import Scene
from engine.scenes.title import TitleScene

REPO_ROOT = Path(__file__).resolve().parent
MODS_DIR = REPO_ROOT / "mods"
RULES_PATH = MODS_DIR / "core" / "rules.py"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ASCII 卡牌遊戲")
    parser.add_argument("--terminal", action="store_true", help="使用終端機渲染器（預設使用 pygame 視窗）")
    parser.add_argument("--enemy", default=None, help="開發測試用：指定敵人完整 id，直接開始單場戰鬥")
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


# ---------------------------------------------------------------------------
# 正式流程：loading -> title -> run（battle / reward / rest）-> result
# ---------------------------------------------------------------------------


class GameController:
    """管理整個 scene 狀態機，一次只有一個 scene 在跑。"""

    def __init__(self, db, report: LoadReport) -> None:
        self.db = db
        self.report = report
        self.bridge: Bridge | None = None
        self.run: Run | None = None
        self.quit_requested = False
        self.scene: Scene = LoadingScene(report)

    def handle(self, actions) -> None:
        self.scene.handle(actions)
        self._advance_if_needed()

    def update(self, dt: float) -> None:
        self.scene.update(dt)

    def draw(self, grid: Grid) -> None:
        self.scene.draw(grid)

    # -- 狀態轉換 ---------------------------------------------------------

    def _advance_if_needed(self) -> None:
        scene = self.scene
        if isinstance(scene, LoadingScene) and scene.finished:
            self._to_title()
        elif isinstance(scene, TitleScene) and scene.finished:
            self._start_new_run()
        elif isinstance(scene, BattleScene) and scene.finished:
            self._after_battle(scene)
        elif isinstance(scene, RewardScene) and scene.finished:
            self._after_stage()
        elif isinstance(scene, RestScene) and scene.finished:
            self._after_stage()
        elif isinstance(scene, ResultScene):
            if scene.restart_requested:
                self._to_title()
            elif scene.quit_requested:
                self.quit_requested = True

    def _to_title(self) -> None:
        self.scene = TitleScene()

    def _start_new_run(self) -> None:
        self.bridge = Bridge(RULES_PATH)
        deck = build_starting_deck(self.db.cards)
        self.run = Run(stages=self.db.run_stages, deck=deck)
        self._enter_current_stage()

    def _after_battle(self, battle: BattleScene) -> None:
        if battle.fatal_error is not None:
            self.scene = ResultScene(victory=False, message="\n".join(battle.fatal_error.panel_lines()))
            return

        player_view = self.bridge.player_view(battle.player)
        self.run.record_hp(player_view["hp"], player_view["max_hp"])

        if battle.result == "lose":
            self.scene = ResultScene(victory=False)
            return

        reward_pool = [c for c in self.db.cards.values() if c.get("in_reward_pool")]
        if reward_pool:
            self.scene = RewardScene(self.run, reward_pool)
        else:
            self._after_stage()

    def _after_stage(self) -> None:
        self.run.advance()
        self._enter_current_stage()

    def _enter_current_stage(self) -> None:
        stage = self.run.current_stage
        if stage is None:
            self.scene = ResultScene(victory=True)
            return
        if stage["type"] == "battle":
            self._enter_battle(stage.get("tier"))
        else:  # "rest"
            self.scene = RestScene(self.run)

    def _enter_battle(self, tier: str | None) -> None:
        try:
            player = self.bridge.create_player(self.run.deck)
            if self.run.max_hp is None:
                self.run.record_hp(player["hp"], player["max_hp"])
            else:
                player["hp"] = self.run.hp
                player["max_hp"] = self.run.max_hp
            enemy_data = pick_enemy(self.db.enemies, tier=tier)
            enemy = self.bridge.create_enemy(enemy_data)
        except ModCallError as exc:
            self.scene = ResultScene(victory=False, message="\n".join(exc.panel_lines()))
            return
        except (KeyError, ValueError) as exc:
            self.scene = ResultScene(victory=False, message=str(exc))
            return
        self.scene = BattleScene(self.bridge, player, enemy, floor=self.run.floor)


def run_game(use_terminal: bool) -> int:
    db, report = load_mods(MODS_DIR)
    print(report.format_text())
    print()

    renderer = _create_renderer(use_terminal)
    if renderer is None:
        return 1

    controller = GameController(db, report)

    grid = Grid()
    controller.draw(grid)
    renderer.present(grid)

    last_time = time.perf_counter()
    while not controller.quit_requested:
        actions = renderer.poll_actions()
        if any(isinstance(a, Quit) for a in actions):
            break
        now = time.perf_counter()
        dt, last_time = now - last_time, now
        controller.handle(actions)
        controller.update(dt)
        grid = Grid()
        controller.draw(grid)
        renderer.present(grid)

    renderer.close()
    print("已離開遊戲。")
    return 0


# ---------------------------------------------------------------------------
# 開發測試用：--enemy 指定時跳過整個流程，直接打一場單場戰鬥
# ---------------------------------------------------------------------------


def run_dev_battle(use_terminal: bool, enemy_full_id: str) -> int:
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
        enemy_data = pick_enemy(db.enemies, full_id=enemy_full_id)
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
    if args.enemy:
        return run_dev_battle(args.terminal, args.enemy)
    return run_game(args.terminal)


if __name__ == "__main__":
    raise SystemExit(main())
