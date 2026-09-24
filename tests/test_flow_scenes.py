from engine import layout
from engine.actions import Back, Choose, ClickCard, Confirm, HoverSkip, PlayCard, Skip
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


# ---------------------------------------------------------------------------
# RewardScene：滑鼠兩段式點擊（選取狀態放在 scene，不在 renderer）
# ---------------------------------------------------------------------------


def test_reward_click_card_first_time_selects_without_choosing():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    scene.handle([ClickCard(0)])
    assert scene.selected_index == 0
    assert scene.finished is False
    assert len(run.deck) == 0


def test_reward_click_card_second_time_confirms_choice():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    chosen_card = scene.options[0]
    scene.handle([ClickCard(0)])
    scene.handle([ClickCard(0)])
    assert scene.finished is True
    assert scene.selected_index is None
    assert run.deck[-1]["id"] == chosen_card["id"]


def test_reward_click_different_card_switches_selection():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    scene.handle([ClickCard(0)])
    assert scene.selected_index == 0
    scene.handle([ClickCard(1)])
    assert scene.selected_index == 1
    assert scene.finished is False


def test_reward_click_blank_deselects():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    scene.handle([ClickCard(0)])
    scene.handle([ClickCard(None)])
    assert scene.selected_index is None
    assert scene.finished is False


def test_reward_esc_deselects_without_skipping_when_something_selected():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    scene.handle([ClickCard(0)])
    scene.handle([Back()])
    assert scene.selected_index is None
    assert scene.finished is False  # 有選取中的卡時，Esc 只取消選取，不會直接跳過
    assert scene.skipped is False


def test_reward_esc_skips_when_nothing_selected():
    """終端機版沒有滑鼠、selected_index 永遠是 None，Esc（對應 b 鍵）維持原本「跳過」的行為。"""
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    scene.handle([Back()])
    assert scene.finished is True
    assert scene.skipped is True


def test_reward_number_key_ignores_pending_mouse_selection():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    chosen_card = scene.options[2]
    scene.handle([ClickCard(0)])  # 滑鼠選取了第 0 張
    scene.handle([PlayCard(2)])  # 數字鍵 3：直接選第 2 張，不管滑鼠選取狀態
    assert scene.finished is True
    assert run.deck[-1]["id"] == chosen_card["id"]


# ---------------------------------------------------------------------------
# RewardScene：跳過按鈕
# ---------------------------------------------------------------------------


def test_reward_hover_skip_sets_flag():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    assert scene.skip_hovered is False
    scene.handle([HoverSkip(True)])
    assert scene.skip_hovered is True
    scene.handle([HoverSkip(False)])
    assert scene.skip_hovered is False


def test_reward_skip_action_always_skips_even_with_selection():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    scene.handle([ClickCard(0)])  # 先選取一張
    scene.handle([Skip()])  # 跳過按鈕：不管選取狀態，一律直接跳過
    assert scene.finished is True
    assert scene.skipped is True
    assert len(run.deck) == 0


def test_reward_draw_skip_button_exists_and_highlights_on_hover():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    grid = Grid()
    scene.draw(grid)
    assert grid.get(layout.REWARD_SKIP_BUTTON_X, layout.REWARD_SKIP_BUTTON_Y).char == "╔"
    assert grid.get(layout.REWARD_SKIP_BUTTON_X, layout.REWARD_SKIP_BUTTON_Y).fg == "frame"

    scene.handle([HoverSkip(True)])
    grid2 = Grid()
    scene.draw(grid2)
    assert grid2.get(layout.REWARD_SKIP_BUTTON_X, layout.REWARD_SKIP_BUTTON_Y).fg == "highlight"


# ---------------------------------------------------------------------------
# RewardScene：選取的卡片上移一格、提示列跟 supports_mouse 掛勾
# ---------------------------------------------------------------------------


def test_reward_draw_shifts_selected_card_up_by_one_row():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    scene.handle([ClickCard(0)])

    grid = Grid()
    scene.draw(grid)
    x = layout.reward_card_x(0)
    assert grid.get(x, layout.REWARD_ROW_TOP - 1).char == "╔"
    assert grid.get(x, layout.REWARD_ROW_TOP).char != "╔"


def test_reward_draw_unselected_card_stays_at_normal_row():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool())
    grid = Grid()
    scene.draw(grid)
    x = layout.reward_card_x(0)
    assert grid.get(x, layout.REWARD_ROW_TOP).char == "╔"


def test_reward_hint_hidden_when_supports_mouse():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool(), supports_mouse=True)
    grid = Grid()
    scene.draw(grid)
    assert plain_lines(grid)[layout.REWARD_HINT_ROW].strip() == ""


def test_reward_hint_shown_when_not_supports_mouse():
    run = Run(stages=[], deck=[])
    scene = RewardScene(run, _reward_pool(), supports_mouse=False)
    grid = Grid()
    scene.draw(grid)
    assert "跳過" in plain_lines(grid)[layout.REWARD_HINT_ROW]
