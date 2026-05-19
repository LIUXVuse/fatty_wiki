"""
generate_category_indexes.py
掃描 Wiki/ 各類別目錄，自動生成分類索引 MD 檔。

輸出位置：Wiki/來源/
  - 肥宅老司機-人物索引.md
  - 肥宅老司機-地點索引.md
  - 肥宅老司機-店家索引.md
  - 肥宅老司機-概念索引.md
"""

import sys
import re
from pathlib import Path
from datetime import date
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

ROOT   = Path(__file__).parent.parent
WIKI   = ROOT / "Wiki"
OUTPUT = WIKI / "來源"
TODAY  = date.today().strftime("%Y-%m-%d")


def read_field(text: str, field: str) -> str:
    """抓 **field**：value 格式的欄位"""
    m = re.search(rf"\*\*{re.escape(field)}\*\*[：:]\s*(.+)", text)
    return m.group(1).strip() if m else ""


def first_section_line(text: str, section: str) -> str:
    """抓某個 ## section 的第一行非空內容"""
    m = re.search(rf"## {re.escape(section)}\n+(.*?)(?:\n\n|\n##|$)", text, re.DOTALL)
    if not m:
        return ""
    lines = [l.strip() for l in m.group(1).splitlines() if l.strip()]
    if not lines:
        return ""
    # 去掉 markdown 表格、bullet 符號、wiki 連結等
    line = lines[0]
    line = re.sub(r"^\|.*", "", line)          # 表格行
    line = re.sub(r"^[-*]\s*", "", line)       # bullet
    line = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", line)  # [[X]] → X
    line = re.sub(r"^\s*\|.*", "", line)       # 剩餘表格
    return line.strip()[:80]                   # 最多 80 字


# ─────────────────────────────────────────────
# 1. 人物索引
# ─────────────────────────────────────────────
def generate_people():
    src = WIKI / "人物"
    files = sorted(src.glob("*.md"))

    groups = defaultdict(list)
    for f in files:
        text = f.read_text(encoding="utf-8")
        kind = read_field(text, "類型") or "其他"
        alias = read_field(text, "別名")
        note = first_section_line(text, "觀點累積") or first_section_line(text, "簡介") or ""
        groups[kind].append((f.stem, alias, note))

    # 分組排序：主持人 > 來賓 > 投稿者 > 其他
    order = ["主持人", "來賓", "投稿者", "其他"]
    all_kinds = order + [k for k in sorted(groups) if k not in order]

    lines = [
        f"# 肥宅老司機 - 人物索引",
        f"",
        f"> 快速導航：[[索引]] | [[肥宅老司機-集數索引]]",
        f"",
        f"**更新日期**：{TODAY}　**總人物數**：{len(files)}",
        f"",
        f"---",
        f"",
    ]
    for kind in all_kinds:
        if kind not in groups:
            continue
        entries = sorted(groups[kind], key=lambda x: x[0])
        lines.append(f"## {kind}（{len(entries)} 人）")
        lines.append(f"")
        lines.append(f"| 人物 | 別名 | 備註 |")
        lines.append(f"|------|------|------|")
        for name, alias, note in entries:
            lines.append(f"| [[{name}]] | {alias} | {note} |")
        lines.append(f"")

    lines += [
        "---",
        "",
        "## 相關連結",
        "- [[索引]] — 知識庫完整目錄",
        "- [[肥宅老司機-集數索引]] — 完整集數標題 + 嘉賓索引",
    ]

    out = OUTPUT / "肥宅老司機-人物索引.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 人物索引：{len(files)} 人 → {out.name}")


# ─────────────────────────────────────────────
# 2. 地點索引
# ─────────────────────────────────────────────
def generate_places():
    src = WIKI / "地點"
    files = sorted(src.glob("*.md"))

    groups = defaultdict(list)
    for f in files:
        text = f.read_text(encoding="utf-8")
        country = read_field(text, "國家") or read_field(text, "地區") or "其他"
        feat = first_section_line(text, "特色") or ""
        groups[country].append((f.stem, feat))

    lines = [
        f"# 肥宅老司機 - 地點索引",
        f"",
        f"> 快速導航：[[索引]] | [[肥宅老司機-集數索引]]",
        f"",
        f"**更新日期**：{TODAY}　**總地點數**：{len(files)}",
        f"",
        f"---",
        f"",
    ]
    for country in sorted(groups):
        entries = sorted(groups[country], key=lambda x: x[0])
        lines.append(f"## {country}（{len(entries)} 個）")
        lines.append(f"")
        lines.append(f"| 地點 | 特色摘要 |")
        lines.append(f"|------|---------|")
        for name, feat in entries:
            lines.append(f"| [[{name}]] | {feat} |")
        lines.append(f"")

    lines += [
        "---",
        "",
        "## 相關連結",
        "- [[索引]] — 知識庫完整目錄（含地域導航）",
        "- [[肥宅老司機-集數索引]] — 完整集數標題索引",
    ]

    out = OUTPUT / "肥宅老司機-地點索引.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 地點索引：{len(files)} 個 → {out.name}")


# ─────────────────────────────────────────────
# 3. 店家索引
# ─────────────────────────────────────────────
def generate_shops():
    src = WIKI / "店家"
    files = sorted(src.glob("*.md"))

    groups = defaultdict(list)
    for f in files:
        text = f.read_text(encoding="utf-8")
        location = read_field(text, "地點") or "未知地點"
        svc = read_field(text, "服務類型") or ""
        note = first_section_line(text, "評價與特色") or first_section_line(text, "費用") or ""
        groups[location].append((f.stem, svc, note))

    lines = [
        f"# 肥宅老司機 - 店家索引",
        f"",
        f"> 快速導航：[[索引]] | [[肥宅老司機-集數索引]]",
        f"",
        f"**更新日期**：{TODAY}　**總店家數**：{len(files)}",
        f"",
        f"---",
        f"",
    ]
    for loc in sorted(groups):
        entries = sorted(groups[loc], key=lambda x: x[0])
        lines.append(f"## {loc}（{len(entries)} 家）")
        lines.append(f"")
        lines.append(f"| 店家 | 服務類型 | 評價摘要 |")
        lines.append(f"|------|---------|---------|")
        for name, svc, note in entries:
            lines.append(f"| [[{name}]] | {svc} | {note} |")
        lines.append(f"")

    lines += [
        "---",
        "",
        "## 相關連結",
        "- [[索引]] — 知識庫完整目錄",
        "- [[肥宅老司機-集數索引]] — 完整集數標題索引",
    ]

    out = OUTPUT / "肥宅老司機-店家索引.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 店家索引：{len(files)} 家 → {out.name}")


# ─────────────────────────────────────────────
# 4. 概念索引
# ─────────────────────────────────────────────
def generate_concepts():
    src = WIKI / "概念"
    files = sorted(src.glob("*.md"))

    groups = defaultdict(list)
    for f in files:
        text = f.read_text(encoding="utf-8")
        kind = read_field(text, "類型") or "其他"
        defn = first_section_line(text, "定義") or ""
        groups[kind].append((f.stem, defn))

    # 常見類型排序
    order = ["術語", "行為", "概念", "服務", "場所", "其他"]
    all_kinds = order + [k for k in sorted(groups) if k not in order]

    lines = [
        f"# 肥宅老司機 - 概念索引",
        f"",
        f"> 快速導航：[[索引]] | [[肥宅老司機-集數索引]]",
        f"",
        f"**更新日期**：{TODAY}　**總概念數**：{len(files)}",
        f"",
        f"---",
        f"",
    ]
    for kind in all_kinds:
        if kind not in groups:
            continue
        entries = sorted(groups[kind], key=lambda x: x[0])
        lines.append(f"## {kind}（{len(entries)} 個）")
        lines.append(f"")
        lines.append(f"| 概念 | 定義摘要 |")
        lines.append(f"|------|---------|")
        for name, defn in entries:
            lines.append(f"| [[{name}]] | {defn} |")
        lines.append(f"")

    lines += [
        "---",
        "",
        "## 相關連結",
        "- [[索引]] — 知識庫完整目錄",
        "- [[肥宅老司機-集數索引]] — 完整集數標題索引",
    ]

    out = OUTPUT / "肥宅老司機-概念索引.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 概念索引：{len(files)} 個 → {out.name}")


# ─────────────────────────────────────────────
if __name__ == "__main__":
    print(f"=== generate_category_indexes.py ({TODAY}) ===")
    generate_people()
    generate_places()
    generate_shops()
    generate_concepts()
    print("\n全部完成。記得跑 update_index.py 更新主索引連結。")
