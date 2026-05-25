# fatty_wiki — AI 知識庫指令手冊

## ⚠️ 每次進來強制執行（不能跳過）

**第一件事：讀 HANDOVER.md**
```
HANDOVER.md 在專案根目錄，裡面有上一個 Agent 留下的待辦事項和注意事項。
沒讀就開始工作 = 重工或踩雷。
```

讀完 HANDOVER.md 之後，再讀這份 CLAUDE.md，才開始回應用戶。

---

## 這個專案是什麼
這是一個個人知識庫系統（fatty_wiki），內容來源是「肥宅老司機」Podcast 的逐字稿。

## 資料夾結構
```
fatty_wiki/
├── Raw/
│   ├── 肥宅老司機/   ← 逐字稿（Claude 親自處理，不再用 Ollama 腳本）
│   ├── claude/       ← PDF / Excel / CSV / 需深度推理的內容（Claude 親自處理）
│   └── processed/    ← 處理完的檔案移到這裡
├── Wiki/
│   ├── 索引.md       ← 整個知識庫的目錄（每次操作後必須更新）
│   ├── 人物/         ← 投稿者、來賓、主持人、個人創作者（每人一個 .md）
│   ├── 店家/         ← 各類場所（按摩、KTV、GoGo Bar 等）
│   ├── 地點/         ← 城市、地區、街道
│   ├── 概念/         ← 術語、行話、概念（每個一個 .md）
│   ├── 來源/         ← 集數摘要頁、PDF 分析頁
│   └── Log.md        ← 每次操作的記錄
├── tools/
│   ├── merge_aliases.py              ← 合併別名、修正全庫連結（機械任務，保留）
│   ├── sync_episode_refs.py          ← 同步 Entity 出現集數 + 階層傳遞（保留）
│   ├── generate_category_indexes.py  ← 重新生成 4 個分類索引 MD（保留）
│   ├── update_index.py               ← 自動生成 Wiki/索引.md（保留）
│   ├── check_links.py                ← 連結品質驗證（選用）
│   ├── ingest_ollama.py              ← 已停用（歷史腳本，勿再呼叫）
│   ├── enrich_contributors.py        ← 已停用（歷史腳本，勿再呼叫）
│   ├── enrich_concepts.py            ← 保留 CONCEPT_ALIAS_MAP 供別名查閱，不再執行
│   └── enrich_places.py              ← 已停用（歷史腳本，勿再呼叫）
└── CLAUDE.md         ← 你現在讀的這份
```

---

## 別名查核流程（每次建立/更新頁面前強制執行）

**在建立或更新任何 人物 / 店家 / 地點 / 概念 頁面之前，必須先做別名查核。**

### Step A：查現有別名表

同時讀取以下兩個地方：
1. `tools/merge_aliases.py` 中的 `ALIAS_MAP`（人名/店名/地名）
2. `tools/enrich_concepts.py` 中的 `CONCEPT_ALIAS_MAP`（術語/概念/服務名）
3. `HANDOVER.md` 底部的「Ollama 別名規律備忘」

### Step B：音近 / 義近 合併判斷

遇到以下情況時，先判斷是否為同一個 Entity：

**高度疑似同一個（直接合併，不問用戶）：**
- 漢字音近：龍筋 / 龍精 / 龍經 / 農金 / 龍金 → 全是同一服務
- 繁簡差異：演员 / 演員、台灣 / 臺灣
- 尊稱後綴：老馬 / 老馬哥（同一人）、伊林 / 伊林老師
- 冗餘地名：台中烏日 → 烏日、新竹湖口 → 湖口、泰國曼谷 → 曼谷
- 括號變體：Caviar / Caviar(魚子醬)、Cherry / Cherry(櫻桃)
- 縮短名稱：141論壇 / 141（同一平台）
- 店名音近且同地點：烏日麗境 / 烏日麗晶 / 烏日力晶（同一區域同性質）

**判斷邏輯（自主執行）：**
1. 名稱音似 → 看地點是否相符
2. 地點相符 → 看服務類型是否相符
3. 全部符合 → 合併，正規名用最常出現的那個
4. 任一不符 → 視為不同 Entity，各自建頁

**真正不確定時才問用戶（問法範例）：**
> 「烏日郵輪」和「烏日麗境」音近且同在烏日，但服務描述差異較大，請確認是否為同一家店？

---

## 核心工作流程

### 指令：`ingest` / `START` / 用戶直接貼入逐字稿

當用戶說「開始處理」「ingest」或直接提供逐字稿內容時：

**Step 1 — 建來源頁（Claude 親自讀取）**

- 讀取逐字稿（`Raw/肥宅老司機/` 下的 .md / .txt，或用戶直接貼的內容）
- 在 `Wiki/來源/` 建立來源摘要頁（格式見下方「來源頁格式」）
- 必須包含：本集嘉賓、摘要、店家表、妹子點評、精彩故事、實用知識、術語、投稿者/來賓/主持人觀點
- 處理完把原始檔移到 `Raw/processed/`

**Step 2 — 建立/更新人物頁**

- 提取本集所有投稿者、來賓、主持人
- 先做別名查核（見上方「別名查核流程」），確認非重複頁面後建立
- 更新 `Wiki/人物/人名.md`（跨集累積，不覆蓋現有內容，追加新集資料）

**Step 3 — 建立/更新店家、地點、概念頁**

- 從來源頁提取所有店家、地點、術語
- 每個 Entity：先做別名查核 → 確認正規名 → 建立或更新對應頁面
- 店家頁要有：類型、地點、服務類型、費用、特色、妹子點評（如有）、出現集數
- 地點頁要有：國家、類型、特色描述、出現集數
- 概念頁要有：定義、出現來源、相關概念

**Step 4 — 機械腳本收尾**

⚠️ **merge_aliases.py 禁止用來合併頁面內容**（會插入低品質 stub 破壞手寫頁面）。
別名頁的合併一律由 Claude 手動讀取、手動寫入主頁、手動刪 stub。

只跑以下 3 個不改寫內容的腳本：
```bash
python -X utf8 tools/sync_episode_refs.py
python -X utf8 tools/generate_category_indexes.py
python -X utf8 tools/update_index.py
```

ALIAS_MAP 仍然維護（供全站連結替換追蹤），但**不執行 merge_aliases.py**。

**Step 4.5 — 手動補集數索引（⚠️ 手動）**
在 `Wiki/來源/肥宅老司機-集數索引.md` 對應區段補一行：
```
| [[肥宅老司機-S3EPxxx]] | 集數標題 |
```

**Step 5 — 在 Log.md 記錄本次處理內容**

**Step 6 — 檢查 Wiki/索引.md 手工區段是否需要更新**

`update_index.py` 只更新 AUTO 區塊（數字統計）。以下手工維護的區段，有新內容就要手動補：
- **地域導航**（各國/城市條目）：新地點或該地點有重要新店家時補
- **常見概念 → 場所類型**：新增重要場所類型概念時補
- **知識缺口**：有填補時劃掉，有新缺口時加入

---

### 指令：`fixname` / 用戶說出名字等號關係（即時寫入別名表）

**觸發條件（以下任一）：**
- 用戶說 `fixname A, B, C → D`
- 用戶說「A 就是 B」「A 其實是 B」「A 和 B 是同一個」「A = B」

**執行動作：**
1. 判斷類型：
   - 人名 / 店名 / 地名 → 寫進 `tools/merge_aliases.py` 的 `ALIAS_MAP`
   - 術語 / 服務名稱 / 行話 → 寫進 `tools/enrich_concepts.py` 的 `CONCEPT_ALIAS_MAP`
2. 正規名（canonical）放 key，所有錯字/同音字/別名放 value list
3. 同時更新 `HANDOVER.md` 底部的「Ollama 別名規律備忘」

**格式範例（`ALIAS_MAP`）：**
```python
"伊林龍筋": ["一一", "一一老師", "伊林", "伊林農金"],
```

**格式範例（`CONCEPT_ALIAS_MAP`）：**
```python
"龍筋": ["龍經", "農金", "龍金", "龍精"],
```

⚠️ 寫完立刻確認：讀回來給用戶看，確保寫入正確。

---

### 指令：`fix` / `補救`（一次性資料補救）
當用戶說「fix」「補救」「執行補救流程」時執行：

> 這個指令是用來修補過去腳本 bug 造成的歷史資料缺口，不是日常流程。
> 執行前先讀 HANDOVER.md 的 🔴 區塊，確認目前需要做哪些步驟。

```bash
python -X utf8 tools/merge_aliases.py
python -X utf8 tools/sync_episode_refs.py
python -X utf8 tools/generate_category_indexes.py
python -X utf8 tools/update_index.py
```

---

### 指令：`ask`（回答問題）
當用戶問任何問題時：

1. 先讀 `Wiki/索引.md` 確認相關頁面在哪裡
2. 讀相關的 概念 / 人物 / 店家 / 地點 / 來源 頁面
3. 綜合多篇來源回答，並標註「根據 [[頁面名稱]]」
4. 如果發現知識不足，主動說明缺口在哪

### 指令：`health`（健康檢查）
當用戶說「健康檢查」「check」時：

1. 掃描所有 Wiki 頁面
2. 找出：孤立頁面（沒有任何連結）、空的概念、矛盾的描述
3. 列出建議補充的主題
4. 不要自動修改，只報告

---

## 頁面格式規範

### 來源頁（Wiki/來源/肥宅老司機-S3EPxxx.md）

```markdown
# 肥宅老司機 S3EPxxx

**來源**：肥宅老司機 Podcast S3EPxxx
**日期**：[處理日期]
**作者**：[[肥宅老司機]]
**分類**：播客、台灣

## 本集嘉賓
[[嘉賓名]]

## 摘要
[100-200 字的核心主題]

## 店家與地點資訊
| 店名 | 地點/城市 | 費用 | 特色或評價 | 實用小技巧 |
| :--- | :--- | :--- | :--- | :--- |

## 妹子點評
**[暱稱/描述]**（店名，城市）
- 外貌：
- 服務：
- 特色：
- 備註：

## 精彩故事
1. **【故事標題】**：敘述

## 實用知識與技巧
- 重點一
- 重點二

## 術語與概念
[[術語]] — 定義說明

## 投稿者
### 投稿者名
**故事**：故事摘要
**知識點**：

## 來賓分享
### 來賓名
**主題**：主題摘要
**知識點**：

## 主持人觀點
### 老雞
-
### 老濕
-

## 提到的人物與地點
[[人物A]], [[地點B]], [[店家C]]
```

### 店家頁（Wiki/店家/店名.md）

```markdown
# 店名

**類型**：GoGo Bar / 按摩店 / KTV / 成人娛樂 / 餐廳（非成人場所） 等
**地點**：[[國家]][[城市]]
**服務類型**：具體服務描述

## 特色
[核心特色描述，含集數與嘉賓來源]

## 消費資訊
| 項目 | 費用 | 備註 |

## 妹子點評（如有）

## 實用技巧

## 出現集數
- [[肥宅老司機-S3EPxxx]]（本集主題摘要）
```

### 地點頁（Wiki/地點/地名.md）

```markdown
# 地名

**國家**：[[國家]]
**類型**：城市 / 地區 / 街道 / 紅燈區

## 特色
[地點核心描述]

## 推薦場所
- [[店家A]] — 特色
- [[店家B]] — 特色

## 出現集數
- [[肥宅老司機-S3EPxxx]]
```

### 概念頁（Wiki/概念/概念名稱.md）

```markdown
# 概念名稱

**類型**：術語 / 行話 / 服務名稱

## 定義
[清楚的定義，白話說明]

## 出現集數
- [[肥宅老司機-S3EPxxx]] — 在本集的用法
```

---

## 重要原則

- **每次操作後必須更新 索引.md**（跑 `update_index.py`）
- **用 [[雙括號]] 建立連結**，讓 Obsidian 圖譜能顯示關係
- **支援格式**：.md、.txt、.pdf（PDF 直接讀，不需轉檔）
- **不要修改 Raw/ 裡的原始檔案內容**，只移動位置
- **Log.md 用時間戳記錄**，讓用戶能追蹤歷史
- **非成人場所必須明確標記**：`（非成人場所）`，避免誤導
- **地點/類型有誤時**加 `> [!warning] ⚠️ 地點更正` 或 `> [!warning] ⚠️ 類型更正` callout
- **別名判斷自主決定**：音近+地點+類型全符合就合併，不必等用戶確認；真正不確定才問
- **人物名稱疑慮必問**：逐字稿人名如果「看起來像外號但有點奇怪」，先問用戶確認是否為台語音譯或誤寫，不要先建頁再刪改（代價高）
- **新建人物頁前先 grep**：確認 Wiki/人物/ 下沒有同人的舊頁（不同稱呼），避免重複建頁後又要合併
- **合併人物頁時**：必須讀完兩頁現有內容，再手工挑選保留哪些集數/故事，不能直接覆蓋

---

## 別名規律快速參考（常見 Ollama 誤寫）

| 正規名 | 常見誤寫 / 別名 |
|--------|----------------|
| 龍筋 | 龍精、龍經、農金、龍金 |
| 芭提雅 | 芭達雅、帕塔亞、Pattaya |
| 胡志明 | 胡志明市 |
| 萬華區 | 萬華 |
| 林森北 | 林森北路 |
| 老雞 | 老基、老機 |
| 老濕 | 老師（主持人） |
| 喇賽 | 喇塞、LASAI |
| 141 | 141論壇 |
| 豆干厝 | 豆干座、豆干措、豆乾、豆乾錯 |
| 長平 | 長坪、東莞長坪 |
| 永登埔 | 永登浦、永登普 |
| 圖山 | 屠山、土山 |
| 烏日（各店） | 烏日麗境/麗晶/力晶/郵輪/利京 — 先查地點和類型才合併 |
| 小藥師 | 洨藥師（台語暱稱）、小鑰匙（逐字稿誤寫） |
| 大口袋 | 大摳呆（台語，大支很胖）—字幕軟體把台語音轉成漢字 |
| 私台 / 私檯 | 師台、師臺（逐字稿誤寫，「私」常被辨識成「師」）|
| 公台 / 公檯 | 攻台（逐字稿誤字，公家概念→公台，非「攻擊」的攻）|
| 八爺 | 巴爺（八/巴 同音 bā yé，同一來賓，集數不重疊）|
| 富國 KTV | 復國 KTV、復國（Phú Quốc 富國島，復=誤字）|
| 無心插柳柳橙汁 | 無心插柳柳成枝（橙汁/成枝同音 chéng zhī，pun 梗名）|

**台語暱稱 / 術語字幕誤寫規律（常見模式）：**
- 台語俚語被字幕軟體轉成同音漢字：洨→小、摳呆→口袋
- 台語術語字幕辨識錯誤：私→師（私台→師台）、公→攻（公台→攻台）
- 遇到「感覺是外號/術語但又不太對」→ 優先問用戶確認，不要直接建頁

完整別名表：`tools/merge_aliases.py` → `ALIAS_MAP`、`tools/enrich_concepts.py` → `CONCEPT_ALIAS_MAP`

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%). Format flags (-c, -l, -L, -o, -Z) run raw.
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->