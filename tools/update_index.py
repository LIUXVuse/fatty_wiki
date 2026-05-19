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

# ── 來賓出場統計 ──────────────────────────────────────────────────────
SKIP_PERSONS = {"肥宅老司機", "老濕", "老雞"}
TOP_N = 12          # 主要名單顯示人數
MIN_EPISODES = 5    # 自動納入門檻（集數）

# 描述由人工維護（只需改這裡），集數範圍自動計算
GUEST_DESCS = {
    "喇賽":    "按摩保養、台灣 / 泰國 / 菲律賓踩點",
    "老張":    "越南 / 日本探店",
    "克里斯":  "包養網、線上到線下操作",
    "藍甲蟲":  "包養文化、台灣夜生活",
    "小茜":    "外送茶工作者、約炮心得",
    "Beast":   "包養網、豆干厝",
    "比爾":    "歐洲 FKK、日本泡泡浴",
    "基德":    "不花錢獵色、3P 實戰",
    "老王":    "成人娛樂媒合生態",
    "小開":    "越南胡志明攻略",
    "康熙":    "台灣酒店文化",
    "小瓢蟲":  "情慾按摩、越南 KTV",
    "吉米":    "保養習慣、台灣夜生活",
    "Jay":     "東南亞酒吧互動",
    "Ken":     "台灣踩點",
    "老馬哥":  "日本泡泡浴文化專家",
    "詹姆士":  "美國 / 墨西哥性產業",
    "悠君":    "日本泡泡浴深度攻略",
    "力書":    "性愛知識、BDSM 講師",
    "小倩":    "外送茶工作者、直播",
}
# 主題代表性來賓（即使集數少也顯示在第二區塊）
NOTABLE_GUESTS = ["老馬哥", "詹姆士", "力書"]

def format_eps(eps, max_show=6):
    ep_str = "、".join(f"S3EP{e}" for e in eps[:max_show])
    if len(eps) > max_show:
        ep_str += f"…共 {len(eps)} 集"
    return ep_str

person_eps = {}
for f in person_dir.glob("*.md"):
    if f.stem in SKIP_PERSONS:
        continue
    content = f.read_text(encoding="utf-8")
    eps = sorted(set(int(e) for e in re.findall(r"\[\[肥宅老司機-S3EP(\d+)\]\]", content)))
    if eps:
        person_eps[f.stem] = eps

ranked = sorted(person_eps.items(), key=lambda x: -len(x[1]))
top_guests = [(name, eps) for name, eps in ranked if len(eps) >= MIN_EPISODES][:TOP_N]

def guest_line(name, eps):
    desc = GUEST_DESCS.get(name, "")
    ep_str = format_eps(eps)
    suffix = f" — {desc}（{ep_str}）" if desc else f"（{ep_str}）"
    return f"- **[[{name}]]**{suffix}"

guest_lines = ["依出場集數排序（全庫統計，主持人不列）：", ""]
guest_lines += [guest_line(name, eps) for name, eps in top_guests]

notable_lines = [
    guest_line(name, person_eps[name])
    for name in NOTABLE_GUESTS if name in person_eps
]
if notable_lines:
    guest_lines += ["", "主題代表性（出場雖少但專長獨特）："]
    guest_lines += notable_lines

GUESTS = "\n".join(guest_lines)

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

NAV = f"""\
| 我想找…             | 直接跳轉                        |
| ---------------- | --------------------------- |
| 集數標題 / 嘉賓 / 主題分類 | [[肥宅老司機-集數索引]]              |
| 人物（主持人、來賓、投稿者）   | [[肥宅老司機-人物索引]]（{n_person} 人）       |
| 地點（城市、地區、國家）     | [[肥宅老司機-地點索引]]（{n_place} 個）或下方地域導航 |
| 店家查詢（按城市分類）      | [[肥宅老司機-店家索引]]（{n_shop} 家）       |
| 術語 / 概念定義        | [[肥宅老司機-概念索引]]（{n_concept} 個）       |
| 旅遊指南 PDF         | 下方「旅遊指南」區塊                  |"""

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
text = replace_block(text, "AUTO-NAV",    NAV)
text = replace_block(text, "AUTO-GUESTS", GUESTS)
text = replace_block(text, "AUTO-GUIDES", GUIDES)
text = replace_block(text, "AUTO-THEMES", THEMES)
# 替換散落的硬編碼數字（不在 AUTO 區塊內的那些）
text = re.sub(r"完整 \d+ 個概念詳見", f"完整 {n_concept} 個概念詳見", text)
text = re.sub(r"完整 \d+ 人詳見", f"完整 {n_person} 人詳見", text)

OUT.write_text(text, encoding="utf-8")

print(f"✅ 索引已更新：{OUT}")
print(f"   來源 {n_total} | 概念 {n_concept} | 人物 {n_person} | 店家 {n_shop} | 地點 {n_place}")
if ep_missing:
    print(f"   缺失集號：{ep_missing}")
