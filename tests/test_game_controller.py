from pathlib import Path

from engine.actions import Back, Confirm, EndTurn, PlayCard
from engine.mod.loader import load_mods
from engine.mod.report import LoadReport
from engine.scenes.battle import BattleScene
from engine.scenes.loading import LoadingScene
from engine.scenes.reward import RewardScene
from engine.scenes.rest import RestScene
from engine.scenes.result import ResultScene
from engine.scenes.title import TitleScene
from main import GameController

MODS_DIR = Path(__file__).resolve().parent.parent / "mods"


def _controller(stages=None):
    """固定只留 tier=normal 裡血量最低的敵人，並在下面用「盡量打完手牌」的策略戰鬥，
    這樣測試 controller 的狀態轉換邏輯時不會被戰鬥平衡或抽牌順序的隨機性搞到不穩定。
    """
    db, report = load_mods(MODS_DIR)
    normal_enemies = {k: v for k, v in db.enemies.items() if v["tier"] == "normal"}
    weakest_id = min(normal_enemies, key=lambda k: normal_enemies[k]["hp"])
    db.enemies = {
        k: v for k, v in db.enemies.items() if v["tier"] != "normal" or k == weakest_id
    }
    if stages is not None:
        db.run_stages = stages
    controller = GameController(db, report)
    controller.handle([Confirm()])  # loading -> title
    controller.handle([Confirm()])  # title -> 第一關
    return controller


def _play_through_battle(controller, max_iterations=100):
    """每回合把打得動的牌都打完再結束回合，直到離開 battle scene（贏、輸或出錯都算離開）。"""
    for _ in range(max_iterations):
        if not isinstance(controller.scene, BattleScene):
            return
        for _ in range(10):  # 一手最多打幾張牌的保險上限
            scene = controller.scene
            if not isinstance(scene, BattleScene) or scene.state != "player_turn":
                break
            hand = controller.bridge.player_view(scene.player).get("hand", [])
            if not hand or not controller.bridge.can_play(scene.player, 0):
                break
            controller.handle([PlayCard(0)])
        if not isinstance(controller.scene, BattleScene):
            return
        controller.handle([EndTurn()])
    raise AssertionError("戰鬥沒有在預期次數內結束")


# ---------------------------------------------------------------------------
# loading -> title -> 第一關
# ---------------------------------------------------------------------------


def test_loading_to_title_to_first_stage():
    db, report = load_mods(MODS_DIR)
    controller = GameController(db, report)
    assert isinstance(controller.scene, LoadingScene)

    controller.handle([Confirm()])
    assert isinstance(controller.scene, TitleScene)

    controller.handle([Confirm()])
    assert isinstance(controller.scene, BattleScene)
    assert controller.run is not None
    assert controller.run.stage_index == 0
    assert controller.run.hp == controller.run.max_hp  # 第一關滿血開始


def test_loading_stuck_when_fatal_never_reaches_title():
    report = LoadReport()
    report.fatal("core 沒有成功載入")
    controller = GameController(db=None, report=report)
    controller.handle([Confirm()])
    assert isinstance(controller.scene, LoadingScene)
    assert controller.run is None


# ---------------------------------------------------------------------------
# 打贏一場戰鬥 -> 進入 reward -> 選卡或跳過 -> 進下一關
# ---------------------------------------------------------------------------


def test_win_battle_goes_to_reward_then_next_battle_on_skip():
    stages = [{"type": "battle", "tier": "normal"}, {"type": "battle", "tier": "normal"}]
    controller = _controller(stages)
    deck_size_before = len(controller.run.deck)

    _play_through_battle(controller)
    assert isinstance(controller.scene, RewardScene)

    controller.handle([Back()])  # 跳過獎勵
    assert isinstance(controller.scene, BattleScene)
    assert controller.run.stage_index == 1
    assert len(controller.run.deck) == deck_size_before  # 跳過不會加卡


def test_choosing_reward_card_adds_to_deck_and_persists_to_next_battle():
    stages = [{"type": "battle", "tier": "normal"}, {"type": "battle", "tier": "normal"}]
    controller = _controller(stages)
    deck_size_before = len(controller.run.deck)

    _play_through_battle(controller)
    assert isinstance(controller.scene, RewardScene)

    controller.handle([PlayCard(0)])  # 選第一張獎勵卡
    assert isinstance(controller.scene, BattleScene)
    assert len(controller.run.deck) == deck_size_before + 1


def test_hp_carries_over_between_battles():
    stages = [{"type": "battle", "tier": "normal"}, {"type": "battle", "tier": "normal"}]
    controller = _controller(stages)

    _play_through_battle(controller)
    hp_after_first_battle = controller.run.hp
    controller.handle([Back()])

    assert isinstance(controller.scene, BattleScene)
    second_battle_player_hp = controller.bridge.player_view(controller.scene.player)["hp"]
    assert second_battle_player_hp == hp_after_first_battle


# ---------------------------------------------------------------------------
# rest 關卡：回復 30% 血量
# ---------------------------------------------------------------------------


def test_rest_stage_heals_and_continues_to_next_battle():
    stages = [{"type": "battle", "tier": "normal"}, {"type": "rest"}, {"type": "battle", "tier": "normal"}]
    controller = _controller(stages)

    _play_through_battle(controller)
    assert isinstance(controller.scene, RewardScene)
    hp_before_rest = controller.run.hp
    controller.handle([Back()])

    assert isinstance(controller.scene, RestScene)
    expected_heal = min(controller.run.max_hp - hp_before_rest, int(controller.run.max_hp * 0.3))
    assert controller.scene.healed_amount == expected_heal
    assert controller.run.hp == hp_before_rest + expected_heal

    controller.handle([Confirm()])
    assert isinstance(controller.scene, BattleScene)
    assert controller.run.stage_index == 2


# ---------------------------------------------------------------------------
# 打完所有關卡 -> 通關；戰敗 -> 戰敗畫面；兩者都能重新開始
# ---------------------------------------------------------------------------


def test_completing_all_stages_reaches_victory_result():
    stages = [{"type": "battle", "tier": "normal"}]
    controller = _controller(stages)

    _play_through_battle(controller)
    assert isinstance(controller.scene, RewardScene)
    controller.handle([Back()])

    assert isinstance(controller.scene, ResultScene)
    assert controller.scene.victory is True


def test_result_scene_confirm_restarts_to_title():
    stages = [{"type": "battle", "tier": "normal"}]
    controller = _controller(stages)
    _play_through_battle(controller)
    controller.handle([Back()])  # 跳過唯一的獎勵 -> 通關
    assert isinstance(controller.scene, ResultScene)

    controller.handle([Confirm()])
    assert isinstance(controller.scene, TitleScene)


def test_result_scene_back_sets_quit_requested():
    stages = [{"type": "battle", "tier": "normal"}]
    controller = _controller(stages)
    _play_through_battle(controller)
    controller.handle([Back()])
    assert isinstance(controller.scene, ResultScene)

    controller.handle([Back()])
    assert controller.quit_requested is True
