"""第一階段 demo：用終端機渲染器畫一個中英文混排的框線，確認對齊。"""
from engine.draw import draw_box, draw_hp_bar, draw_text
from engine.grid import Grid
from engine.render.terminal_renderer import TerminalRenderer


def main() -> None:
    grid = Grid()

    draw_box(grid, 4, 2, 40, 10, fg="cyan", title="狀態視窗 Status")
    draw_text(grid, 6, 4, "名稱 Name: 哥布林 Goblin", fg="white")
    draw_text(grid, 6, 5, "生命 HP:", fg="white")
    draw_hp_bar(grid, 15, 5, 20, 7, 10, fg="green")
    draw_text(grid, 6, 6, "護盾 Block: 3", fg="cyan")
    draw_text(grid, 6, 7, "意圖 Intent: 攻擊 Attack 8", fg="red")

    draw_box(grid, 4, 13, 40, 6, fg="yellow", title="卡牌 Card")
    draw_text(grid, 6, 15, "斬擊 Strike  cost:1", fg="white")
    draw_text(grid, 6, 16, "造成 6 點傷害 Deal 6 dmg", fg="white")

    renderer = TerminalRenderer()
    renderer.present(grid)


if __name__ == "__main__":
    main()
