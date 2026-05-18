"""
update_index.py — 自動生成 Wiki/索引.md

從實際檔案系統讀取統計數字與檔案清單，產生正確的索引頁。
不依賴 Ollama，純 Python，隨時可跑。

用法：
    python -X utf8 tools/update_index.py
"""

import sys
import re
from pathlib import Path
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

WIKI = Path("Wiki")
OUT  = WIKI / "索引.md"

# ── 1. 計算各類別檔案數 ──────────────────────────────────────────────
def count_md(folder: Path) -> int:
    return len(list(folder.glob("*.md")))

src_dir     = WIKI / "來源"
concept_dir = WIKI / "概念"
person_dir  = WIKI / "人物"
shop_dir    = WIKI / "店家"
place_dir   = WIKI / "地點"

n_concept = count_md(concept_dir)
n_person  = count_md(person_dir)
n_shop    = count_md(shop_dir)
n_place   = count_md(place_dir)

# 集數統計
ep_files = sorted(
    [f for f in src_dir.glob("肥宅老司機-S3EP*.md")],
    key=lambda f: int(re.sub(r"[^\d]", "", f.stem.replace("肥宅老司機-S3EP", "")))
    if re.sub(r"[^\d]", "", f.stem.replace("肥宅老司機-S3EP", "")) else 0
)
n_ep = len(ep_files)
ep_max = max(
    int(f.stem.replace("肥宅老司機-S3EP", ""))
    for f in ep_files
) if ep_files else 0
ep_nums  = {int(f.stem.replace("肥宅老司機-S3EP", "")) for f in ep_files}
ep_missing = sorted(set(range(1, ep_max + 1)) - ep_nums)

# 非集數來源（旅遊指南 + 主題專輯）
other_src = sorted(
    [f for f in src_dir.glob("*.md") if "S3EP" not in f.stem],
    key=lambda f: f.stem
)
n_other_src = len(other_src)
n_src_total = n_ep + n_other_src

# ── 2. 分類非集數來源 ───────────────────────────────────────────────
guide_files   = [f for f in other_src if not f.stem.startswith("肥宅老司機")]
fatman_themes = [f for f in other_src if f.stem.startswith("肥宅老司機")]

# ── 3. 已知概念代表（固定列表，改這裡就改索引）──────────────────────
CONCEPT_SAMPLES = [
    ("泰浴",     "概念", "泰國傳統服務場所，芭提雅/曼谷，2800-33000 銖"),
    ("GoGo Bar", "店家", "步行街高端酒吧，位於芭提雅與曼谷"),
    ("6巷",      "概念", "芭提雅半開放式紅燈區，經濟實惠"),
    ("日K",      "概念", "曼谷 Thaniya 日 K 一條街"),
    ("泡泡浴",   "概念", "日本傳統風俗業，3-8 萬日幣"),
    ("KTV",      "店家", "卡拉 OK 酒吧，越南/泰國/東莞應酬核心"),
    ("日按",     "概念", "日式按摩，東南亞常見服務類型"),
    ("樓鳳",     "概念", "台灣站路女產業"),
    ("台幹",     "概念", "在海外工作的台灣人"),
    ("外圍",     "概念", "兼職性工作者"),
    ("外送茶",   "店家", "電話/網路預約外送服務"),
    ("應酬文化", "概念", "東南亞商務娛樂文化"),
]

PERSON_SAMPLES = [
    ("肥宅老司機", "人物", "播客節目主持人"),
    ("老馬哥",     "人物", "日本泡泡浴文化專家，常駐嘉賓"),
    ("力書",       "人物", "性愛知識專家，BDSM 講師"),
    ("波尼",       "人物", "旅遊指南作者（芭提雅/曼谷/胡志明）"),
    ("關生",       "人物", "旅遊指南共同作者"),
]

# ── 4. 驗證連結是否存在 ──────────────────────────────────────────────
def file_exists(name: str) -> bool:
    for d in [concept_dir, person_dir, shop_dir, place_dir, src_dir]:
        if (d / f"{name}.md").exists():
            return True
    return False

broken = []
for name, cat, _ in CONCEPT_SAMPLES + PERSON_SAMPLES:
    if not file_exists(name):
        broken.append(f"[[{name}]] ({cat})")

# ── 5. 組合索引文字 ──────────────────────────────────────────────────
lines = []
today = date.today().strftime("%Y-%m-%d")

lines.append(f"# 知識庫索引\n")
lines.append(f"**最後更新**：{today}  ")
lines.append(f"**來源數量**：{n_src_total}（{n_ep} 集 S3EP，最高 S3EP{ep_max}；{n_other_src} 個主題/指南）  ")
lines.append(f"**概念數量**：{n_concept}  ")
lines.append(f"**人物數量**：{n_person}  ")
lines.append(f"**店家數量**：{n_shop}  ")
lines.append(f"**地點數量**：{n_place}  ")
lines.append(f"**Entities 合計**：{n_person + n_shop + n_place}  ")
if ep_missing:
    lines.append(f"**缺失集號**：{ep_missing}（共 {len(ep_missing)} 集）  ")
lines.append("")

# 概念
lines.append("---\n")
lines.append("## 概念目錄（代表性條目）\n")
for name, _, desc in CONCEPT_SAMPLES:
    lines.append(f"- [[{name}]] — {desc}")
lines.append(f"\n> 完整 {n_concept} 個概念詳見 `Wiki/概念/` 資料夾\n")

# 人物
lines.append("---\n")
lines.append("## 人物目錄（代表性條目）\n")
for name, _, desc in PERSON_SAMPLES:
    lines.append(f"- [[{name}]] — {desc}")
lines.append(f"\n> 完整 {n_person} 人詳見 `Wiki/人物/` 資料夾\n")

# 來源 - 旅遊指南
lines.append("---\n")
lines.append("## 來源目錄\n")
lines.append("### 旅遊指南\n")
for f in guide_files:
    lines.append(f"- [[{f.stem}]]")

# 來源 - 主題專輯
lines.append("\n### 肥宅老司機主題專輯\n")
for f in fatman_themes:
    if f.stem != "肥宅老司機-集數索引":
        lines.append(f"- [[{f.stem}]]")
lines.append(f"- [[肥宅老司機-集數索引]] — Season 3 全集清單\n")

# 來源 - 集數
lines.append("### 播客集數（S3EP）\n")
lines.append(f"- S3EP1 ~ S3EP{ep_max}，共 {n_ep} 個檔案")
if ep_missing:
    lines.append(f"- 缺失集號：{ep_missing}")
lines.append(f"- 詳見 [[肥宅老司機-集數索引]]\n")

# 知識缺口
lines.append("---\n")
lines.append("## 知識缺口（待補充）\n")
lines.append("- [ ] 嘉賓背景介紹（老馬哥、力書的個人經歷）")
lines.append("- [ ] 人妖識別與安全警示（詳細版）")
lines.append("- [ ] 日本風俗業的法律和社會背景")
lines.append("- [ ] 台灣性工作產業的歷史與現況")
lines.append("- [ ] BDSM 的安全實踐指南")
lines.append("- [ ] 越南與泰國產業對比分析")
lines.append("- [ ] 越南的樹枝店文化")
lines.append("- [ ] 各地 KTV 應酬文化比較")
lines.append("- [ ] enrich_concept_defs.py 待補概念定義（約 140 個）\n")

# 系統說明
lines.append("---\n")
lines.append("## 系統說明\n")
lines.append(f"- **概念**：術語、行話（`Wiki/概念/`，{n_concept} 個）")
lines.append(f"- **人物**：投稿者、來賓、主持人（`Wiki/人物/`，{n_person} 人）")
lines.append(f"- **店家**：各類場所（`Wiki/店家/`，{n_shop} 家）")
lines.append(f"- **地點**：城市、地區（`Wiki/地點/`，{n_place} 個）")
lines.append(f"- **來源**：集數摘要、PDF、旅遊指南（`Wiki/來源/`，{n_src_total} 篇）\n")
lines.append("詳見 CLAUDE.md 的工作流程說明。\n")

# ── 6. 斷連警告 ──────────────────────────────────────────────────────
if broken:
    lines.append("---\n")
    lines.append("## ⚠️ 索引內斷連（需修復）\n")
    for b in broken:
        lines.append(f"- {b}")
    lines.append("")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"✅ 索引已更新：{OUT}")
print(f"   來源 {n_src_total} | 概念 {n_concept} | 人物 {n_person} | 店家 {n_shop} | 地點 {n_place}")
if ep_missing:
    print(f"   缺失集號：{ep_missing}")
if broken:
    print(f"⚠️  斷連 {len(broken)} 個：{broken}")
else:
    print("   所有代表性連結驗證通過")
