"""pygame 版渲染器：用附帶的 Sarasa Fixed 字型畫出跟終端機版一樣的內容。"""
from __future__ import annotations

from pathlib import Path

import pygame

from .. import layout, palette
from ..actions import (
    Action,
    Back,
    ClickButton,
    ClickCard,
    Confirm,
    EndTurn,
    HoverButton,
    HoverEndTurn,
    HoverSkip,
    Inspect,
    PlayCard,
    Quit,
    Reload,
    Skip,
)
from ..grid import CELL_PIXEL_HEIGHT, CELL_PIXEL_WIDTH, HEIGHT as GRID_HEIGHT, WIDTH as GRID_WIDTH, Grid
from .base import Renderer

DEFAULT_FONT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "assets" / "fonts" / "SarasaFixedTC-Regular.ttf"
)

WINDOW_WIDTH = GRID_WIDTH * CELL_PIXEL_WIDTH
WINDOW_HEIGHT = GRID_HEIGHT * CELL_PIXEL_HEIGHT

FPS = 60

_KEY_TO_ACTION = {
    pygame.K_e: EndTurn,
    pygame.K_RETURN: Confirm,
    pygame.K_KP_ENTER: Confirm,
    pygame.K_F5: Reload,
    pygame.K_ESCAPE: Back,
}

# title／loading／rest／result 共用的具名按鈕，(x, y, w, h)。座標可能跟 battle／reward 的
# 區域重疊也沒關係：這些畫面不會同時顯示，收到的 scene 只認自己的名稱，其他一律忽略。
_MENU_BUTTON_RECTS: dict[str, tuple[int, int, int, int]] = {
    "title_start": (
        layout.TITLE_START_BUTTON_X,
        layout.TITLE_START_BUTTON_Y,
        layout.MENU_BUTTON_WIDTH,
        layout.MENU_BUTTON_HEIGHT,
    ),
    "loading_continue": (
        layout.LOADING_CONTINUE_BUTTON_X,
        layout.LOADING_CONTINUE_BUTTON_Y,
        layout.MENU_BUTTON_WIDTH,
        layout.MENU_BUTTON_HEIGHT,
    ),
    "rest_continue": (
        layout.REST_CONTINUE_BUTTON_X,
        layout.REST_CONTINUE_BUTTON_Y,
        layout.MENU_BUTTON_WIDTH,
        layout.MENU_BUTTON_HEIGHT,
    ),
    "result_restart": (
        layout.RESULT_RESTART_BUTTON_X,
        layout.RESULT_BUTTON_ROW,
        layout.MENU_BUTTON_WIDTH,
        layout.MENU_BUTTON_HEIGHT,
    ),
    "result_quit": (
        layout.RESULT_QUIT_BUTTON_X,
        layout.RESULT_BUTTON_ROW,
        layout.MENU_BUTTON_WIDTH,
        layout.MENU_BUTTON_HEIGHT,
    ),
}


class FontLoadError(Exception):
    """字型檔遺失或載入失敗時使用，讓呼叫端可以顯示清楚的中文說明，不要讓程式直接崩潰。"""


def _fit_font(path: str, cell_width: int, cell_height: int) -> pygame.font.Font:
    """挑一個字級，讓半形字元剛好佔一格、全形字元剛好佔兩格。"""
    size = cell_height
    while size > 4:
        font = pygame.font.Font(path, size)
        ascii_w, ascii_h = font.size("A")
        cjk_w, cjk_h = font.size("字")
        if ascii_w <= cell_width and cjk_w <= cell_width * 2 and max(ascii_h, cjk_h) <= cell_height:
            return font
        size -= 1
    return pygame.font.Font(path, 4)


class PygameRenderer(Renderer):
    def __init__(self, font_path: str | Path = DEFAULT_FONT_PATH) -> None:
        font_path = Path(font_path)
        if not font_path.exists():
            raise FontLoadError(
                f"找不到字型檔：{font_path}\n"
                "請確認 assets/fonts/SarasaFixedTC-Regular.ttf 是否存在，"
                "或使用 --terminal 改用終端機版。"
            )

        pygame.display.init()
        pygame.font.init()
        try:
            self._font = _fit_font(str(font_path), CELL_PIXEL_WIDTH, CELL_PIXEL_HEIGHT)
        except pygame.error as exc:
            raise FontLoadError(f"字型檔載入失敗：{font_path}（{exc}）") from exc

        self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("ASCII 卡牌遊戲")
        self._clock = pygame.time.Clock()
        self._glyph_cache: dict[tuple[str, str, str | None], pygame.Surface] = {}
        self._hover_index: int | None = None
        self._hover_end_turn = False
        self._hover_skip = False
        self._hovered_menu_buttons: frozenset[str] = frozenset()

    # ------------------------------------------------------------------
    # Renderer 介面
    # ------------------------------------------------------------------

    def present(self, grid: Grid) -> None:
        if not grid.dirty:
            return
        self._screen.fill(palette.resolve("bg"))
        for y in range(grid.height):
            for x in range(grid.width):
                cell = grid.get(x, y)
                if cell.wide_tail:
                    continue
                surface = self._glyph_surface(cell.char, cell.fg, cell.bg)
                self._screen.blit(surface, (x * CELL_PIXEL_WIDTH, y * CELL_PIXEL_HEIGHT))
        pygame.display.flip()
        grid.dirty = False

    def poll_actions(self) -> list[Action]:
        self._clock.tick(FPS)
        actions: list[Action] = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                actions.append(Quit())
            elif event.type == pygame.KEYDOWN:
                action = self._action_for_keydown(event)
                if action is not None:
                    actions.append(action)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._is_over_end_turn_button(event.pos):
                    actions.append(EndTurn())
                elif self._is_over_skip_button(event.pos):
                    actions.append(Skip())
                else:
                    for name in self._menu_buttons_at(event.pos):
                        actions.append(ClickButton(name))
                    actions.append(ClickCard(self._click_card_index_at(event.pos)))
            elif event.type == pygame.MOUSEMOTION:
                index = self._card_index_at(event.pos)
                if index != self._hover_index:
                    self._hover_index = index
                    actions.append(Inspect(index))
                over_end_turn = self._is_over_end_turn_button(event.pos)
                if over_end_turn != self._hover_end_turn:
                    self._hover_end_turn = over_end_turn
                    actions.append(HoverEndTurn(over_end_turn))
                over_skip = self._is_over_skip_button(event.pos)
                if over_skip != self._hover_skip:
                    self._hover_skip = over_skip
                    actions.append(HoverSkip(over_skip))
                hovered_menu = self._menu_buttons_at(event.pos)
                if hovered_menu != self._hovered_menu_buttons:
                    for name in self._hovered_menu_buttons - hovered_menu:
                        actions.append(HoverButton(name, False))
                    for name in hovered_menu - self._hovered_menu_buttons:
                        actions.append(HoverButton(name, True))
                    self._hovered_menu_buttons = hovered_menu
        return actions

    def supports_animation(self) -> bool:
        return True

    def supports_mouse(self) -> bool:
        return True

    def close(self) -> None:
        pygame.display.quit()
        pygame.font.quit()

    # ------------------------------------------------------------------
    # 內部細節
    # ------------------------------------------------------------------

    def _glyph_surface(self, char: str, fg: str, bg: str | None) -> pygame.Surface:
        key = (char, fg, bg)
        surface = self._glyph_cache.get(key)
        if surface is None:
            fg_rgb = palette.resolve(fg)
            bg_rgb = palette.resolve(bg) if bg else palette.resolve("bg")
            surface = self._font.render(char if char else " ", True, fg_rgb, bg_rgb)
            self._glyph_cache[key] = surface
        return surface

    @staticmethod
    def _action_for_keydown(event: pygame.event.Event) -> Action | None:
        if pygame.K_1 <= event.key <= pygame.K_7:
            return PlayCard(event.key - pygame.K_1)
        action_cls = _KEY_TO_ACTION.get(event.key)
        return action_cls() if action_cls is not None else None

    def _click_card_index_at(self, pos: tuple[int, int]) -> int | None:
        """手牌跟獎勵卡共用 ClickCard：兩者的列範圍不重疊，最多只有一邊會命中。"""
        index = self._card_index_at(pos)
        if index is not None:
            return index
        return self._reward_card_index_at(pos)

    @staticmethod
    def _card_index_at(pos: tuple[int, int]) -> int | None:
        px, py = pos
        col = px // CELL_PIXEL_WIDTH
        row = py // CELL_PIXEL_HEIGHT
        if not (layout.HAND_ROW_TOP <= row <= layout.HAND_ROW_BOTTOM):
            return None
        for i in range(layout.CARD_MAX_COUNT):
            start = layout.card_slot_x(i)
            if start <= col < start + layout.CARD_WIDTH:
                return i
        return None

    @staticmethod
    def _reward_card_index_at(pos: tuple[int, int]) -> int | None:
        px, py = pos
        col = px // CELL_PIXEL_WIDTH
        row = py // CELL_PIXEL_HEIGHT
        if not (layout.REWARD_ROW_TOP <= row < layout.REWARD_ROW_TOP + layout.CARD_HEIGHT):
            return None
        for i in range(layout.REWARD_CARD_COUNT):
            start = layout.reward_card_x(i)
            if start <= col < start + layout.CARD_WIDTH:
                return i
        return None

    @staticmethod
    def _menu_buttons_at(pos: tuple[int, int]) -> frozenset[str]:
        """回傳目前座標命中的具名按鈕集合；正常只會有 0 或 1 個，title／loading／rest 的
        按鈕座標刻意相同時會有多個，各自的 scene 只認自己的名稱。"""
        px, py = pos
        col = px // CELL_PIXEL_WIDTH
        row = py // CELL_PIXEL_HEIGHT
        return frozenset(
            name
            for name, (bx, by, bw, bh) in _MENU_BUTTON_RECTS.items()
            if bx <= col < bx + bw and by <= row < by + bh
        )

    @staticmethod
    def _is_over_end_turn_button(pos: tuple[int, int]) -> bool:
        px, py = pos
        col = px // CELL_PIXEL_WIDTH
        row = py // CELL_PIXEL_HEIGHT
        return (
            layout.END_TURN_BUTTON_X <= col < layout.END_TURN_BUTTON_X + layout.END_TURN_BUTTON_WIDTH
            and layout.END_TURN_BUTTON_Y <= row < layout.END_TURN_BUTTON_Y + layout.END_TURN_BUTTON_HEIGHT
        )

    @staticmethod
    def _is_over_skip_button(pos: tuple[int, int]) -> bool:
        px, py = pos
        col = px // CELL_PIXEL_WIDTH
        row = py // CELL_PIXEL_HEIGHT
        return (
            layout.REWARD_SKIP_BUTTON_X <= col < layout.REWARD_SKIP_BUTTON_X + layout.REWARD_SKIP_BUTTON_WIDTH
            and layout.REWARD_SKIP_BUTTON_Y <= row < layout.REWARD_SKIP_BUTTON_Y + layout.REWARD_SKIP_BUTTON_HEIGHT
        )
