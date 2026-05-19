"""
sync_episode_refs.py — 同步所有 Entity 頁面的「出現集數」

問題：enrich_concepts.py 只在處理來源頁時更新 Entity，
若 Ollama 把「印尼」提取成「雅加達」（子城市），
印尼.md 的「出現集數」就不會收到那集。

本腳本做三件事：
1. 掃描所有來源頁的 [[連結]]，建立 entity → [來源頁] 的反向索引
2. 對每個地點/人物/店家/概念頁，補上缺漏的「出現集數」
3. 階層傳遞：城市集數也傳到上層國家（依 **國家** 欄位）

用法：
  python tools/sync_episode_refs.py           # 執行修正
  python tools/sync_episode_refs.py --dry-run # 只列出會改什麼
  python tools/sync_episode_refs.py --dir 地點 # 只跑指定目錄
"""

import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE     = Path(__file__).parent.parent
WIKI     = BASE / "Wiki"
SOURCES  = WIKI / "來源"
DIRS     = {
    "地點": WIKI / "地點",
    "人物": WIKI / "人物",
    "店家": WIKI / "店家",
    "概念": WIKI / "概念",
}

# ── 工具 ──────────────────────────────────────────────────────────

def ep_num(ref: str) -> int:
    """從 [[肥宅老司機-S3EP42]] 提取集號整數"""
    m = re.search(r'EP(\d+)', ref, re.IGNORECASE)
    return int(m.group(1)) if m else 9999


def parse_ep_section(text: str) -> list[str]:
    """抽出 ## 出現集數 區塊的所有集數連結"""
    m = re.search(r'## 出現集數\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if not m:
        return []
    return re.findall(r'\[\[([^\]]+)\]\]', m.group(1))


def update_ep_section(text: str, new_refs: list[str]) -> str:
    """把 new_refs 插入 ## 出現集數，排序去重，保留原有描述行"""
    m = re.search(r'(## 出現集數\n)(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if not m:
        # 沒有出現集數區塊，加在末尾
        bullets = "\n".join(f"- [[{r}]]" for r in sorted(new_refs, key=ep_num))
        return text.rstrip() + f"\n\n## 出現集數\n{bullets}\n"

    existing_block = m.group(2)
    # 已存在的帶描述行保留不動（以集號為 key）
    existing_lines: dict[int, str] = {}
    for line in existing_block.splitlines():
        if not line.strip().startswith("-"):
            continue
        refs = re.findall(r'\[\[([^\]|]+)\]\]', line)
        if refs:
            key = ep_num(refs[0])
            existing_lines[key] = line

    # 新增缺漏的裸連結（只加，不覆蓋有描述的）
    for ref in new_refs:
        k = ep_num(ref)
        if k not in existing_lines:
            existing_lines[k] = f"- [[{ref}]]"

    sorted_lines = "\n".join(v for _, v in sorted(existing_lines.items()))
    new_block = m.group(1) + sorted_lines + "\n"
    return text[:m.start()] + new_block + text[m.end():]


# ── 建立城市→國家階層 ─────────────────────────────────────────────

def build_hierarchy() -> dict[str, str]:
    """從地點頁的 **國家** 欄位建立 {城市: 國家} 對照"""
    hierarchy: dict[str, str] = {}
    places_dir = DIRS["地點"]
    for f in places_dir.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        n = re.search(r'\*\*國家\*\*：(.+)', text)
        if not n:
            continue
        raw = n.group(1).strip()
        # 「老撾（寮國）」→ 取括號內
        m = re.search(r'（(.+)）', raw)
        country = m.group(1) if m else raw
        city = f.stem
        if city != country and (places_dir / f"{country}.md").exists():
            hierarchy[city] = country
    return hierarchy


# ── 建立反向索引：entity → [來源頁 stem] ──────────────────────────

def build_backlink_index() -> dict[str, set[str]]:
    """掃所有來源頁的 [[連結]]，建立 {被連結名稱: {來源頁stem, ...}}"""
    index: dict[str, set[str]] = defaultdict(set)
    for f in SOURCES.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        for link in re.findall(r'\[\[([^\]|]+)\]\]', text):
            link = link.strip()
            index[link].add(f.stem)
    return index


# ── 核心：更新單一 Entity 頁 ───────────────────────────────────────

def sync_entity(
    entity_path: Path,
    backlinks: set[str],   # 直接連結到本頁的來源頁 stem
    dry_run: bool,
) -> int:
    """回傳新增集數數量"""
    text = entity_path.read_text(encoding="utf-8")
    existing = set(parse_ep_section(text))
    existing_keys = {ep_num(r) for r in existing}

    # 只考慮「集數型來源頁」（S3EPxxx 格式）
    new_refs = [
        stem for stem in backlinks
        if re.search(r'S3EP\d+', stem, re.IGNORECASE)
        and ep_num(stem) not in existing_keys
    ]
    if not new_refs:
        return 0

    if dry_run:
        print(f"  [dry] {entity_path.parent.name}/{entity_path.stem}: "
              f"補 {len(new_refs)} 集 → {sorted(new_refs, key=ep_num)[:5]}")
        return len(new_refs)

    updated = update_ep_section(text, new_refs)
    entity_path.write_text(updated, encoding="utf-8")
    return len(new_refs)


# ── 主程式 ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="同步 Entity 頁面的出現集數")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dir", default="", help="只跑指定目錄（地點/人物/店家/概念）")
    args = parser.parse_args()

    if args.dry_run:
        print("🔍 DRY RUN — 不修改檔案\n")

    print("建立反向連結索引…")
    backlinks = build_backlink_index()
    print(f"  共索引 {len(backlinks)} 個 entity 的來源連結")

    print("建立地點階層…")
    hierarchy = build_hierarchy()  # {城市: 國家}
    print(f"  {len(hierarchy)} 組城市→國家對應")

    # 階層傳遞：把城市的反向連結也加進對應國家
    country_extra: dict[str, set[str]] = defaultdict(set)
    for city, country in hierarchy.items():
        if city in backlinks:
            country_extra[country].update(backlinks[city])

    target_dirs = {args.dir: DIRS[args.dir]} if args.dir in DIRS else DIRS

    total_files = total_eps = 0
    for dir_name, dir_path in target_dirs.items():
        print(f"\n── {dir_name}/ ──")
        dir_files = dir_eps = 0
        for entity_file in sorted(dir_path.glob("*.md")):
            name = entity_file.stem
            # 直接連結 + 階層傳遞（只對地點適用）
            refs = set(backlinks.get(name, set()))
            if dir_name == "地點" and name in country_extra:
                refs.update(country_extra[name])

            added = sync_entity(entity_file, refs, args.dry_run)
            if added:
                dir_files += 1
                dir_eps += added
                if not args.dry_run:
                    print(f"  ✅ {name}: +{added} 集")

        print(f"  → {dir_name}/：{dir_files} 個頁面，新增 {dir_eps} 筆集數")
        total_files += dir_files
        total_eps += dir_eps

    print(f"\n🎉 完成：共 {total_files} 個頁面，新增 {total_eps} 筆集數")
    if not args.dry_run and total_eps > 0:
        print("建議跑一次 update_index.py 更新索引數字")


if __name__ == "__main__":
    main()
