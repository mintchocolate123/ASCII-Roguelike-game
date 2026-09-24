"""驗收條件：python main.py --terminal 可以完整打完一場戰鬥，不會崩潰。"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_battle(enemy: str, keys: str, timeout: int = 15) -> subprocess.CompletedProcess:
    # 明確指定 COLUMNS/LINES：subprocess 的輸出被導向管線、不是真的終端機，
    # 但 shutil.get_terminal_size() 仍然會優先讀這兩個環境變數，測試環境可能剛好設成
    # 比較小的值，導致誤觸「視窗太小」的提示，所以在這裡固定成夠大的畫面。
    env = {**os.environ, "COLUMNS": "96", "LINES": "40"}
    return subprocess.run(
        [sys.executable, "main.py", "--terminal", "--enemy", enemy],
        cwd=REPO_ROOT,
        input=keys,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def test_full_battle_against_slime_completes_without_traceback():
    # 開場 Enter，接著重複「打第一張牌、結束回合」，次數足夠打完史萊姆（25 HP）
    keys = "\n" + "1\ne\n" * 20
    result = _run_battle("core:slime", keys)
    assert "Traceback (most recent call last)" not in result.stderr
    assert result.returncode == 0
    assert ("恭喜獲勝" in result.stdout) or ("你被擊敗了" in result.stdout)


def test_full_battle_against_boss_completes_without_traceback():
    # 守門巨像 HP 較高、行動循環較長，多打幾輪確保能分出勝負
    keys = "\n" + "1\ne\n" * 40
    result = _run_battle("core:gate_colossus", keys)
    assert "Traceback (most recent call last)" not in result.stderr
    assert result.returncode == 0
    assert ("恭喜獲勝" in result.stdout) or ("你被擊敗了" in result.stdout)


def test_unknown_enemy_full_id_fails_gracefully():
    result = _run_battle("core:does_not_exist", "\n", timeout=10)
    assert "Traceback (most recent call last)" not in result.stderr
    assert result.returncode != 0
    assert "無法開始戰鬥" in result.stdout


def test_reload_mid_battle_via_dev_flow_does_not_crash():
    """驗收條件：F5（終端機版對應 r）重新載入所有 mod 資料與 rules.py，重開目前這場戰鬥，不能讓遊戲崩潰。

    r 放在任何出牌之前：cards.json 目前可能正被拿來手動測試（傷害值可能被改得很高），
    如果先出牌再 r，戰鬥可能在按到 r 之前就已經結束，測試會不穩定。
    """
    keys = "\nr\n" + "1\ne\n" * 20
    result = _run_battle("core:slime", keys)
    assert "Traceback (most recent call last)" not in result.stderr
    assert result.returncode == 0
    assert "已重新載入" in result.stdout
    assert ("恭喜獲勝" in result.stdout) or ("你被擊敗了" in result.stdout)


def test_default_flow_no_enemy_flag_reaches_first_battle_via_loading_and_title():
    """驗收條件：main.py 改成從 loading 進入。不帶 --enemy 時走 loading -> title -> 第一關戰鬥。"""
    env = {**os.environ, "COLUMNS": "96", "LINES": "40"}
    result = subprocess.run(
        [sys.executable, "main.py", "--terminal"],
        cwd=REPO_ROOT,
        input="\n\n",  # Enter 通過 loading，再 Enter 通過 title
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    assert "Traceback (most recent call last)" not in result.stderr
    assert result.returncode == 0
    assert "已離開遊戲" in result.stdout
    assert "ASCII 卡牌遊戲" in result.stdout  # title 畫面
    assert "[ 冒險者 ]" in result.stdout  # 已經進到戰鬥畫面，不是卡在 loading/title
