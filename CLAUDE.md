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
這是一個個人知識庫系統（fatty_wiki）。

## 資料夾結構
```
MyWiki/
├── Raw/
│   ├── 肥宅老司機/   ← 逐字稿（Ollama 處理）
│   ├── claude/       ← 高精度需求：PDF 分析、Excel/CSV、複雜推理（Claude 親自處理）
│   └── processed/    ← 處理完的檔案移到這裡
├── Wiki/
│   ├── 索引.md       ← 整個知識庫的目錄（每次操作後必須更新）
│   ├── 人物/         ← 投稿者、來賓、主持人、個人創作者（每人一個 .md）
│   ├── 店家/         ← 各類場所（按摩、KTV、GoGo Bar 等）
│   ├── 地點/         ← 城市、地區、街道（47 個）
│   ├── 概念/         ← 術語、行話、概念（每個一個 .md）
│   ├── 來源/         ← 集數摘要頁、PDF 分析頁
│   └── Log.md        ← 每次操作的記錄
├── tools/
│   ├── ingest_ollama.py         ← Step1：逐字稿 → 來源/ 頁
│   ├── enrich_contributors.py   ← Step2：補投稿者/來賓/主持人 → 人物/
│   ├── enrich_concepts.py       ← Step3：術語 → 概念/；店家 → 店家/；地點 → 地點/
│   ├── enrich_places.py         ← Step4：補地點 ## 特色（待補充 → Ollama 生成）
│   ├── merge_aliases.py         ← Step5：合併別名、修正連結
│   ├── update_index.py          ← Step7：自動生成 Wiki/索引.md（含連結驗證）
│   ├── enrich_concept_defs.py   ← 選用：更新概念定義（累積多集後跑）
│   ├── migrate_to_chinese_dirs.py ← 一次性遷移腳本（已執行，保留備用）
│   └── check_links.py           ← 連結品質驗證（選用）
└── CLAUDE.md         ← 你現在讀的這份
```

---

## 核心工作流程

### 指令：`開始` / `START`（主要入口 SOP）
當用戶說「開始」或「START」時，依序執行：

**Step 1 — Ollama 處理 Raw/**
執行以下 bash 指令，讓 Ollama gemma4 批量處理所有逐字稿：
```bash
python -X utf8 tools/ingest_ollama.py
```
- 自動掃描 `Raw/` 下所有子資料夾（排除 `claude/` 和 `processed/`）
- 每集選最佳版本（_ver > _draft > _talk > _摘要）
- 輸出：`Wiki/來源/` 頁面（基本摘要、店家、妹子點評）
- 處理完移到 `Raw/processed/`

**Step 2 — 補充投稿者 / 來賓 / 主持人**
```bash
python -X utf8 tools/enrich_contributors.py
```
- 讀逐字稿 + Sources 頁，讓 Ollama 提取三類人的故事和知識點
- 在 Sources 頁新增「來賓分享」「投稿者故事」「主持人觀點」段落
- 建立 / 更新每個人的 `Wiki/人物/ 或 Wiki/店家/ 或 Wiki/地點/` 頁面（跨集累積）

**Step 3 — 展開術語、店家、地點交叉連結**
```bash
python -X utf8 tools/enrich_concepts.py
```
- 必須在 Step 2 之後跑，確保 Source 頁已被 contributors 豐富再讀取
- 從 Sources 頁提取術語/店家/地點，建立或更新對應 Wiki 頁面
- 自動套用別名正規化（`CONCEPT_ALIAS_MAP`），防止重複頁面

**Step 4 — 補充地點特色**
```bash
python -X utf8 tools/enrich_places.py
```
- 對 `## 特色` 還是「待補充」的地點頁，從來源頁收集資料讓 Ollama 生成描述
- 只處理尚未補充的頁面，不會覆蓋已有內容

**Step 5 — 合併別名、修正連結**
```bash
python -X utf8 tools/merge_aliases.py
```
- 掃描全庫連結，套用 `ALIAS_MAP` 修正常見筆誤與同義詞
- 把重複 Entity 頁合併到正規名

**Step 6 — Claude 處理 Raw/claude/**
親自讀取 `Raw/claude/` 裡的所有檔案：
- `.pdf` — 分段讀取，提取重要資訊
- `.xlsx` / `.csv` — 解讀欄位、分析數據
- `.md` / `.txt` — 需要深度推理或跨文件連結的內容
- 為每個檔案建立 `Wiki/來源/` 頁面，提取 Concepts 和 Entities

**Step 7 — 更新索引和 Log**
```bash
python -X utf8 tools/update_index.py
```
- 自動從檔案系統計算真實數字，驗證代表性連結，輸出 `Wiki/索引.md`
- 在 `Wiki/Log.md` 記錄這次處理了什麼

---

### 指令：`fix` / `補救`（一次性資料補救）
當用戶說「fix」「補救」「執行補救流程」時執行：

> 這個指令是用來修補過去腳本 bug 造成的歷史資料缺口，不是日常流程。
> 執行前先讀 HANDOVER.md 的 🔴 區塊，確認目前需要做哪些步驟。

**Step 1 — 確認前置任務完成**
檢查是否還有 Source 頁缺 `## 主持人觀點`：
```bash
python3 -c "
import sys; sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
missing = [f.stem for f in Path('Wiki/來源').glob('肥宅老司機-S3EP*.md')
           if '## 主持人觀點' not in f.read_text(encoding='utf-8')]
print(f'缺主持人觀點：{missing}' if missing else '全部齊全')
"
```
有缺就補：`python -X utf8 tools/enrich_contributors.py --ep S3EPxxx`

**Step 2 — 全庫重跑 enrich_concepts**
```bash
del Wiki\concepts_processed.json
python -X utf8 tools/enrich_concepts.py
```

**Step 3 — 補充地點特色**
```bash
python -X utf8 tools/enrich_places.py
```

**Step 4 — 更新概念定義**
```bash
python -X utf8 tools/enrich_concept_defs.py
```

**Step 5 — 整理連結**
```bash
python -X utf8 tools/merge_aliases.py
```

**Step 6 — 更新索引和 Log**
```bash
python -X utf8 tools/update_index.py
```
- 在 `Wiki/Log.md` 記錄補救完成

---

### 指令：`ingest`（處理新文章）
當用戶說「處理 Raw」「ingest」「消化新文章」時執行：

1. 遞迴掃描 `Raw/` 資料夾及所有子資料夾，找出所有未處理的文件（支援 .md、.txt、.pdf）
   - 子資料夾名稱可當作「主題分類」標籤，記錄在 Sources 頁的 metadata 裡
   - 例如 `Raw/科技/文章.md` → Sources 頁標記 **分類：科技**
2. 對每篇文章 / PDF：
   - PDF 直接用 Read 工具讀取，超過 10 頁的 PDF 分段讀（每次最多 20 頁）
   - 在 `Wiki/來源/` 建立來源摘要頁（格式見下方）
   - 提取重要概念 → 新增或更新 `Wiki/概念/` 頁面
   - 提取人物、組織、產品 → 新增或更新 `Wiki/人物/ 或 Wiki/店家/ 或 Wiki/地點/` 頁面
   - 在各頁面之間建立 `[[雙向連結]]`
3. 執行 `python -X utf8 tools/update_index.py` 更新索引
4. 在 `Wiki/Log.md` 記錄這次處理了什麼
5. 把處理完的原始文件移到 `Raw/processed/`（沒有就建立）

### 指令：`ask`（回答問題）
當用戶問任何問題時：

1. 先讀 `Wiki/索引.md` 確認相關頁面在哪裡（由 `update_index.py` 自動維護，數字可信）
2. 讀相關的 Concepts / Entities / Sources 頁面
3. 綜合多篇來源回答，並標註「根據 [[頁面名稱]]」
4. 如果發現知識不足，主動說明缺口在哪

### 指令：`health`（健康檢查）
當用戶說「健康檢查」「check」時：

1. 掃描所有 Wiki 頁面
2. 找出：孤立頁面（沒有任何連結）、空的概念、矛盾的描述
3. 列出建議補充的主題
4. 不要自動修改，只報告

### 指令：`gap`（補充缺口）
當用戶說「補充缺口」「fill gap」時：

1. 先執行 `health` 找出缺口
2. 針對每個缺口，搜尋相關資料（用 WebSearch）
3. 把找到的資料整理成新的 Concepts 或 Sources 頁
4. 更新 Index

---

## 頁面格式規範

### 來源頁（Wiki/來源/文章標題.md）
```markdown
# [文章標題]

**來源**：[URL 或檔名]
**日期**：[處理日期]
**作者**：[作者名，連結到 Entities]

## 摘要
[100-200 字的核心觀點]

## 關鍵概念
- [[概念A]] — 本文的用法說明
- [[概念B]] — 本文的用法說明

## 重要引用
> [值得保留的原文段落]

## 相關來源
- [[其他相關文章]]
```

### 概念頁（Wiki/概念/概念名稱.md）
```markdown
# [概念名稱]

## 定義
[清楚的定義，用白話說]

## 出現在
- [[來源文章A]] — 在這篇裡的意思是...
- [[來源文章B]] — 在這篇裡的意思是...

## 相關概念
- [[概念X]]：因為...所以相關
- [[概念Y]]：對比關係

## 延伸問題
- [這個概念還沒被回答的問題，作為知識缺口標記]
```

### 人物／店家／地點頁（Wiki/人物/ 或 Wiki/店家/ 或 Wiki/地點/名字.md）
```markdown
# [人名 / 組織名]

**類型**：人物 / 組織 / 產品
**領域**：[主要活躍領域]

## 簡介
[2-3 句話介紹]

## 主要觀點 / 貢獻
- [觀點一]（來自 [[來源]]）
- [觀點二]（來自 [[來源]]）

## 相關人物
- [[人物A]]：關係說明
```

---

## 索引格式（Wiki/索引.md）
```markdown
# 知識庫索引

**最後更新**：[日期]
**來源數量**：[數字]
**概念數量**：[數字]
**人物數量**：[數字]
**店家數量**：[數字]
**地點數量**：[數字]

## 概念目錄
- [[概念A]] — 一句話說明

## 人物 / 組織目錄
- [[人名A]] — 身份說明

## 來源目錄
- [[文章標題A]] — 作者，主題

## 知識缺口（待補充）
- [ ] 主題X — 目前缺少這方面的資料
```

---

## 重要原則
- **每次操作後必須更新 索引.md**，這是整個系統的核心
- **用 [[雙括號]] 建立連結**，讓 Obsidian 的圖譜能顯示關係
- **支援格式**：.md、.txt、.pdf（PDF 直接讀，不需轉檔）
- **不要修改 Raw/ 裡的原始檔案內容**，只移動位置
- **Log.md 用時間戳記錄**，讓用戶能追蹤歷史
- 回答問題時優先用知識庫裡的內容，超出範圍才用外部搜尋
