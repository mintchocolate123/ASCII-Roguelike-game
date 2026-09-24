from engine.actions import Back, Choose, Confirm, PlayCard
from engine.grid import Grid, plain_lines
from engine.mod.report import LoadReport
from engine.run import Run
from engine.scenes.loading import LoadingScene
from engine.scenes.reward import RewardScene
from engine.scenes.rest import RestScene
from engine.scenes.result import ResultScene
from engine.scenes.title import TitleScene

# ---------------------------------------------------------------------------
# LoadingScene
# ---------------------------------------------------------------------------


def test_loading_scene_confirm_finishes_when_no_fatal():
    report = LoadReport()
    report.warning("有點問題但不嚴重")
    scene = LoadingScene(report)
    assert scene.finished is False
    scene.handle([Confirm()])
    assert scene.finished is True


def test_loading_scene_stuck_forever_when_fatal():
    report = LoadReport()
    report.fatal("core 沒有成功載入")
    scene = LoadingScene(report)
    scene.handle([Confirm()])
    assert scene.finished is False
    scene.handle([Confirm()])
    scene.handle([Confirm()])
    assert scene.finished is False


def test_loading_scene_draws_report_text():
    report = LoadReport()
    report.warning("這是一則警告文字")
    scene = LoadingScene(report)
    grid = Grid()
    scene.draw(grid)
    lines = plain_lines(grid)
    assert any("這是一則警告文字" in line for line in lines)


def test_loading_scene_draws_fatal_message():
    report = LoadReport()
    report.fatal("core 沒有成功載入")
    scene = LoadingScene(report)
    grid = Grid()
    scene.draw(grid)
    lines = plain_lines(grid)
    assert any("無法開始遊戲" in line for line in lines)


# ---------------------------------------------------------------------------
# TitleScene
# ---------------------------------------------------------------------------


def test_title_scene_confirm_finishes():
    scene = TitleScene()
    assert scene.finished is False
    scene.handle([Confirm()])
    assert scene.finished is True


def test_title_scene_draws_title_text():
    scene = TitleScene()
    grid = Grid()
    scene.draw(grid)
    lines = plain_lines(grid)
    assert any("ASCII 卡牌遊戲" in line for line in lines)


# ---------------------------------------------------------------------------
# RestScene
# ---------------------------------------------------------------------------


def test_rest_scene_heals_30_percent_on_entry():
    run = Run(stages=[], deck=[])
    run.record_hp(20, 50)
    scene = RestScene(run)
    assert scene.healed_amount == 15
    assert run.hp == 35


def test_rest_scene_confirm_finishes():
    run = Run(stages=[], deck=[])
    run.record_hp(20, 50)
    scene = RestScene(run)
    scene.handle([Confirm()])
    assert scene.finished is True


def test_rest_scene_draws_healed_amount():
    run = Run(stages=[], deck=[])
    run.record_hp(20, 50)
    scene = RestScene(run)
    grid = Grid()
    scene.draw(grid)
    lines = plain_lines(grid)
    assert any("15" in line for line in lines)


# ---------------------------------------------------------------------------
# ResultScene
# ---------------------------------------------------------------------------


def test_result_scene_victory_confirm_requests_restart():
    scene = ResultScene(victory=True)
    scene.handle([Confirm()])
    assert scene.restart_requested is True
    assert scene.quit_requested is False


def test_result_scene_back_requests_quit():
    scene = ResultScene(victory=False)
    scene.handle([Back()])
    assert scene.quit_requested is True
    assert scene.restart_requested is False


def test_result_scene_draws_victory_and_defeat_text():
    win_grid = Grid()
    ResultScene(victory=True).draw(win_grid)
    assert any("通關" in line for line in plain_lines(win_grid))

    lose_grid = Grid()
    ResultScene(victory=False).draw(lose_grid)
    assert any("戰敗" in line for line in plain_lines(lose_grid))


def test_result_scene_draws_custom_message():
    scene = ResultScene(victory=False, message="自訂的錯誤說明")
    grid = Grid()
    scene.draw(grid)
    assert any("自訂的錯誤說明" in line for line in plain_lines(grid))


# ---------------------------------------------------------------------------
# RewardScene
# ---------------------------------------------------------------------------


def _reward_pool():
    return [
        {"id": "a", "name": "卡片A", "cost": 1, "type": "attack", "description": "描述 A。"},
        {"id": "b", "name": "卡片B", "cost": 1, "type": "skill", "description": "描述 B。"},
        {"id": "c", "name": "卡片C", "cost": 1, "type": "power", "description": "描述 C。"},
        {"id": "d", "name": "卡片D", "cost": 1, "type": "attack", "description": "描述 D。"},
    ]


def test_reward_scene_samples_at_most_three_cards():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    assert len(scene.options) == 3


def test_reward_scene_fewer_than_three_available():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool()[:2])
    assert len(scene.options) == 2


def test_reward_scene_choosing_card_adds_to_deck_and_finishes():
    run = Run(stages=[], deck=[{"id": "strike"}])
    scene = RewardScene(run, _reward_pool())
    chosen_card = scene.options[1]
    scene.handle([PlayCard(1)])
    assert scene.finished is True
    assert scene.skipped is False
    assert run.deck[-1]["id"] == chosen_card["id"]
    assert len(run.deck) == 2


def test_reward_scene_accepts_choose_action_too():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    scene.handle([Choose(0)])
    assert scene.finished is True
    assert len(run.deck) == 1


def test_reward_scene_out_of_range_index_is_ignored():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    scene.handle([PlayCard(99)])
    assert scene.finished is False
    assert len(run.deck) == 0


def test_reward_scene_back_skips_without_adding_card():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    scene.handle([Back()])
    assert scene.finished is True
    assert scene.skipped is True
    assert len(run.deck) == 0


def test_reward_scene_draws_card_names():
    run = Run(stages=[], deck=[])
    pool = _reward_pool()[:1]
    scene = RewardScene(run, pool)
    grid = Grid()
    scene.draw(grid)
    lines = plain_lines(grid)
    assert any(pool[0]["name"] in line for line in lines)
