"""
update_index.py — 更新 Wiki/索引.md 的自動區塊

只更新 <!-- AUTO-*-START --> ... <!-- AUTO-*-END --> 之間的內容。
地域導航、概念說明、嘉賓分析等人工維護段落不會被覆蓋。

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

# ── 統計 ─────────────────────────────────────────────────────────────
src_dir     = WIKI / "來源"
concept_dir = WIKI / "概念"
person_dir  = WIKI / "人物"
shop_dir    = WIKI / "店家"
place_dir   = WIKI / "地點"

def count_md(folder): return len(list(folder.glob("*.md")))

n_concept = count_md(concept_dir)
n_person  = count_md(person_dir)
n_shop    = count_md(shop_dir)
n_place   = count_md(place_dir)

ep_files = []
for f in src_dir.glob("肥宅老司機-S3EP*.md"):
    m = re.search(r"S3EP(\d+)", f.stem)
    if m:
        ep_files.append(int(m.group(1)))
ep_files.sort()
n_ep    = len(ep_files)
ep_max  = max(ep_files) if ep_files else 0
ep_missing = sorted(set(range(1, ep_max + 1)) - set(ep_files))

other_src = [f for f in src_dir.glob("*.md") if "S3EP" not in f.stem]
n_other   = len(other_src)
n_total   = n_ep + n_other

guide_files  = sorted([f for f in other_src if not f.stem.startswith("肥宅老司機")])
theme_files  = sorted([f for f in other_src if f.stem.startswith("肥宅老司機") and f.stem != "肥宅老司機-集數索引"])

# ── 各 AUTO 區塊內容 ──────────────────────────────────────────────────
today = date.today().strftime("%Y-%m-%d")

STATS = f"""\
**最後更新**：{today}
**來源數量**：{n_total}（{n_ep} 集 S3EP，最高 S3EP{ep_max}；{n_other} 個主題/指南）
**概念數量**：{n_concept}
**人物數量**：{n_person}
**店家數量**：{n_shop}
**地點數量**：{n_place}
**Entities 合計**：{n_person + n_shop + n_place}
**缺失集號**：{ep_missing}（共 {len(ep_missing)} 集）"""

GUIDES = "\n".join(f"- [[{f.stem}]]" for f in guide_files)

THEMES = "\n".join(f"- [[{f.stem}]]" for f in theme_files) + \
         "\n- [[肥宅老司機-集數索引]] ← 完整集數導航在這裡"

# ── 替換 marker 區塊 ──────────────────────────────────────────────────
def replace_block(text: str, tag: str, new_content: str) -> str:
    pattern = rf"(<!-- {tag}-START -->\n).*?(<!-- {tag}-END -->)"
    replacement = rf"\g<1>{new_content}\n\2"
    result, count = re.subn(pattern, replacement, text, flags=re.DOTALL)
    if count == 0:
        print(f"  ⚠️  找不到 {tag} marker，跳過")
    return result

text = OUT.read_text(encoding="utf-8")
text = replace_block(text, "AUTO-STATS",  STATS)
text = replace_block(text, "AUTO-GUIDES", GUIDES)
text = replace_block(text, "AUTO-THEMES", THEMES)
OUT.write_text(text, encoding="utf-8")

print(f"✅ 索引已更新：{OUT}")
print(f"   來源 {n_total} | 概念 {n_concept} | 人物 {n_person} | 店家 {n_shop} | 地點 {n_place}")
if ep_missing:
    print(f"   缺失集號：{ep_missing}")
