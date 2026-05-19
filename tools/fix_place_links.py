# -*- coding: utf-8 -*-
"""
fix_place_links.py
修正 Wiki/地點/ 下所有 MD 檔案的問題：
1. Wiki 連結中 `/` → `_` 的轉換（對應店家目錄的實際檔名）
2. 去除 ## 提到的店家 段落中的重複項目
"""

import re
import sys
from pathlib import Path

WIKI_ROOT = Path("Wiki")
PLACES_DIR = WIKI_ROOT / "地點"

# 收集所有 Wiki 頁面的檔名（不含 .md），用於連結驗證
def get_all_page_names():
    names = set()
    for subdir in ["店家", "人物", "概念", "地點", "來源"]:
        d = WIKI_ROOT / subdir
        if d.exists():
            for f in d.glob("*.md"):
                names.add(f.stem)
    return names

def try_fix_slash_link(link_text, all_pages):
    """
    嘗試把 link_text 裡的 / 換成 _ ，確認換完後有對應頁面存在才回傳新名稱。
    link_text: 不含 [[ ]] 的純文字
    """
    if "/" not in link_text:
        return None

    # 兩種替換方式：有空格 " / " → " _ "，無空格 "/" → "_"
    candidate_space = link_text.replace(" / ", " _ ")
    candidate_nospace = link_text.replace("/", "_")

    if candidate_space in all_pages:
        return candidate_space
    if candidate_nospace in all_pages:
        return candidate_nospace
    # 混合情況（如 "如環保/極品" 無空格，但其他部分有空格）
    candidate_mixed = re.sub(r'\s*/\s*', ' _ ', link_text)
    if candidate_mixed in all_pages:
        return candidate_mixed
    candidate_mixed2 = re.sub(r'/', '_', link_text)
    if candidate_mixed2 in all_pages:
        return candidate_mixed2

    return None  # 找不到對應頁面，不自動改

def fix_links_in_text(text, all_pages):
    """掃描文字中所有 [[...]] 連結，嘗試修正含 / 的連結"""
    changes = []

    def replace_link(m):
        inner = m.group(1)  # [[ ]] 內的文字（可能含 | 的 alias）
        # 處理 [[目標|顯示名]] 格式
        if "|" in inner:
            target, alias = inner.split("|", 1)
        else:
            target, alias = inner, None

        if "/" not in target:
            return m.group(0)  # 沒有 /，不動

        fixed = try_fix_slash_link(target, all_pages)
        if fixed and fixed != target:
            changes.append((target, fixed))
            if alias:
                return f"[[{fixed}|{alias}]]"
            return f"[[{fixed}]]"
        return m.group(0)  # 找不到對應，不動

    new_text = re.sub(r'\[\[([^\[\]]+)\]\]', replace_link, text)
    return new_text, changes

def deduplicate_section(text, section_header="## 提到的店家"):
    """去除指定 section 下的重複 bullet 項目（保留第一次出現）"""
    lines = text.splitlines(keepends=True)
    in_section = False
    seen = set()
    removed = []
    result = []

    for line in lines:
        stripped = line.rstrip()
        # 偵測目標 section 開始
        if stripped == section_header:
            in_section = True
            result.append(line)
            seen.clear()
            continue
        # 偵測另一個 ## section 開始（離開目標 section）
        if in_section and stripped.startswith("## ") and stripped != section_header:
            in_section = False

        if in_section and stripped.startswith("- [["):
            key = stripped.strip()
            if key in seen:
                removed.append(key)
                continue  # 跳過重複
            seen.add(key)

        result.append(line)

    return "".join(result), removed

def process_file(md_path, all_pages, dry_run=False):
    text = md_path.read_text(encoding="utf-8")
    original = text

    # Step 1: 修正連結中的 /
    text, link_changes = fix_links_in_text(text, all_pages)

    # Step 2: 去重複
    text, removed_dupes = deduplicate_section(text, "## 提到的店家")

    if text == original:
        return False, [], []

    if not dry_run:
        md_path.write_text(text, encoding="utf-8")

    return True, link_changes, removed_dupes

def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("[DRY RUN] 不會實際寫入檔案")

    all_pages = get_all_page_names()
    print(f"已載入 {len(all_pages)} 個 Wiki 頁面名稱\n")

    total_changed = 0
    unresolved_links = {}  # 記錄無法自動修正的 / 連結

    for md_path in sorted(PLACES_DIR.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")

        # 先收集無法解析的連結（便於最後報告）
        for m in re.finditer(r'\[\[([^\[\]]+)\]\]', text):
            inner = m.group(1)
            target = inner.split("|")[0]
            if "/" in target:
                fixed = try_fix_slash_link(target, all_pages)
                if not fixed:
                    unresolved_links.setdefault(md_path.name, []).append(target)

        changed, link_changes, removed_dupes = process_file(md_path, all_pages, dry_run)

        if changed:
            total_changed += 1
            print(f"✅ {md_path.name}")
            for old, new in link_changes:
                print(f"   🔗 [[{old}]] → [[{new}]]")
            for dupe in removed_dupes:
                print(f"   🗑️  移除重複：{dupe}")

    print(f"\n共修改 {total_changed} 個檔案")

    if unresolved_links:
        print("\n⚠️  以下連結含 / 但找不到對應頁面，需人工確認：")
        for fname, links in unresolved_links.items():
            print(f"\n  {fname}:")
            for link in links:
                print(f"    - [[{link}]]")

if __name__ == "__main__":
    main()
