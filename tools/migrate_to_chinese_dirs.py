"""
migrate_to_chinese_dirs.py — 一次性遷移：把 Entities/Concepts/Sources 改為中文資料夾
用法：
  python tools/migrate_to_chinese_dirs.py --dry-run   # 預覽，不實際移動
  python tools/migrate_to_chinese_dirs.py             # 執行遷移

新結構：
  Wiki/人物/  ← 投稿者、來賓、主持人、個人創作者
  Wiki/店家/  ← 各類成人場所
  Wiki/地點/  ← 城市、地區、街道
  Wiki/概念/  ← 原 Concepts/
  Wiki/來源/  ← 原 Sources/
"""

import re
import sys
import shutil
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE     = Path(__file__).parent.parent
WIKI     = BASE / "Wiki"

OLD_ENTITIES = WIKI / "Entities"
OLD_CONCEPTS = WIKI / "Concepts"
OLD_SOURCES  = WIKI / "Sources"

NEW_PEOPLE  = WIKI / "人物"
NEW_VENUES  = WIKI / "店家"
NEW_PLACES  = WIKI / "地點"
NEW_CONCEPTS = WIKI / "概念"
NEW_SOURCES  = WIKI / "來源"


def classify_entity(path: Path) -> Path:
    """根據檔案內容的 **類型** 欄位決定目標資料夾"""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return NEW_PEOPLE  # 讀不到就預設人物

    m = re.search(r'\*\*類型\*\*：(.+)', text)
    if not m:
        return NEW_PEOPLE

    t = m.group(1).strip()

    if "店家" in t:
        return NEW_VENUES
    if any(k in t for k in ["城市", "地點", "地區"]):
        return NEW_PLACES
    # 其餘（聽眾投稿者/來賓/主持人/人物/個人創作者/組織/平台/播客…）→ 人物
    return NEW_PEOPLE


def migrate(dry_run: bool):
    # ── 建立新資料夾 ─────────────────────────────────────────
    for d in [NEW_PEOPLE, NEW_VENUES, NEW_PLACES, NEW_CONCEPTS, NEW_SOURCES]:
        if not dry_run:
            d.mkdir(parents=True, exist_ok=True)
        else:
            print(f"[dry] mkdir {d.relative_to(BASE)}")

    counts = {"人物": 0, "店家": 0, "地點": 0, "概念": 0, "來源": 0, "衝突": 0}

    # ── 遷移 Entities/ → 人物/ 店家/ 地點/ ──────────────────
    print("\n=== Entities → 人物 / 店家 / 地點 ===")
    for f in sorted(OLD_ENTITIES.glob("*.md")):
        target_dir = classify_entity(f)
        dst = target_dir / f.name
        label = target_dir.name

        if dst.exists():
            print(f"  ⚠️  衝突（目標已存在）：{f.name} → {label}/")
            counts["衝突"] += 1
            continue

        print(f"  {f.name} → {label}/")
        if not dry_run:
            shutil.move(str(f), str(dst))
        counts[label] += 1

    # ── 遷移 Concepts/ → 概念/ ──────────────────────────────
    print("\n=== Concepts → 概念 ===")
    for f in sorted(OLD_CONCEPTS.glob("*.md")):
        dst = NEW_CONCEPTS / f.name
        if dst.exists():
            print(f"  ⚠️  衝突：{f.name}")
            counts["衝突"] += 1
            continue
        print(f"  {f.name} → 概念/")
        if not dry_run:
            shutil.move(str(f), str(dst))
        counts["概念"] += 1

    # ── 遷移 Sources/ → 來源/ ───────────────────────────────
    print("\n=== Sources → 來源 ===")
    for f in sorted(OLD_SOURCES.glob("*.md")):
        dst = NEW_SOURCES / f.name
        if dst.exists():
            print(f"  ⚠️  衝突：{f.name}")
            counts["衝突"] += 1
            continue
        print(f"  {f.name} → 來源/")
        if not dry_run:
            shutil.move(str(f), str(dst))
        counts["來源"] += 1

    # ── 移除空的舊資料夾 ────────────────────────────────────
    if not dry_run:
        for old_dir in [OLD_ENTITIES, OLD_CONCEPTS, OLD_SOURCES]:
            remaining = list(old_dir.glob("*"))
            if not remaining:
                old_dir.rmdir()
                print(f"\n🗑️  已移除空資料夾：{old_dir.relative_to(BASE)}/")
            else:
                print(f"\n⚠️  {old_dir.name}/ 還有 {len(remaining)} 個檔案未移動，保留資料夾")

    print("\n=== 統計 ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}：{v} 個")
    if dry_run:
        print("\n（dry-run 模式，未實際移動）")
    else:
        print("\n✅ 遷移完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(args.dry_run)
