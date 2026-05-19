## ✅ 本次完成（2026-05-19）

### 流水線前瞻修復 — 新逐字稿不再需要手動補救

**commit cf8aaf2**：4 files changed

#### 1. ingest_ollama.py — Ollama 別名在入口即修正
`build_canonical_map()` 現在同時載入 ALIAS_MAP + CONCEPT_ALIAS_MAP。
Ollama 輸出 `[[龍精]]`、`[[親工]]`、`[[長中]]` 等音近字時，Source 頁建立當下就自動修正。
不再等到 merge_aliases 才發現，不再產生孤立別名頁。

#### 2. enrich_contributors.py — is_fully_processed() 加嚴
標題存在但段落空白（Ollama 無輸出）→ 仍視為未完整，下次重試。
防止 Ollama 輸出失敗時永久跳過某集。

#### 3. enrich_concepts.py — 新增 --force-ep 旗標
```bash
python -X utf8 tools/enrich_concepts.py --force-ep S3EP263
```
強制重跑指定集並從 processed.json 移除，補救時不再需要手改 JSON。

#### 4. merge_aliases.py — 長鍾補 "長中" 別名
確保 `[[長中]]` 能被 canonical_map 在入口修正到 `[[長鍾]]`。

---

## ✅ 本次完成（2026-05-19）

### sync_episode_refs.py — 全庫 Entity 出現集數補漏

**根本原因**：enrich_concepts.py 以 Ollama 提取 entity，粒度不一致
（如提取「雅加達」但未提取「印尼」），導致國家頁不收錄子城市集數。

**新腳本 `tools/sync_episode_refs.py`**：
- 反向掃描所有來源頁的 [[連結]] 建立 entity 反向索引
- 補漏各頁「## 出現集數」中缺漏的集數引用
- 階層傳遞：城市集數自動傳到上層國家（依 **國家** 欄位）
- 本次修正：163 個頁面，補入 1099 筆集數（含 印尼.md 收到 EP263）

**CLAUDE.md SOP 新增 Step 5.5**（每次 Step 3-5 後必跑）

---

## ✅ 本次完成（2026-05-19）

### 全庫斷連結修正（改名/合併遺漏）
- 掃描 來源/概念/人物/店家/地點 全部 .md，修正 99 個檔案、144 條連結
- 另修正複合詞 1 個檔案、2 條（如 `[[龍經店]]→[[龍筋店]]`）
- `update_wiki_links()` 強化：合併時自動推導衍生複合詞後綴

---

## ✅ 本次完成（2026-05-19）

### merge_aliases.py 定義融合強化 + 32 個錯字概念頁改名
- 新增 `merge_definitions()`：Ollama 融合主名+別名定義
- 32 個錯字概念頁批次改名（五套→無套、管事服務→莞式 等）
- ~25 組 ALIAS_MAP 新增別名對

---

## 🔴 下一個對話要先做

### Step 1：建立缺漏的地點頁（高優先）

全庫掃出 **1128 個連結指向不存在頁面**，其中高頻未建地點頁：

| 地點 | 出現次數 | 備註 |
|------|---------|------|
| 中壢 | 30 | 台灣桃園市 |
| 苗栗 | 15 | 台灣 |
| 萬華區 | 15 | 台北市 |
| 中和 | 13 | 新北市 |
| 新竹 | 13 | 台灣 |
| 三重 | 12 | 新北市 |
| 林森北 | 12 | 台北市 |
| 沖繩 | 17 | 日本 |
| 法蘭克福 | 17 | 德國 |
| Tijuana | 19 | 墨西哥 |
| 多倫多 | 16 | 加拿大 |
| 拉斯維加斯 | 9 | 美國 |

**做法**：可用 `enrich_concepts.py` 的地點建立邏輯批量建，或逐一手動建。
建完後跑一次 `sync_episode_refs.py` 讓集數自動填入。

### Step 2：補充地點特色
```bash
python -X utf8 tools/enrich_places.py
```

---

## ⚠️ 已知問題 / 注意事項

- **1128 個連結指向不存在頁面**（主要是未建地點頁的城市）
- `enrich_places.py` 不會自動更新已填地點的特色，若要重生成需改回「（待補充）」
- `enrich_contributors.py` 的相似名字警告寫進 merge_suggestions.txt，無自動驗證流程
- PG島 無對應地點頁（索引已改為純文字）

---

## 快速指令

| 指令 | 效果 |
|------|------|
| `python -X utf8 tools/ingest_ollama.py` | Step1：逐字稿 → 來源頁（別名在入口即修正）|
| `python -X utf8 tools/enrich_contributors.py` | Step2：補人物頁 |
| `python -X utf8 tools/enrich_concepts.py` | Step3：補概念/店家/地點頁 |
| `python -X utf8 tools/enrich_concepts.py --force-ep S3EPxxx` | 強制重跑指定集（補救用）|
| `python -X utf8 tools/enrich_places.py` | Step4：補地點特色 |
| `python -X utf8 tools/merge_aliases.py` | Step5：合併別名、修正連結 |
| `python -X utf8 tools/sync_episode_refs.py` | Step5.5：同步 Entity 出現集數 + 階層傳遞 |
| `python -X utf8 tools/generate_category_indexes.py` | Step7：重新生成 4 個分類索引 |
| ⚠️ 手動補 `Wiki/來源/肥宅老司機-集數索引.md` | Step7.5：新集數補進集數索引 |
| `python -X utf8 tools/update_index.py` | Step8：更新主索引數字 |

---

## 知識庫現況（2026-05-19）

| 類型 | 數量 |
|------|------|
| 來源 | 290（257 集 S3EP + 33 主題/指南）|
| 概念 | 670 |
| 人物 | 341 |
| 店家 | 529 |
| 地點 | 47 |

---

## Ollama 別名規律備忘

1. 英中混用：Scott ↔ 史考特、James ↔ 詹姆士
2. 截斷：詹姆士 → 詹姆
3. 同音字：喇賽/喇塞/啦塞/拉塞
4. 錯別字：小瓢蟲/小飄蟲、永登埔/永登浦
5. 台/臺異體：台灣/臺灣
6. 大陸/台灣用詞：老撾 ↔ 寮國、萬象 ↔ 永珍
7. 括號變體：Cherry ↔ Cherry(櫻桃)
8. 尊稱後綴：老馬 ↔ 老馬哥（同一人）⚠️ 但老張 ≠ 老張哥（不同人）
9. 音近誤寫：老基 = 老雞、K-FUN = K房、小書桶 = 小書童
10. 同店不同名：伊林龍筋 = 伊林農金店 = 一一老師龍筋按摩（已寫入 ALIAS_MAP）
11. 越南旗袍店：奧代/澳代 = 奧黛（áo dài）
12. 城市音近：芭達雅 = 芭提雅（Pattaya）
13. 術語誤字：口報 = 口爆；外國人料理 = 外國人料金
14. 概念合併：龍經 = 龍筋（已合併）
15. 主持人同音字：老師 = 老濕（已合併）
16. 複合詞衍生：龍經店 = 龍筋店（merge_aliases 自動處理後綴衍生）
17. ⭐ 新：Ollama 音近字現在在 ingest 入口就修正，不會再產生孤立別名頁
