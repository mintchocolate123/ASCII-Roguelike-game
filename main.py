"""啟動點：解析參數（--terminal）、載入 mod、進入主迴圈。預設使用 pygame 視窗。

一般玩法從 loading 進場：loading -> title -> (battle -> reward 或 rest -> 下一關...) -> result，
result 可以重新開始（回到 title）或離開。

--enemy 保留給開發測試用：指定敵人完整 id 時跳過整個流程，直接打一場單場戰鬥。

F5（Reload）在戰鬥畫面隨時可以按：重新載入所有 mod 資料與 rules.py，重開目前這場戰鬥，
不保留舊的戰鬥狀態。重新載入失敗時只顯示錯誤，繼續用重新載入前那個還能動的版本玩下去。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from engine.actions import Quit
from engine.bridge import Bridge, ModCallError, RulesReloadError
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
# 熱重載共用邏輯：mod 資料 + rules.py 都重新載入成功才算數，失敗一律保留舊版本
# ---------------------------------------------------------------------------


class ReloadFailed(Exception):
    """F5 熱重載失敗時使用；呼叫端應該保留重新載入前的 db/bridge/scene 繼續遊戲。"""


def _reload_mods_and_rules(bridge: Bridge):
    """回傳新的 (db, report)。任何一步失敗都會拋出 ReloadFailed，bridge.rules 保持原本還能用的版本。"""
    new_db, new_report = load_mods(MODS_DIR)
    if new_report.has_fatal:
        raise ReloadFailed("mod 資料重新載入後出現致命錯誤，已繼續使用原本的版本：\n" + new_report.format_text())
    try:
        bridge.reload()
    except RulesReloadError as exc:
        raise ReloadFailed(str(exc)) from exc
    return new_db, new_report


def _build_battle(
    bridge: Bridge,
    db,
    deck: list[dict],
    *,
    tier: str | None = None,
    enemy_full_id: str | None = None,
    hp: int | None = None,
    max_hp: int | None = None,
    floor: int = 1,
    supports_animation: bool = True,
    supports_mouse: bool = True,
) -> BattleScene:
    """建立一場新的戰鬥；初次進場或 F5 重開都走這裡，確保兩者邏輯一致。"""
    player = bridge.create_player(deck)
    if hp is not None:
        player["hp"] = hp
        player["max_hp"] = max_hp
    enemy_data = pick_enemy(db.enemies, full_id=enemy_full_id, tier=tier)
    enemy = bridge.create_enemy(enemy_data)
    return BattleScene(
        bridge, player, enemy, floor=floor, supports_animation=supports_animation, supports_mouse=supports_mouse
    )


# ---------------------------------------------------------------------------
# 正式流程：loading -> title -> run（battle / reward / rest）-> result
# ---------------------------------------------------------------------------


class GameController:
    """管理整個 scene 狀態機，一次只有一個 scene 在跑。"""

    def __init__(
        self, db, report: LoadReport, *, supports_animation: bool = True, supports_mouse: bool = True
    ) -> None:
        self.db = db
        self.report = report
        self.supports_animation = supports_animation
        self.supports_mouse = supports_mouse
        self.bridge: Bridge | None = None
        self.run: Run | None = None
        self.quit_requested = False
        self.scene: Scene = LoadingScene(report)

    def handle(self, actions) -> None:
        self.scene.handle(actions)
        if isinstance(self.scene, BattleScene) and self.scene.reload_requested:
            self._handle_reload()
            return
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
            self.scene = _build_battle(
                self.bridge,
                self.db,
                self.run.deck,
                tier=tier,
                hp=self.run.hp,
                max_hp=self.run.max_hp,
                floor=self.run.floor,
                supports_animation=self.supports_animation,
                supports_mouse=self.supports_mouse,
            )
        except ModCallError as exc:
            self.scene = ResultScene(victory=False, message="\n".join(exc.panel_lines()))
            return
        except (KeyError, ValueError) as exc:
            self.scene = ResultScene(victory=False, message=str(exc))
            return
        if self.run.max_hp is None:
            player_view = self.bridge.player_view(self.scene.player)
            self.run.record_hp(player_view["hp"], player_view["max_hp"])

    # -- F5 熱重載 ---------------------------------------------------------

    def _handle_reload(self) -> None:
        scene = self.scene
        scene.reload_requested = False
        tier = self.run.current_stage.get("tier") if self.run and self.run.current_stage else None

        try:
            new_db, new_report = _reload_mods_and_rules(self.bridge)
        except ReloadFailed as exc:
            scene.battle_log.append(f"重新載入失敗：{exc}")
            return

        self.db = new_db
        self.report = new_report
        self.run.refresh_deck(self.db.cards)  # 牌組裡每張卡都換成重新載入後的最新版本
        try:
            new_scene = _build_battle(
                self.bridge,
                self.db,
                self.run.deck,
                tier=tier,
                hp=self.run.hp,
                max_hp=self.run.max_hp,
                floor=self.run.floor,
                supports_animation=self.supports_animation,
                supports_mouse=self.supports_mouse,
            )
        except ModCallError as exc:
            scene.battle_log.append("重新載入後無法重開戰鬥：" + "\n".join(exc.panel_lines()))
            return
        except (KeyError, ValueError) as exc:
            scene.battle_log.append(f"重新載入後無法重開戰鬥：{exc}")
            return

        new_scene.battle_log.append("已重新載入 mod 資料與 rules.py，戰鬥重新開始。")
        self.scene = new_scene


def run_game(use_terminal: bool) -> int:
    db, report = load_mods(MODS_DIR)
    print(report.format_text())
    print()

    renderer = _create_renderer(use_terminal)
    if renderer is None:
        return 1

    controller = GameController(
        db, report, supports_animation=renderer.supports_animation(), supports_mouse=renderer.supports_mouse()
    )

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
        scene = _build_battle(
            bridge,
            db,
            deck,
            enemy_full_id=enemy_full_id,
            supports_animation=renderer.supports_animation(),
            supports_mouse=renderer.supports_mouse(),
        )
    except ModCallError as exc:
        print("無法開始戰鬥：")
        print("\n".join(exc.panel_lines()))
        renderer.close()
        return 1
    except (KeyError, ValueError) as exc:
        print(f"無法開始戰鬥：{exc}")
        renderer.close()
        return 1

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

        if scene.reload_requested:
            scene.reload_requested = False
            try:
                db, report = _reload_mods_and_rules(bridge)
            except ReloadFailed as exc:
                scene.battle_log.append(f"重新載入失敗：{exc}")
            else:
                try:
                    new_deck = build_starting_deck(db.cards)
                    scene = _build_battle(
                        bridge, db, new_deck, enemy_full_id=enemy_full_id,
                        supports_animation=renderer.supports_animation(),
                        supports_mouse=renderer.supports_mouse(),
                    )
                    scene.battle_log.append("已重新載入 mod 資料與 rules.py，戰鬥重新開始。")
                except ModCallError as exc:
                    scene.battle_log.append("重新載入後無法重開戰鬥：" + "\n".join(exc.panel_lines()))
                except (KeyError, ValueError) as exc:
                    scene.battle_log.append(f"重新載入後無法重開戰鬥：{exc}")

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
