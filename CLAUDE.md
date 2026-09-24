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
│   ├── draw.py                 繪圖函式（文字、換行、框線、血條、ASCII 圖、卡牌）
│   ├── layout.py               畫面區塊座標常數
│   ├── palette.py              具名色表
│   ├── cardtext.py             卡牌描述：佔位符代入與自動產生
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
├── tools/                      開發用的 demo 與工具，不放在根目錄
├── assets/fonts/SarasaFixedTC-Regular.ttf
└── tests/
```

## 第一層：字元格與繪圖

- 畫面大小為 96×32 格，每格 10×20 像素，視窗為 960×640。
- `Cell` 包含 `char`、`fg`、`bg` 和 `wide_tail`（是否為寬字元後半格）。
- 寫入 grid 時要把 dirty 設為 True；渲染器畫完後清除。
- `draw.py` 使用 `unicodedata.east_asian_width()` 判斷寬度：`W` 和 `F` 佔兩格，其他（包含 `A` 寬度不明確的字元，例如 ─ ═ ║ █ ░ ◆ ◇ ●）一律佔一格。附帶字型 Sarasa Fixed 會用半形寬度繪製這些字元，因此畫面與此規則一致。
- 寬字元的第二格標記為 `wide_tail`，渲染時略過。寬字元只剩一格空間時整個字不畫。覆寫寬字元的前半格或後半格時，另一半要清成空白。
- 提供 `text_width(s)` 給排版計算使用。
- 超出畫面範圍的寫入直接裁切，不拋出例外。

### 換行：`wrap_text(text, width) -> list[str]`

- 以顯示寬度計算，不以字元數計算。
- 中文字之間可以斷行；連續的 ASCII 英數字（例如 `10`、`HP`）視為一個單位，不可從中間斷開。單位本身超過 width 時才強制切斷。
- 行首禁則：`，。、；：！？）」』…` 不可出現在行首。遇到時採用「推出式」處理：把上一行的最後一個字連同標點一起移到下一行，不可讓標點超出 width（卡牌框線緊鄰文字，超出會蓋掉框線）。
- 原文中的 `\n` 視為強制換行。
- 必須有測試：剛好等於 width、行首標點、數字不被切斷、強制換行、空字串。

### 色表（engine/palette.py）

色表使用語意名稱，兩種渲染器各自對應：pygame 使用下列 RGB，終端機對應到最接近的 ANSI 256 色。

| 名稱 | RGB | 用途 |
|---|---|---|
| bg | #0E0C0A | 背景 |
| frame | #B08D57 | 外框與分隔線（暗金） |
| frame_dim | #5C4A2E | 次要分隔線 |
| text | #D8D2C4 | 一般文字 |
| dim | #6E6658 | 次要文字、無法打出的卡牌 |
| highlight | #FFF4D6 | 滑鼠停留、選取中 |
| hp | #C0392B | 血條與扣血數字 |
| hp_empty | #3A2A26 | 血條空的部分 |
| block | #4A90C2 | 護盾 |
| energy | #E0B23C | 能量與卡牌費用 |
| attack | #C8553D | 攻擊牌框線、攻擊意圖 |
| skill | #4A7FB5 | 技能牌框線、防禦意圖 |
| power | #C9A227 | 能力牌框線 |
| status_good | #6FAF5F | 正面狀態（第二階段） |
| status_bad | #9B59B6 | 負面狀態（第二階段） |
| keyword | #E8C170 | 描述中的【關鍵字】 |

敵人 ASCII 圖的 `color` 欄位使用另一組基本色名稱：white、red、green、cyan、yellow、blue、gray、magenta。

## 畫面版面（layout.py）

風格為「厚重奇幻」：雙線外框、暗金框線、標題帶。以下是參考畫面，座標以下面的列、欄定義為準（從 0 開始）。

```
╔══════════════════════════════════════════════════════════════╦═══════════════════════════════╗
║ ◆ 地下第 3 層                                          回合 4║      ─── 戰鬥紀錄 ───         ║
╠══════════════════════════════════════════════════════════════╣                               ║
║                           .-"""-.                            ║                               ║
║                          /  o o  \                           ║                               ║
║                         |    ^    |                          ║                               ║
║                                                               ║                               ║
║           ═══════════════[ 哥布林 ]═══════════════           ║ › 斬擊 造成 6 傷害            ║
║               HP ██████████████░░░░░░ 24/35      盾 6        ║ › 哥布林 獲得 6 護盾          ║
║                       >> 準備攻擊 8 <<                       ║ › 你受到 5 傷害               ║
║                                                               ║                               ║
╠══════════════════════════════════════════════════════════════╩═══════════════════════════════╣
║ [ 冒險者 ]  HP █████████████████░░░ 42/50    盾 5    能量 ◆    牌堆 0 / 棄牌 0               ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝
 ╔◆1════════╗╔◆1════════╗╔◆1════════╗╔◆0════════╗╔◆1════════╗                         ╔════════╗
 ║   斬擊   ║║   連斬   ║║   背水   ║║   洞察   ║║   盾擊   ║                         ║        ║
 ╟──────────╢╟──────────╢╟──────────╢╟──────────╢╟──────────╢                         ║        ║
 ║造成 6 點 ║║造成 3 點 ║║造成 10 點║║抽 2 張   ║║造成 5 點 ║                         ║        ║
 ║傷害。    ║║傷害，重複║║傷害。自己║║牌。      ║║傷害，獲得║                         ║結束回合║
 ║          ║║3 次。    ║║失去 3 點 ║║          ║║5 點護盾。║                         ║        ║
 ║          ║║          ║║生命。    ║║          ║║          ║                         ║  [E]   ║
 ║          ║║          ║║          ║║          ║║          ║                         ║        ║
 ║          ║║          ║║          ║║          ║║          ║                         ║        ║
 ╚═══攻擊═══╝╚═══攻擊═══╝╚═══攻擊═══╝╚═══技能═══╝╚═══攻擊═══╝                         ╚════════╝
            [1-7] 出牌        [E] 結束回合        [?N] 檢視卡牌        [?] 取消檢視
```

（上圖是實際渲染結果，這裡把敵人圖裁短、省略力量/狀態列方便排版；上圖是終端機版，有操作提示列；
pygame 版沒有操作提示列，見下方「操作提示」一節。手牌之間刻意不留間距，才能在欄 0 到 95
內同時放下 7 張卡與結束回合按鈕；實際欄位仍以下方座標為準。）

### 主框（列 0 到 20）

- 外框欄 0 與欄 95。左面板內容欄 1 到 62，左右分隔線在欄 63，右面板內容欄 64 到 94。
- 列 0：上框線，欄 63 為 `╦`。
- 列 1：左側顯示樓層（`◆ 地下第 N 層`）與回合數；右側顯示面板標題。
- 列 2：只在左面板畫分隔線（欄 0 `╠`、欄 63 `╣`），右面板繼續延伸。
- 列 3 到 12：敵人 ASCII 圖區域，24×10，在左面板內水平置中。
- 列 13：敵人名稱標題帶，格式為 `════[ 名稱 ]════`，置中，框線用 frame 色，名稱用 text 色。
- 列 14：敵人血條（寬 20，`█` 與 `░`）、`目前/最大`、護盾（護盾為 0 時不顯示）。
- 列 15：意圖，格式為 `>> 準備攻擊 N <<` 或 `>> 準備防禦 N <<`，攻擊用 attack 色，防禦用 skill 色。
- 列 16：敵人狀態列，第一階段留空。
- 列 17：全寬分隔線，欄 0 `╠`、欄 63 `╩`、欄 95 `╣`。
- 列 18：玩家狀態，包含 `[ 冒險者 ]`、血條（寬 20）、護盾、能量（`◆` 為剩餘、`◇` 為已用，energy 色）、牌堆數與棄牌數。
- 列 19：玩家狀態列，第一階段留空。
- 列 20：下框線。

### 右面板（列 3 到 16，寬 31）

- 平常顯示戰鬥紀錄：最新的在最下面，每則以 `› ` 開頭，用 `wrap_text` 換行，寬度 29，超出的舊紀錄捨棄。
- 檢視卡牌時切換成卡牌詳細資訊：名稱、費用、類型，以及以寬度 29 換行的完整描述。第二階段會在描述下方加入關鍵字說明。

### 手牌（列 21 到 30）

- 每張卡寬 12、高 10，最多 7 張。第 i 張（從 0 開始）的左上角是欄 `layout.card_slot_x(i)`
  （= `1 + i * 12`）、列 21。卡片彼此緊鄰、不留間距，這樣欄 1 到 85 剛好放滿 7 張卡，
  才擠得出空間給右邊的結束回合按鈕。
- 卡牌結構：
  - 第 0 列：上框線，費用嵌在左側，例如 `╔◆1════════╗`，費用數字用 energy 色。
  - 第 1 列：卡名置中，內部寬 10，最多 5 個中文字。
  - 第 2 列：`╟──────────╢` 分隔線。
  - 第 3 到 8 列：描述，最多 6 行，每行寬 10。
  - 第 9 列：下框線，類型文字置中，例如 `╚═══攻擊═══╝`。
- 卡牌框線顏色依類型決定：攻擊為 attack、技能為 skill、能力為 power。
- 能量不足以打出的卡，框線與文字全部改用 dim 色。
- 描述中以 `【】` 包住的文字使用 keyword 色。

#### 選取狀態（滑鼠兩段式點擊，狀態存在 battle scene，不在 renderer）

- 手牌兩段式點擊：第一下選取這張卡——右面板固定顯示這張卡的詳細資訊（直到取消選取或選到別張
  卡之前都不會被滑鼠移出蓋掉），卡片整張上移一格（`layout.SELECTED_CARD_ROW_OFFSET`，即第 0
  列變成畫在列 20）。對已經選取的那張卡再點一次才會真的出牌。點另一張卡會改成選取那一張；點
  空白處或按 Esc 取消選取。
- 能量不足打不起的卡：第一下一樣會在右面板顯示詳情，但不會進入選取狀態（卡片不會上移、框線不
  會變成 highlight），再點也不會出牌。
- 選取中或滑鼠停留中的卡牌，框線改用 highlight 色。
- 數字鍵 1 到 7 維持原本行為：一律直接出牌，不走兩段式選取。

#### 結束回合按鈕

- 緊接在第 7 張卡右邊（`layout.END_TURN_BUTTON_X`，= `1 + 7 * 12 + 1`），寬 10、高 10（跟卡片
  同高），雙線框，置中顯示「結束回合」與 `[E]`。
- 平常框線用 frame 色；滑鼠移到按鈕上方時改用 highlight 色；點擊等於送出 `EndTurn()`。
- pygame 版與終端機版都會畫這個按鈕；終端機沒有滑鼠事件，所以按鈕不會變色，操作還是只能按
  `E` 鍵，行為跟熱重載前完全一樣。

### 操作提示（列 31）

- 終端機版：置中顯示目前可用的按鍵提示，使用 dim 色。
- pygame 版：不畫這一列。滑鼠停留在卡牌或按鈕上就會看到提示，不需要額外的文字說明。

### 獎勵畫面（reward scene，列 8 到 23）

- 三張獎勵卡置中排列，欄位由 `layout.reward_card_x(i)` 決定（固定以 3 張卡置中計算，
  跟這次實際抽到幾張無關，滑鼠點擊判定才會永遠對得上畫面）；卡片本身跟手牌同樣式（寬 12、
  高 10，最多顯示 6 行描述）。標題在 `layout.REWARD_TITLE_ROW`（卡片上方 3 列），沿用手牌
  的卡片列高（列 11 到 20），跟手牌的列 21 到 30 不重疊，避免滑鼠點擊判定搞混兩個畫面。
- 跳過按鈕：緊接在第 3 張卡右邊（`layout.REWARD_SKIP_BUTTON_X`），尺寸跟結束回合按鈕相同
  （寬 10、高 10、雙線框），置中顯示「跳過」與 `[B]`。平常框線用 frame 色，滑鼠移上去用
  highlight 色，點擊送出 `Skip()`——不管有沒有選取中的卡，點下去一律直接跳過。
- 三張卡兩段式點擊（選取狀態放在 `RewardScene`，不在 renderer；終端機沒有滑鼠事件，行為完全
  不變）：第一下選取——卡片整張上移一格（`layout.SELECTED_CARD_ROW_OFFSET`），框線改用
  highlight 色；對已經選取的那張卡再點一次才確定加入牌組。點另一張卡改成選取那一張；點空白處
  （`ClickCard(None)`）取消選取。Esc（`Back()`）：如果目前有選取中的卡，只取消選取；沒有選取
  中的卡時維持原本「跳過」的行為（終端機的 `b` 鍵一律走這一支，selected_index 永遠是
  `None`，行為跟改版前完全一樣）。
- 數字鍵 1 到 3（`PlayCard`／`Choose`）維持原本行為：一律直接選取該卡加入牌組，不走兩段式。
- pygame 版：不畫「[1-3] 選擇這張卡　[B] 跳過」的文字提示（`layout.REWARD_HINT_ROW`），滑鼠
  停留在按鈕上就會看到提示。終端機版保留文字提示。

## 卡牌描述（engine/cardtext.py）

- CardDef 的 `description` 是選填欄位，可使用佔位符 `{damage}`、`{hits}`、`{block}`、`{heal}`、`{draw}`、`{energy}`、`{self_damage}`。引擎會用卡牌資料的值代入。
- 佔位符只能引用這張卡有值的數值欄位。引用不存在的名稱或沒有值的欄位時，這張卡判定無效，並在報告中顯示是哪個佔位符有問題。
- 沒有填寫 `description` 時，依照下列順序自動產生，只串接有值的欄位：
  1. damage，並有 hits：`造成 {damage} 點傷害，重複 {hits} 次。`
  2. damage，沒有 hits：`造成 {damage} 點傷害。`
  3. block：`獲得 {block} 點護盾。`
  4. heal：`回復 {heal} 點生命。`
  5. draw：`抽 {draw} 張牌。`
  6. energy：`獲得 {energy} 點能量。`
  7. self_damage：`失去 {self_damage} 點生命。`
- 有 `effect` 的卡牌（第二階段）必須填寫 `description`，因為引擎無法從程式推測效果。
- 描述代入數值後，以寬度 10 換行，超過 6 行時這張卡無效。報告格式例如：「example_mod：cards.json，卡牌 fireball：描述超過卡片空間，換行後共 8 行，上限 6 行」。
- 第二階段加入力量等修正後，佔位符會代入修正後的數值；和基礎值不同時，數字以 status_good 或 hp 色顯示。第一階段不需要實作這一點，但 cardtext 的介面要允許傳入修正後的數值。

## 第二層：渲染與輸入

```python
class Renderer:
    def present(self, grid): ...
    def poll_actions(self) -> list[Action]: ...
    def supports_animation(self) -> bool: ...
```

- Action 類型包括 `PlayCard(index)`、`EndTurn()`、`Choose(index)`、`Confirm()`、`Back()`、`Reload()`、`Quit()`、`Inspect(index)`、`ClickCard(index)`、`HoverEndTurn(active)`、`Skip()` 和 `HoverSkip(active)`。`Inspect(None)` 表示結束檢視。
- `ClickCard(index)` 跟 `PlayCard(index)` 不同：renderer 只負責回報「滑鼠點到第幾張卡」（點空白處是
  `ClickCard(None)`），要不要出牌／加入牌組、要不要進入選取狀態一律由 scene 決定（兩段式點擊的
  狀態存在 scene 裡，不在 renderer；battle scene 跟 reward scene 都用這一組動作）。`PlayCard(index)`／
  `Choose(index)` 只由數字鍵觸發，一律直接生效，不走兩段式。
- pygame 版的輸入對應：
  - 按鍵 1 到 7（battle）或 1 到 3（reward）對應 PlayCard 或 Choose，一律直接生效
  - 滑鼠點擊卡牌區域（手牌或獎勵卡）對應 `ClickCard(i)`，點空白處對應 `ClickCard(None)`
  - 滑鼠移入卡牌區域對應 `Inspect(i)`，移出所有卡牌時對應 `Inspect(None)`
  - 滑鼠點擊結束回合按鈕對應 EndTurn；移入/移出按鈕對應 `HoverEndTurn(True)`／`HoverEndTurn(False)`
  - 滑鼠點擊獎勵畫面的跳過按鈕對應 `Skip()`；移入/移出按鈕對應 `HoverSkip(True)`／`HoverSkip(False)`
  - E 對應 EndTurn
  - Enter 對應 Confirm
  - F5 對應 Reload
  - Esc 對應 Back
- 終端機版輸入 `?2` 對應 `Inspect(1)`，輸入 `?` 對應 `Inspect(None)`。終端機版不會送出
  `ClickCard`／`HoverEndTurn`／`Skip`／`HoverSkip`（沒有滑鼠事件），所以兩段式選取與按鈕變色都
  不會發生，操作跟原本完全一樣；獎勵畫面的 `b` 鍵維持原本「跳過」的行為。
- pygame 版使用 `(char, fg, bg)` 作為 key 快取 `font.render()` 結果，只有 grid dirty 時才重畫。
- 終端機版使用 ANSI 色碼整頁輸出；`poll_actions()` 以 `input()` 阻塞讀取，並把輸入解析成 Action。`supports_animation()` 回傳 False。
- 終端機版啟動時要把 stdout 設為 UTF-8，以避免 Windows cp950 亂碼。終端機寬度小於 96 欄或高度小於 33 列時，顯示中文提示要求使用者放大視窗，不要輸出跑版的畫面。
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
5. 驗證卡牌描述：代入佔位符、換行並檢查行數，規則見「卡牌描述」一節。
6. 讀取並驗證 ASCII 圖檔：路徑相對於該 mod 的 `art/`；最大 24×10；只允許字元碼 32 到 126。尺寸超出時裁切並產生警告，出現非法字元時該敵人無效。
7. 檢查跨檔參照：run.json 中每個 tier 至少要有一個敵人，overrides 的目標必須存在。
8. 合併到全域資料庫。
9. 第二階段：載入 mod 的 `scripts/*.py` 並註冊 class，再檢查 JSON 中的 `effect` 是否有對應的已註冊 class。

### 錯誤等級

- 單筆資料錯誤：跳過那一筆並產生警告。
- manifest 錯誤或依賴失敗：停用整個 mod。
- core 載入失敗或沒有可用內容：致命錯誤，只顯示載入報告，不能開始遊戲。

`report.py` 負責把 Pydantic 錯誤轉成中文，格式為「mod id：檔案名稱，第 N 筆，欄位 X：說明，收到的值」。常見錯誤類型，例如缺少欄位、型別錯誤、超出範圍、字串太長、不在允許選項中，都要有中文對應；沒有對應的錯誤則顯示原文。

### Pydantic 模型（engine/mod/models.py）

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

from engine.draw import text_width

ID_PATTERN = r"^[a-z][a-z0-9_]*$"

class ModManifest(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str
    version: str
    author: str = "unknown"
    depends: list[str] = []

class CardDef(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str
    type: Literal["attack", "skill", "power"]
    cost: int = Field(ge=0, le=5)
    description: Optional[str] = None            # 可用 {damage} 等佔位符；省略時自動產生
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

    @field_validator("name")
    @classmethod
    def name_fits_card(cls, v: str) -> str:
        if text_width(v) > 10:
            raise ValueError("卡名太長：顯示寬度最多 10 格（5 個中文字）")
        return v

class EnemyAction(BaseModel):
    type: Literal["attack", "block"]
    value: int = Field(ge=0)

class EnemyDef(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str
    tier: Literal["normal", "elite", "boss"]
    hp: int = Field(ge=1)
    art: str
    color: str = "white"
    actions: list[EnemyAction] = Field(min_length=1)
    overrides: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_fits_band(cls, v: str) -> str:
        if text_width(v) > 16:
            raise ValueError("敵人名稱太長：顯示寬度最多 16 格（8 個中文字）")
        return v

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

rules.py 不處理任何檔案讀取，也不處理卡牌描述，描述由引擎的 cardtext 負責。第一版必須支援 damage、block 和 heal。hits、draw、energy 和 self_damage 保留給學生作為課後作業，引擎要能正常處理「卡牌有這些欄位，但規則沒有處理」的情況。

## 遊戲流程

- scene 狀態機：loading → title → battle → reward 或 rest → 下一個 battle ... → result。
- battle 內部狀態：BATTLE_START → PLAYER_TURN → ENEMY_TURN → BATTLE_END。每次狀態轉換都要呼叫 `check_result`。
- 每場戰鬥結束後，從獎勵池中用 `random.sample` 抽三張卡，可選一張或跳過。獎勵畫面沿用手牌的卡牌樣式。休息點回復 30% 最大血量。
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

1. **grid、draw、終端機渲染器**（已完成）
1b. **套用版面規格**
   內容：palette.py、layout.py 座標常數、`wrap_text`、cardtext.py、雙線框線與卡牌繪製、`Inspect` 動作、終端機尺寸檢查。
   驗收：`wrap_text` 與 cardtext 的測試通過（包含行首標點與佔位符錯誤）；`tools/demo_layout.py` 用假資料畫出與「畫面版面」參考圖相同結構的完整戰鬥畫面，至少包含 5 張不同描述長度的卡牌與一張能量不足的卡牌。
2. **mod loader 與 report**
   驗收：core 能正常載入；測試要涵蓋欄位錯誤、重複 id、缺少依賴、循環依賴、覆寫、非法 ASCII 字元、圖檔過大、卡名太長、描述超過 6 行、佔位符錯誤，並確認中文報告內容，不能只驗證有沒有報錯。
3. **bridge 與 battle scene（終端機）**
   驗收：`python main.py --terminal` 可以完整打完一場戰鬥；故意讓 rules.py 拋出例外或回傳錯誤型別時，遊戲不會崩潰，並顯示正確的錯誤訊息。
4. **pygame 渲染器**
   驗收：與終端機版顯示相同內容，中文使用附帶字型正常顯示，滑鼠可以點擊卡牌，滑鼠停留會顯示卡牌詳細資訊。
5. **run、reward、rest、result、title、loading**
   驗收：可以完整跑完 run.json 定義的一局遊戲。
6. **fx 與熱重載**
   驗收：修改 rules.py 或 JSON 後按 F5，會立即生效。
7. **第二階段：registry、mod 腳本與 class 介面**
   驗收：example_mod 用一個 class 實作特殊卡牌效果；bridge 能同時支援 dict 與 to_dict() 兩種介面。

## 內容資料

### 卡牌（mods/core/cards.json）

描述欄位全部省略，使用自動產生。`count` 為放入初始牌組的張數；初始牌的 `in_reward_pool` 為 false。

| id | 名稱 | 類型 | 費用 | 效果欄位 | count | in_reward_pool |
|---|---|---|---|---|---|---|
| strike | 斬擊 | attack | 1 | damage 6 | 5 | false |
| defend | 防禦 | skill | 1 | block 5 | 4 | false |
| bash | 重擊 | attack | 2 | damage 12 | 1 | false |
| shield_bash | 盾擊 | attack | 1 | damage 5, block 5 | 0 | true |
| bandage | 包紮 | skill | 1 | heal 6 | 0 | true |
| iron_wall | 鐵壁 | skill | 2 | block 12 | 0 | true |
| execute | 處決 | attack | 3 | damage 24 | 0 | true |
| flurry | 連斬 | attack | 1 | damage 3, hits 3 | 0 | true |
| insight | 洞察 | skill | 0 | draw 2 | 0 | true |
| charge | 蓄力 | skill | 0 | energy 2 | 0 | true |
| last_stand | 背水 | attack | 1 | damage 10, self_damage 3 | 0 | true |

### 敵人（mods/core/enemies.json）

| id | 名稱 | tier | HP | 顏色 | 行動循環 |
|---|---|---|---|---|---|
| slime | 史萊姆 | normal | 25 | cyan | 攻擊 5 → 攻擊 5 → 防禦 5 |
| goblin | 哥布林 | normal | 35 | green | 攻擊 8 → 攻擊 5 → 防禦 6 |
| skeleton_knight | 骷髏騎士 | elite | 55 | white | 防禦 10 → 攻擊 16 |
| gate_colossus | 守門巨像 | boss | 120 | yellow | 防禦 15 → 攻擊 6 → 攻擊 6 → 攻擊 25 |

### 關卡（mods/core/run.json）

```json
[
    {"type": "battle", "tier": "normal"},
    {"type": "battle", "tier": "normal"},
    {"type": "battle", "tier": "elite"},
    {"type": "rest"},
    {"type": "battle", "tier": "boss"}
]
```

ASCII 圖必須是原創圖案，不要複製網路上的現成作品。

## 不在範圍內

- 分支地圖、商店、藥水、隨機事件、卡牌升級
- 多角色
- 存檔
- 音效
