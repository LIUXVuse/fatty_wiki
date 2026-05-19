## ✅ 本次完成（2026-05-19，最新）

### 關生 txt/PDF 來源頁完整性核查 + 斷連結修復

**來源頁對照表修正**（關生.md 和 2025年5月芭提雅探店指南.md 用了錯誤連結名）：
| 錯誤連結 | 正確連結 |
|---------|---------|
| `[[2025年3月曼谷和芭提雅]]` | `[[2025年曼谷完整探店指南]]` |
| `[[2025年3月越南胡志明]]` | `[[2025年越南胡志明探店指南]]` |
| `[[2025年5月曼谷]]` | `[[2025年曼谷極少眾暗黑玩法]]` |
| `[[Walking Street Gogobar]]` | `[[Walking Street]] GoGo Bar` |

**來源頁完整性確認**（全部通過）：
- `2025年曼谷完整探店指南.md` ✓
- `2025年越南胡志明探店指南.md` ✓
- `2025年曼谷極少眾暗黑玩法.md` ✓
- `2025年5月芭提雅探店指南.md` ✓（修正 5 個虛構事件連結）
- `胡志明攻略2025年3月PDF版.md` ✓
- `胡志明探店指南2026.md` ✓

**新建頁面**：
- `概念/人妖.md`、`概念/俄羅斯吧.md`、`概念/越南夜生活.md`
- `店家/T-Ded99.md`、`店家/Danika Massage.md`、`店家/Paikanyai Bar.md`

**索引更新**：概念 669 → 672，店家 528 → 530

---

## ✅ 本次完成（2026-05-19）

### 六巷地點頁修復 + 人物頁斷連結掃描

**六巷（芭提雅 Soi 6）**：
- 原本只有 `概念/6巷.md`（位置放錯），且 `[[六巷]]` 連結斷掉
- 建立 `地點/六巷.md`（正確分類），加 ALIAS_MAP `"六巷": ["6巷"]`
- 跑 `merge_aliases.py --group 六巷`：合併舊概念頁、8 個檔案連結自動修正
- 慣例：`六巷` 不加前綴 = 芭提雅六巷；是拉差若有內容另建 `是拉差六巷.md`

**人物頁斷連結掃描（python 全庫掃描結果）**：
- `力書.md`：`[[肥宅老司機 S3EP3]]` → `[[肥宅老司機-S3EP3]]` 已修；移除不存在的 `[[台灣半套店]]`、`[[性愛技巧]]`
- `老馬哥.md`：無斷連結（格式已正確）
- `肥宅老司機.md`：`[[莞式服務]]` 頁面尚不存在，留待補建
- `關生.md`：`[[2025年3月曼谷和芭提雅]]`、`[[2025年3月越南胡志明]]`、`[[2025年5月曼谷]]` 三個來源頁不存在 — 這是前向連結，Raw 素材 ingest 後會自動補上（不是 bug）

**索引更新**：地點 59 → 60（加了六巷）；概念 670 → 669（6巷 合入六巷）

---

## ✅ 本次完成（2026-05-19）

### 肥宅老司機.md 全面重寫（Claude 親寫）

- 修正主持人：「未具名」→ [[老濕]]、[[老雞]]（正確兩人）
- 高頻來賓從 3 人擴充到 10 人，每人附出現集數
- 地域表補全：台、日、泰、越、菲、印尼、中、歐、美洲 9 大區、26 個城市
- 主題專輯 23 個、旅遊指南 6 篇全部條列
- 核心概念分場所類型 / 行話 / 特殊主題三區
- 集數範圍更新：「180+ 集」→ S3EP1～S3EP263（257 集），缺集明確標出

---

## ✅ 本次完成（2026-05-19）

### 建立 12 個缺漏地點頁 + 補地點特色 + 更新索引

**新建地點頁**（全部帶正確上層地點 / 國家欄位）：
- 台灣：中壢（桃園）、苗栗、萬華區（台北）、中和（新北）、新竹、三重（新北）、林森北（台北）
- 日本：沖繩
- 德國：法蘭克福
- 墨西哥：Tijuana
- 加拿大：多倫多
- 美國：拉斯維加斯

**sync_episode_refs.py**：13 個頁面，補入 90 筆集數。

**enrich_places.py**：13 個地點補完「## 特色」段落（含舊的清遠）。

**索引更新**：
- `generate_category_indexes.py` 重生成地點索引（47 → 59）
- `update_index.py` 更新主索引

地點數：47 → 59。

---

## ✅ 本次完成（2026-05-19，前次）

### 流水線前瞻修復 + sync_episode_refs + 全庫斷連結修正 + merge_aliases 強化

- **ingest_ollama.py**：別名在入口即修正，不再產生孤立別名頁
- **enrich_contributors.py**：is_fully_processed() 加嚴防止 Ollama 輸出失敗永久跳過
- **enrich_concepts.py**：新增 `--force-ep` 旗標強制重跑指定集
- **merge_aliases.py**：新增 merge_definitions()；32 個錯字頁改名；~25 組新別名
- **tools/sync_episode_refs.py**（新腳本）：163 頁面補 1099 筆集數，支援階層傳遞
- 全庫斷連結修正：99 檔案 144 條

---

## 🔴 下一個對話要先做

### Step 1：全庫斷連結掃描（⚠️ 仍有待處理）
本次用 python 全庫掃描（非 check_links.py，它只掃英文路徑），結果：
- **人物/ 4 個檔案 8 條斷連結** — 本次修了 力書.md，其餘見「已知問題」
- **其他目錄（地點/概念/店家/來源）298 個檔案 1506 條** — 主要在來源頁，量大需批量處理

待補建的概念頁（高頻出現但無頁面）：
- `莞式服務` — 源自東莞的服務形式（`肥宅老司機.md` 有引用）
- `人妖` — 泰國 Ladyboy（`概念/6巷.md` 和 `地點/芭提雅.md` 有引用）
- `安全旅遊` — 旅遊警示概念（`地點/芭提雅.md` 引用）

### Step 2：新集數 ingest（有新逐字稿時）
```bash
python -X utf8 tools/ingest_ollama.py
python -X utf8 tools/enrich_contributors.py
python -X utf8 tools/enrich_concepts.py
python -X utf8 tools/enrich_places.py
python -X utf8 tools/merge_aliases.py
python -X utf8 tools/sync_episode_refs.py
python -X utf8 tools/generate_category_indexes.py
python -X utf8 tools/update_index.py
```
⚠️ 記得手動補 `Wiki/來源/肥宅老司機-集數索引.md`（Step 7.5）

---

## ⚠️ 已知問題 / 注意事項

- **斷連結**：建 12 個地點頁前有 1128 個，建完後未重新統計，下次可跑 check_links.py 確認
- `enrich_places.py` 不會更新已填地點的特色，若要重生成需改回「（待補充）」
- `enrich_contributors.py` 的相似名字警告寫進 merge_suggestions.txt，無自動驗證流程
- PG島 無對應地點頁（索引已改為純文字）
- 缺失集號：S3EP20、153、167、174、198、211

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
| 地點 | 59 |

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
