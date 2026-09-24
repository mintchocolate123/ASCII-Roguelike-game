"""畫面區塊座標常數。列（row）與欄（col）皆從 0 開始，scene 不得直接寫死座標數字。"""

SCREEN_WIDTH = 96
SCREEN_HEIGHT = 32

# --- 主框（列 0 到 20） ---
FRAME_LEFT = 0
FRAME_RIGHT = 95
FRAME_TOP = 0
FRAME_BOTTOM = 20
FRAME_WIDTH = FRAME_RIGHT - FRAME_LEFT + 1
FRAME_HEIGHT = FRAME_BOTTOM - FRAME_TOP + 1

PANEL_DIVIDER_COL = 63
LEFT_CONTENT_START = 1
LEFT_CONTENT_END = 62
RIGHT_CONTENT_START = 64
RIGHT_CONTENT_END = 94

HEADER_ROW = 1  # 樓層／回合數（左）、面板標題（右）
LEFT_DIVIDER_ROW = 2  # 只在左面板畫分隔線

ENEMY_ART_TOP = 3
ENEMY_ART_BOTTOM = 12
ENEMY_ART_WIDTH = 24
ENEMY_ART_HEIGHT = ENEMY_ART_BOTTOM - ENEMY_ART_TOP + 1  # 10

ENEMY_BANNER_ROW = 13  # ════[ 名稱 ]════
ENEMY_HP_ROW = 14
ENEMY_INTENT_ROW = 15
ENEMY_STATUS_ROW = 16  # 第一階段留空

FULL_DIVIDER_ROW = 17  # 欄 0 ╠、欄 63 ╩、欄 95 ╣

PLAYER_STATUS_ROW = 18
PLAYER_STATUS2_ROW = 19  # 第一階段留空

# --- 右面板（列 3 到 16，寬 31） ---
RIGHT_PANEL_TOP = ENEMY_ART_TOP
RIGHT_PANEL_BOTTOM = ENEMY_STATUS_ROW
RIGHT_PANEL_WIDTH = RIGHT_CONTENT_END - RIGHT_CONTENT_START + 1 + 2  # 含左右邊框共 31
RIGHT_PANEL_CONTENT_WIDTH = 29

# --- 手牌（列 21 到 30） ---
HAND_ROW_TOP = 21
HAND_ROW_BOTTOM = 30
CARD_WIDTH = 12
CARD_HEIGHT = 10
CARD_MAX_COUNT = 7
CARD_SLOT_START_COL = 1
CARD_SLOT_STRIDE = 12  # 等於 CARD_WIDTH，卡片緊鄰排列、彼此不留間距，
# 才能在欄 0 到 95 內同時放下 7 張卡與結束回合按鈕。

# 選取中的卡牌會整張上移一格，用來當作「已選取、再點一次就出牌」的提示。
SELECTED_CARD_ROW_OFFSET = -1


def card_slot_x(index: int) -> int:
    """第 index 張手牌（從 0 開始）左上角的欄座標。"""
    return CARD_SLOT_START_COL + index * CARD_SLOT_STRIDE


# 結束回合按鈕：緊接在第 7 張卡右邊，跟卡片同高。
END_TURN_BUTTON_GAP = 1
END_TURN_BUTTON_WIDTH = 10
END_TURN_BUTTON_HEIGHT = CARD_HEIGHT
END_TURN_BUTTON_X = CARD_SLOT_START_COL + CARD_MAX_COUNT * CARD_SLOT_STRIDE + END_TURN_BUTTON_GAP
END_TURN_BUTTON_Y = HAND_ROW_TOP

# --- 操作提示（列 31）。終端機版才會畫；pygame 版有結束回合按鈕可以點，不需要文字提示。---
HINT_ROW = 31

# --- 獎勵畫面：三張卡置中，列 11 到 20（跟手牌的列 21 到 30 不重疊，
#     滑鼠點擊判定才不會被搞混，不管目前是戰鬥還是獎勵畫面）。 ---
REWARD_CARD_COUNT = 3
REWARD_CARD_GAP = 3
REWARD_ROW_TOP = 11
REWARD_TITLE_ROW = REWARD_ROW_TOP - 3
REWARD_HINT_ROW = REWARD_ROW_TOP + CARD_HEIGHT + 2


def reward_card_x(index: int) -> int:
    """第 index 張獎勵卡（從 0 開始）的左上角欄座標。位置固定（永遠以 3 張卡置中計算），
    跟這次實際抽到幾張卡無關，這樣滑鼠點擊判定才會永遠對得上畫面上的位置。"""
    total_width = REWARD_CARD_COUNT * CARD_WIDTH + (REWARD_CARD_COUNT - 1) * REWARD_CARD_GAP
    start_x = max(0, (SCREEN_WIDTH - total_width) // 2)
    return start_x + index * (CARD_WIDTH + REWARD_CARD_GAP)


# 跳過按鈕：沿用結束回合按鈕的尺寸，固定接在獎勵卡版面的右邊。
REWARD_SKIP_BUTTON_WIDTH = END_TURN_BUTTON_WIDTH
REWARD_SKIP_BUTTON_HEIGHT = END_TURN_BUTTON_HEIGHT
REWARD_SKIP_BUTTON_X = reward_card_x(REWARD_CARD_COUNT - 1) + CARD_WIDTH + REWARD_CARD_GAP
REWARD_SKIP_BUTTON_Y = REWARD_ROW_TOP
