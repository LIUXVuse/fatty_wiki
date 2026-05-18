# check_links.py
# 驗證 Concepts 的「出現集數」連結是否真的在 Sources 內文中出現
# 輸出：suspicious_links.md（可疑配對清單）

import os
import re
from pathlib import Path

WIKI_ROOT = Path(__file__).parent.parent / "Wiki"
CONCEPTS_DIR = WIKI_ROOT / "Concepts"
SOURCES_DIR = WIKI_ROOT / "Sources"
ENTITIES_DIR = WIKI_ROOT / "Entities"
WIKI_CONCEPTS_DIR = WIKI_ROOT / "Concepts"
OUTPUT_FILE = WIKI_ROOT / "suspicious_links.md"

# 與 enrich_concepts.py 保持同步的別名表
# 格式：{原始寫法: 正規化後的 Concept 頁名}
CONCEPT_ALIAS_MAP = {
    # 豆干厝系列（同一台語詞的不同記音）
    "豆干":     "豆乾",
    "豆乾厝":   "豆干厝",
    "豆乾措":   "豆干厝",
    "豆干措":   "豆干厝",
    "豆乾錯":   "豆干厝",
    "豆干錯":   "豆干厝",
    "豆乾鎖":   "豆干厝",
    "豆干座":   "豆干厝",
    "豆干戳":   "豆干厝",
    # 字形差異
    "黒服":     "黑服",
    # 全形/半形
    "日Ｋ":     "日K",
    # 同義詞
    "回轉壽司": "迴轉壽司",
    "龍津":     "龍津殿",
    "龍筋按摩": "龍筋",
    "青蛙抬腿": "青蛙腿",
    "青蛙踢":   "青蛙腿",
    "走勝不走心": "走腎不走心",  # 走勝是走腎的錯字
    # 服務等級系統（個別數字 → 統一頁面）
    "0.3":      "0.3_0.5_1",
    "0.5":      "0.3_0.5_1",
    "1.0":      "0.3_0.5_1",
    # 括號命名 → 主概念頁
    "GoGo Bar (如 Rainbow 3, Nana Plaza)": "GoGo Bar",
    "GoGo Bar (如Rainbow 3, Nana Plaza)":  "GoGo Bar",
    "KTV酒店":           "KTV",
    "KTV 酒店 (一般)":   "KTV",
    "外圍 (獨立)":       "外圍",
    "定點 (酒店)":       "定點",
    "脫衣舞酒吧 (Strip Club)": "脫衣舞酒吧",
    # 空格差異
    "裸 K":     "裸K",
    "混 K":     "混K",
    "Bar-fine": "Bar Fine",
    "Club 模式": "Club模式",
}

# 反向對應：正規名 → [所有原始別名]
REVERSE_ALIAS: dict[str, list[str]] = {}
for alias, canonical in CONCEPT_ALIAS_MAP.items():
    REVERSE_ALIAS.setdefault(canonical, []).append(alias)


def extract_sources_from_concept(content: str) -> list[str]:
    """從 Concept 頁抓出「出現集數」區塊裡每行的第一個 [[連結]]（即 Source 參照）"""
    section = re.search(r"## 出現集數(.*?)(?=^##|\Z)", content, re.DOTALL | re.MULTILINE)
    if not section:
        return []
    sources = []
    for line in section.group(1).splitlines():
        match = re.search(r"\[\[([^\]]+)\]\]", line)
        if match:
            sources.append(match.group(1))
    return sources


def load_source_content(source_name: str) -> str | None:
    """載入 Sources 頁內文，找不到回傳 None"""
    path = SOURCES_DIR / f"{source_name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def is_known_entity_or_concept(name: str) -> bool:
    """檢查是否為已知的 Entity 或 Concept（非 Source）"""
    return (ENTITIES_DIR / f"{name}.md").exists() or (WIKI_CONCEPTS_DIR / f"{name}.md").exists()


def concept_mentioned(concept_name: str, source_content: str) -> bool:
    """
    概念名稱是否出現在來源內文。
    處理三種情況：
    1. 直接比對（含去空格正規化）
    2. 複合名稱（_ 或 與 分隔）→ 任一部分出現即可
    3. 別名比對（從 REVERSE_ALIAS 取得所有原始別名）
    """
    content_lower = source_content.lower()

    # 1. 直接比對
    if concept_name.lower() in content_lower:
        return True

    # 1b. 去空格比對（處理 混K vs 混 K 等空格差異）
    if concept_name.replace(" ", "").lower() in content_lower.replace(" ", ""):
        return True

    # 2. 複合名稱拆解
    parts = []
    if "_" in concept_name:
        parts = [p.strip() for p in concept_name.split("_") if p.strip()]
    elif "與" in concept_name:
        parts = [p.strip() for p in concept_name.split("與") if p.strip()]
    if parts and any(p.lower() in content_lower for p in parts):
        return True

    # 3. 別名比對
    aliases = REVERSE_ALIAS.get(concept_name, [])
    if aliases and any(a.lower() in content_lower for a in aliases):
        return True

    return False


def main():
    suspicious = []
    not_found_sources = []

    concept_files = sorted(CONCEPTS_DIR.glob("*.md"))
    print(f"掃描 {len(concept_files)} 個 Concept 頁面...")

    for concept_path in concept_files:
        concept_name = concept_path.stem
        content = concept_path.read_text(encoding="utf-8")
        sources = extract_sources_from_concept(content)

        for source in sources:
            source_content = load_source_content(source)
            if source_content is None:
                if not is_known_entity_or_concept(source):
                    not_found_sources.append((concept_name, source))
                continue
            if not concept_mentioned(concept_name, source_content):
                suspicious.append((concept_name, source))

    # 輸出報告
    from datetime import date
    today = date.today().isoformat()
    lines = ["# 連結品質報告\n", f"掃描日期：{today}\n\n"]

    lines.append(f"## 可疑配對（概念名稱未出現在來源內文）\n\n")
    lines.append(f"共 {len(suspicious)} 筆\n\n")
    lines.append("| 概念 | 來源 |\n|------|------|\n")
    for concept, source in suspicious:
        lines.append(f"| {concept} | {source} |\n")

    lines.append(f"\n## 連結目標不存在的 Sources\n\n")
    lines.append(f"共 {len(not_found_sources)} 筆\n\n")
    lines.append("| 概念 | 找不到的 Source |\n|------|----------------|\n")
    for concept, source in not_found_sources:
        lines.append(f"| {concept} | {source} |\n")

    OUTPUT_FILE.write_text("".join(lines), encoding="utf-8")
    print(f"\n完成！報告已寫入 {OUTPUT_FILE}")
    print(f"可疑配對：{len(suspicious)} 筆")
    print(f"連結不存在：{len(not_found_sources)} 筆")


if __name__ == "__main__":
    main()
