# ASCII 卡牌遊戲（Python 教學用）

## 專案目的

這是 Python 基礎課程的教學遊戲，玩法是簡化版的殺戮尖塔，畫面由 ASCII 字元組成，並用 pygame 視窗顯示。
架構刻意模仿維斯緹（Vestige）的後端 mod 系統：引擎負責載入、驗證與流程控制，遊戲內容與規則都以 mod 形式提供。
學生只會修改 `mods/` 底下的檔案，不會碰 `engine/`。所有設計決策都要以這個前提為準。

## 硬性原則

1. `engine/` 以外的程式碼都視為學生可修改、可能寫錯的程式碼。引擎絕對不能因為 mod 內容錯誤而崩潰。
2. 引擎呼叫 mod 程式碼只能透過 `engine/bridge.py`，scene 不得直接 import mod 模組。
3. 驗證一律在引擎端執行，不能依賴學生程式碼做檢查。
4. 繪圖層只寫入字元格緩衝區，不得知道最後使用哪個渲染器。
5. 給玩家或學生看的訊息一律使用繁體中文，錯誤訊息要讓程式初學者看得懂。
6. 使用 Python 3.10 以上版本；依賴套件只有 pygame-ce（不可使用原版 pygame，因為它沒有新版 Python 的預編譯套件）、pydantic v2 和 pytest。

## 目錄結構

```
（repo 根目錄）
├── main.py                     啟動點：解析參數（--terminal）、載入 mod、進入主迴圈
├── engine/
│   ├── grid.py                 字元格緩衝區
│   ├── draw.py                 繪圖函式（文字、框線、血條、ASCII 圖、卡牌）
│   ├── layout.py               畫面區塊座標常數
│   ├── actions.py              抽象輸入動作
│   ├── fx.py                   視覺效果佇列
│   ├── run.py                  一局遊戲的進度
│   ├── bridge.py               呼叫 mod 程式碼的唯一出入口
│   ├── render/
│   │   ├── base.py             Renderer 介面
│   │   ├── pygame_renderer.py
│   │   └── terminal_renderer.py
│   ├── scenes/
│   │   ├── scene.py            Scene 基底類別
│   │   ├── loading.py          顯示 mod 載入報告
│   │   ├── title.py
│   │   ├── battle.py
│   │   ├── reward.py
│   │   ├── rest.py
│   │   └── result.py
│   └── mod/
│       ├── models.py           Pydantic 資料模型
│       ├── loader.py           掃描、排序、驗證、合併
│       ├── registry.py         效果、狀態、遺物註冊表（第二階段）
│       └── report.py           載入報告與中文化錯誤訊息
├── mods/
│   ├── core/                   遊戲本體
│   │   ├── mod.json
│   │   ├── cards.json
│   │   ├── enemies.json
│   │   ├── run.json
│   │   ├── art/
│   │   └── rules.py
│   └── example_mod/            範例 mod，學生複製此資料夾開始製作
├── assets/fonts/SarasaFixedTC-Regular.ttf
└── tests/
```

## 第一層：字元格與繪圖

- 畫面大小為 96×32 格，每格 10×20 像素，視窗為 960×640。
- `Cell` 包含 `char`、`fg`、`bg` 和 `wide_tail`（是否為寬字元後半格）。
- 寫入 grid 時要把 dirty 設為 True；渲染器畫完後清除。
- `draw.py` 使用 `unicodedata.east_asian_width()` 判斷寬度：`W` 和 `F` 佔兩格，其他佔一格。寬字元的第二格標記為 `wide_tail`，渲染時略過。
- 提供 `text_width(s)` 給排版計算使用。
- 超出畫面範圍的寫入直接裁切，不拋出例外。
- 顏色使用具名色表，例如 white、red、green、cyan、yellow、blue、gray、black，由 `draw.py` 定義，兩種渲染器各自對應到 RGB 或 ANSI 色碼。

`layout.py` 定義各區塊位置，scene 不得直接寫入座標數字：

- 敵人 ASCII 圖：上方中央，24×10
- 敵人狀態列：敵人圖下方，包含名稱、血條、護盾和意圖
- 戰鬥紀錄：右側，寬 30 格
- 玩家狀態列：中下方，包含血條、護盾、能量、抽牌堆數與棄牌堆數
- 手牌：底部，每張 14×7，最多 7 張
- 卡牌內部可顯示 6 個中文字寬度的名稱，因此 CardDef.name 最多 6 字

## 第二層：渲染與輸入

```python
class Renderer:
    def present(self, grid): ...
    def poll_actions(self) -> list[Action]: ...
    def supports_animation(self) -> bool: ...
```

- Action 類型包括 `PlayCard(index)`、`EndTurn()`、`Choose(index)`、`Confirm()`、`Back()`、`Reload()` 和 `Quit()`。
- pygame 版的輸入對應：
  - 按鍵 1 到 7 對應 PlayCard 或 Choose
  - 滑鼠點擊卡牌區域對應 PlayCard
  - E 對應 EndTurn
  - Enter 對應 Confirm
  - F5 對應 Reload
  - Esc 對應 Back
- pygame 版使用 `(char, fg, bg)` 作為 key 快取 `font.render()` 結果，只有 grid dirty 時才重畫。
- 終端機版使用 ANSI 色碼整頁輸出；`poll_actions()` 以 `input()` 阻塞讀取，並把輸入解析成 Action。`supports_animation()` 回傳 False。
- 終端機版啟動時要把 stdout 設為 UTF-8，以避免 Windows cp950 亂碼。
- 主迴圈：`actions = renderer.poll_actions()`，把 actions 交給 `scene.handle()` 後呼叫 `scene.update(dt)`、`scene.draw(grid)`，最後 `renderer.present(grid)`。

## 第三層：mod 系統

### manifest（mod.json）

```json
{"id": "example_mod", "name": "範例擴充", "version": "1.0.0", "author": "someone", "depends": ["core"]}
```

### 完整 id 與覆寫規則

- 內容 id 在 mod 內必須唯一，引擎內部使用完整 id：`mod_id:content_id`。
- 相同完整 id 重複出現時直接報錯，不允許默默覆蓋。
- 如果要修改其他 mod 的內容，必須在資料中宣告 `"overrides": "core:strike"`，並在依賴清單中加入該 mod。覆寫會完整取代原資料，並記錄在載入報告中。

### 載入流程（engine/mod/loader.py）

1. 掃描 `mods/`，略過名稱以 `_` 開頭的資料夾，視為停用。
2. 讀取並驗證每個 `mod.json`。
3. 依照 `depends` 進行拓撲排序，core 永遠最先。缺少依賴或循環依賴時，停用相關 mod。
4. 依序讀取 `cards.json`、`enemies.json`、`run.json`（只有 core 可以提供 run.json），轉換成 Pydantic 模型。所有資料檔都是選填。
5. 讀取並驗證 ASCII 圖檔：路徑相對於該 mod 的 `art/`；最大 24×10；只允許字元碼 32 到 126。尺寸超出時裁切並產生警告，出現非法字元時該敵人無效。
6. 檢查跨檔參照：run.json 中每個 tier 至少要有一個敵人，overrides 的目標必須存在。
7. 合併到全域資料庫。
8. 第二階段：載入 mod 的 `scripts/*.py` 並註冊 class，再檢查 JSON 中的 `effect` 是否有對應的已註冊 class。

### 錯誤等級

- 單筆資料錯誤：跳過那一筆並產生警告。
- manifest 錯誤或依賴失敗：停用整個 mod。
- core 載入失敗或沒有可用內容：致命錯誤，只顯示載入報告，不能開始遊戲。

`report.py` 負責把 Pydantic 錯誤轉成中文，格式為「mod id：檔案名稱，第 N 筆，欄位 X：說明，收到的值」。常見錯誤類型，例如缺少欄位、型別錯誤、超出範圍、字串太長、不在允許選項中，都要有中文對應；沒有對應的錯誤則顯示原文。

### Pydantic 模型（engine/mod/models.py）

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

ID_PATTERN = r"^[a-z][a-z0-9_]*$"

class ModManifest(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str
    version: str
    author: str = "unknown"
    depends: list[str] = []

class CardDef(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(max_length=6)
    cost: int = Field(ge=0, le=5)
    count: int = Field(default=1, ge=0)          # 放入初始牌組的張數，0 表示只出現在獎勵池
    in_reward_pool: bool = True
    damage: Optional[int] = Field(default=None, ge=0)
    hits: Optional[int] = Field(default=None, ge=1)
    block: Optional[int] = Field(default=None, ge=0)
    heal: Optional[int] = Field(default=None, ge=0)
    draw: Optional[int] = Field(default=None, ge=0)
    energy: Optional[int] = Field(default=None, ge=0)
    self_damage: Optional[int] = Field(default=None, ge=0)
    effect: Optional[str] = None                 # 第二階段：註冊表中的完整 id
    overrides: Optional[str] = None

class EnemyAction(BaseModel):
    type: Literal["attack", "block"]
    value: int = Field(ge=0)

class EnemyDef(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(max_length=8)
    tier: Literal["normal", "elite", "boss"]
    hp: int = Field(ge=1)
    art: str
    color: str = "white"
    actions: list[EnemyAction] = Field(min_length=1)
    overrides: Optional[str] = None

class RunStage(BaseModel):
    type: Literal["battle", "rest"]
    tier: Optional[Literal["normal", "elite", "boss"]] = None
```

模型傳給 rules.py 前要用 `model_dump(exclude_none=True)` 轉成 dict，讓規則檔可以用 `"damage" in card` 判斷欄位是否存在。卡牌 dict 還要加入 `full_id`。敵人 dict 的 `art` 要替換成已驗證的字串 list。

## 第四層：bridge（engine/bridge.py）

1. 使用 importlib 載入 `mods/core/rules.py`。
2. 每次呼叫 mod 函式都要包在 try/except 中。出錯時顯示錯誤面板，內容包括函式名稱、例外類型、mod 檔案中的行號與該行程式碼，並讓遊戲回到安全狀態：出牌失敗就取消這次出牌，戰鬥流程出錯則回到標題畫面。從 traceback 找出 mod 檔案中的 frame 顯示，不要只顯示引擎內部的最後一個 frame。
3. 檢查回傳值：
   - `can_play` 必須回傳 bool
   - `check_result` 只能回傳 "win"、"lose" 或 None
   - `play_card` 和 `enemy_act` 必須回傳 str
   - `create_player` 和 `create_enemy` 必須回傳帶有必要欄位的物件
4. 格式錯誤時要顯示中文說明，例如「play_card 應該回傳字串，但回傳了 None」。
5. 提供 `player_view()` 和 `enemy_view()`，回傳固定格式的 dict 給畫面使用。物件是 dict 時直接取欄位；物件有 `to_dict()` 時呼叫該方法（第二階段 class 介面）。
6. 熱重載（F5）時，重新載入所有 mod 資料和 rules.py，並重新開始目前的戰鬥，不保留舊的戰鬥狀態。
7. 觸發時機的呼叫點包括：`on_battle_start`、`on_turn_start`、`before_play`、`after_play`、`on_turn_end`、`on_battle_end`。呼叫前先確認有實作，沒有就跳過。第一階段 rules.py 不需要實作這些函式。

## rules.py 介面（core，第一堂課的練習目標）

引擎會依序呼叫以下函式，名稱與回傳格式固定：

| 函式 | 回傳 |
|---|---|
| `create_player(card_list)` | player dict |
| `create_enemy(enemy_data)` | enemy dict |
| `start_turn(player)` | None |
| `can_play(player, hand_index)` | bool |
| `play_card(player, enemy, hand_index)` | str（顯示訊息） |
| `end_turn(player)` | None |
| `get_enemy_intent(enemy)` | action dict |
| `enemy_act(enemy, player)` | str（顯示訊息） |
| `check_result(player, enemy)` | "win"、"lose" 或 None |

player dict 必要欄位：`name`、`hp`、`max_hp`、`block`、`energy`、`draw_pile`、`hand`、`discard`。
enemy dict 必要欄位：`id`、`name`、`hp`、`max_hp`、`block`、`actions`、`action_index`、`art`、`color`。

rules.py 不處理任何檔案讀取。第一版必須支援 damage、block 和 heal。hits、draw、energy 和 self_damage 保留給學生作為課後作業，引擎要能正常處理「卡牌有這些欄位，但規則沒有處理」的情況。

## 遊戲流程

- scene 狀態機：loading → title → battle → reward 或 rest → 下一個 battle ... → result。
- battle 內部狀態：BATTLE_START → PLAYER_TURN → ENEMY_TURN → BATTLE_END。每次狀態轉換都要呼叫 `check_result`。
- 每場戰鬥結束後，從獎勵池中用 `random.sample` 抽三張卡，可選一張或跳過。休息點回復 30% 最大血量。
- 玩家狀態（血量與牌組）由 run.py 在戰鬥之間保存，每場戰鬥開始時重建抽牌堆。
- 同一種 tier 有多個敵人時隨機選擇。

## fx

效果由引擎比較 bridge 呼叫前後的 view 差異自動產生，學生不需要呼叫任何 fx API：
- 敵人 HP 下降：敵人圖閃紅並左右抖動 1 格
- 玩家 HP 下降：玩家狀態列閃紅
- 護盾增加：護盾數字閃藍色
效果播放期間 battle scene 不接受輸入。終端機版直接略過效果。

## 實作階段與驗收條件

每個階段都要能執行，並附上 pytest 測試，完成後再進入下一階段。

1. **grid、draw、終端機渲染器**
   驗收：中英文混排的框線能在終端機中對齊；`text_width` 有測試。
2. **mod loader 與 report**
   驗收：core 能正常載入；測試要涵蓋欄位錯誤、重複 id、缺少依賴、循環依賴、覆寫、非法 ASCII 字元和圖檔過大，並確認中文報告內容。
3. **bridge 與 battle scene（終端機）**
   驗收：`python main.py --terminal` 可以完整打完一場戰鬥；故意讓 rules.py 拋出例外或回傳錯誤型別時，遊戲不會崩潰，並顯示正確的錯誤訊息。
4. **pygame 渲染器**
   驗收：與終端機版顯示相同內容，中文使用附帶字型正常顯示，滑鼠可以點擊卡牌。
5. **run、reward、rest、result、title、loading**
   驗收：可以完整跑完 run.json 定義的一局遊戲。
6. **fx 與熱重載**
   驗收：修改 rules.py 或 JSON 後按 F5，會立即生效。
7. **第二階段：registry、mod 腳本與 class 介面**
   驗收：example_mod 用一個 class 實作特殊卡牌效果；bridge 能同時支援 dict 與 to_dict() 兩種介面。

## 內容資料

core 的初始內容：
- 初始牌組：斬擊×5、防禦×4、重擊×1
- 獎勵池：盾擊、包紮、鐵壁、處決、連斬、洞察、蓄力、背水
- 敵人：
  - normal：史萊姆、哥布林
  - elite：骷髏騎士
  - boss：守門巨像

`run.json` 內容：

```json
[
    {"type": "battle", "tier": "normal"},
    {"type": "battle", "tier": "normal"},
    {"type": "battle", "tier": "elite"},
    {"type": "rest"},
    {"type": "battle", "tier": "boss"}
]
```

數值請參考 `mods/core/cards.json` 和 `mods/core/enemies.json`。ASCII 圖必須是原創圖案，不要複製網路上的現成作品。

## 不在範圍內

- 分支地圖、商店、藥水、隨機事件、卡牌升級
- 多角色
- 存檔
- 音效
