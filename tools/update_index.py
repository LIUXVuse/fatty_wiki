"""
update_index.py — 更新 Wiki/索引.md 的自動區塊

只更新 <!-- AUTO-*-START --> ... <!-- AUTO-*-END --> 之間的內容。
地域導航、概念說明、嘉賓分析等人工維護段落不會被覆蓋。

用法：
    python -X utf8 tools/update_index.py
"""

import sys
import re
import json
import urllib.request
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
NOTABLE_GUESTS = ["老馬哥", "詹姆士", "力書"]  # 主題代表性來賓（即使集數少也顯示）

# 描述存在 guest_descs.json，新來賓自動用 Ollama 生成
DESCS_FILE = Path("tools/guest_descs.json")

def load_descs():
    if DESCS_FILE.exists():
        return json.loads(DESCS_FILE.read_text(encoding="utf-8"))
    return {}

def save_descs(d):
    DESCS_FILE.write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
    )

def ollama_desc(name, person_file):
    """從人物頁的集數標題讓 Ollama 生成一句話描述，失敗回傳空字串。"""
    try:
        content = person_file.read_text(encoding="utf-8")
        # 取有標題的集數行（「— xxx」部分）
        titles = re.findall(r"—\s+(.+)", content)[:10]
        if not titles:
            return ""
        titles_str = "、".join(t.strip() for t in titles)
        prompt = (
            f"以下是播客來賓「{name}」出場時的集數標題摘要：\n{titles_str}\n\n"
            f"根據這些標題，用繁體中文寫一句話（15字以內）說明這位來賓的專長或常見話題。"
            f"只輸出那句話，不要標點以外的其他文字。"
        )
        payload = json.dumps({"model": "gemma3:27b", "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip().strip("。")
    except Exception:
        return ""

def format_eps(eps, max_show=6):
    ep_str = "、".join(f"S3EP{e}" for e in eps[:max_show])
    if len(eps) > max_show:
        ep_str += f"…共 {len(eps)} 集"
    return ep_str

person_eps  = {}
person_file = {}
for f in person_dir.glob("*.md"):
    if f.stem in SKIP_PERSONS:
        continue
    content = f.read_text(encoding="utf-8")
    eps = sorted(set(int(e) for e in re.findall(r"\[\[肥宅老司機-S3EP(\d+)\]\]", content)))
    if eps:
        person_eps[f.stem]  = eps
        person_file[f.stem] = f

ranked     = sorted(person_eps.items(), key=lambda x: -len(x[1]))
need_desc  = {name for name, eps in ranked if len(eps) >= MIN_EPISODES} | set(NOTABLE_GUESTS)
need_desc &= person_eps.keys()

guest_descs = load_descs()
new_descs   = {}
for name in need_desc:
    if name not in guest_descs:
        print(f"  🤖 Ollama 生成來賓描述：{name}…", end=" ", flush=True)
        desc = ollama_desc(name, person_file[name])
        guest_descs[name] = desc
        new_descs[name]   = desc
        print(desc or "(空)")
if new_descs:
    save_descs(guest_descs)
    print(f"  💾 已儲存 {len(new_descs)} 筆新描述 → {DESCS_FILE}")

top_guests = [(name, eps) for name, eps in ranked if len(eps) >= MIN_EPISODES][:TOP_N]

def guest_line(name, eps):
    desc   = guest_descs.get(name, "")
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
