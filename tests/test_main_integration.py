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
