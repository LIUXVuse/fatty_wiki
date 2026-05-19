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

### Step 1：掃描剩餘斷連結（可選）
```bash
python -X utf8 tools/check_links.py
```
確認 1128 個斷連結中還剩多少（本次建了 12 個地點頁後應大幅減少）。

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
