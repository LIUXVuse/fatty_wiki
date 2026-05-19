#!/usr/bin/env python -u
# -*- coding: utf-8 -*-
"""
enrich_concepts.py — 從 Sources 頁提取術語、服務類型、店家、城市/地點，建立/更新 Wiki 頁面
用法：
  python -u tools/enrich_concepts.py            # 處理所有未處理的 Sources 頁
  python -u tools/enrich_concepts.py --test 5   # 只跑前 5 個未處理
  python -u tools/enrich_concepts.py --ep S3EP100  # 只跑指定集數
"""

import re
import sys
import json
import argparse
from pathlib import Path
from datetime import date

# ── 路徑設定 ────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent.parent
SOURCES_DIR  = BASE / "Wiki" / "來源"
CONCEPTS_DIR = BASE / "Wiki" / "概念"
VENUES_DIR   = BASE / "Wiki" / "店家"
PLACES_DIR   = BASE / "Wiki" / "地點"
PROCESSED_FILE = BASE / "Wiki" / "concepts_processed.json"

# ── 地點關鍵字 ───────────────────────────────────────────────────────────────
LOCATION_KEYWORDS = {
    "台灣", "台中", "台北", "高雄", "桃園", "台南", "新北", "基隆",
    "泰國", "曼谷", "芭提雅", "清邁", "普吉", "芭達雅",
    "越南", "胡志明", "河內", "峴港",
    "菲律賓", "天使城", "馬尼拉", "宿霧",
    "日本", "東京", "大阪", "名古屋", "福岡",
    "老撾", "永珍", "萬象", "寮國",
    "香港", "澳門", "新加坡", "馬來西亞", "吉隆坡",
    "中國", "上海", "東莞", "深圳", "廣州", "長平", "清遠", "廈門",
    "韓國", "首爾", "釜山",
    "印尼", "峇里島", "雅加達",
    "柬埔寨", "金邊", "暹粒",
    "緬甸", "仰光",
}

# 地點的國家對應
LOCATION_COUNTRY = {
    "台灣": "台灣", "台中": "台灣", "台北": "台灣", "高雄": "台灣",
    "桃園": "台灣", "台南": "台灣", "新北": "台灣", "基隆": "台灣",
    "泰國": "泰國", "曼谷": "泰國", "芭提雅": "泰國", "清邁": "泰國",
    "普吉": "泰國", "芭達雅": "泰國",
    "越南": "越南", "胡志明": "越南", "河內": "越南", "峴港": "越南",
    "菲律賓": "菲律賓", "天使城": "菲律賓", "馬尼拉": "菲律賓", "宿霧": "菲律賓",
    "日本": "日本", "東京": "日本", "大阪": "日本", "名古屋": "日本", "福岡": "日本",
    "老撾": "老撾（寮國）", "永珍": "老撾（寮國）", "萬象": "老撾（寮國）", "寮國": "老撾（寮國）",
    "香港": "香港", "澳門": "澳門", "新加坡": "新加坡",
    "馬來西亞": "馬來西亞", "吉隆坡": "馬來西亞",
    "中國": "中國", "上海": "中國", "東莞": "中國", "深圳": "中國",
    "廣州": "中國", "長平": "中國", "清遠": "中國", "廈門": "中國",
    "韓國": "韓國", "首爾": "韓國", "釜山": "韓國",
    "印尼": "印尼", "峇里島": "印尼", "雅加達": "印尼",
    "柬埔寨": "柬埔寨", "金邊": "柬埔寨", "暹粒": "柬埔寨",
    "緬甸": "緬甸", "仰光": "緬甸",
}

# 店家名稱過濾用詞（含這些詞就不是店名）
NOT_SHOP_WORDS = {"妹子", "阿姨", "小姐", "女孩", "女生", "姐姐", "妹妹", "嫂子",
                  "老婆", "太太", "媽媽", "姊姊", "妹", "姐", "嫂", "姑", "嬤"}

# ── Concept 別名正規化表 ─────────────────────────────────────────────────────
# Ollama 對同一口語詞常記音不一致，在這裡統一對應到正確檔名
# 格式：{Ollama 可能輸出的寫法: 正確的 Concepts 頁檔名}
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
    "黒服":     "黑服",       # 黒（日文字形）vs 黑
    # 全形/半形
    "日Ｋ":     "日K",        # 全形 K → 半形 K
    # 同義詞
    "回轉壽司": "迴轉壽司",
    "龍津":     "龍津殿",
    "龍筋按摩": "龍筋",
    "龍經":     "龍筋",   # 同音字
    "農金":     "龍筋",   # 同音字（伊林農金店的「農金」即龍筋）
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
    # 簡繁體差異
    "演员":     "演員",   # 簡體「员」→繁體「員」
}


# ── 工具函數 ─────────────────────────────────────────────────────────────────
def load_processed() -> list:
    if PROCESSED_FILE.exists():
        try:
            return json.loads(PROCESSED_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_processed(processed: list):
    PROCESSED_FILE.write_text(
        json.dumps(sorted(set(processed)), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_section(text: str, heading: str) -> str:
    """提取指定 ## 段落的內容（不含下一個 ## ）"""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def wiki_link(name: str) -> str:
    return f"[[{name}]]"


def is_valid_shop_name(name: str) -> bool:
    """過濾掉不是店名的字串"""
    name = name.strip()
    if len(name) < 2:
        return False
    for word in NOT_SHOP_WORDS:
        if word in name:
            return False
    # 過濾純地名
    if name in LOCATION_KEYWORDS:
        return False
    return True


def infer_service_type(feature: str) -> str:
    """從特色欄推斷服務類型"""
    feature_lower = feature.lower()
    mapping = [
        (["gogobar", "gogo bar", "歌歌吧", "GoGo"], "GoGo Bar"),
        (["按摩", "massage", "泰浴", "日按"], "按摩"),
        (["ktv", "k 房", "k房", "卡拉OK"], "KTV"),
        (["包養", "包養網"], "包養"),
        (["兵妹"], "兵妹"),
        (["外送茶", "外送"], "外送茶"),
        (["援交", "兼職"], "兼職/援交"),
    ]
    for keywords, label in mapping:
        for kw in keywords:
            if kw.lower() in feature_lower:
                return label
    return "成人娛樂"


# ── Parse 函數 ───────────────────────────────────────────────────────────────
def parse_terms(text: str, source_ep: str) -> list:
    """
    從 ## 術語與概念 提取術語
    支援兩種格式：
      [[術語]] — 解釋
      - [[術語]] — 解釋
    回傳 [{name, definition, source_ep}]
    """
    section = get_section(text, "術語與概念")
    if not section:
        return []

    results = []
    # 支援 "- [[name]] — def" 或 "[[name]] — def"
    # 用 [^\]]+ 防止跨越 ]] 捕捉（如 [[A]] / [[B]] — def 誤捕捉 A]] / [[B）
    pattern = r"^\s*-?\s*\[\[([^\]]+)\]\]\s*[—–\-]+\s*(.+)"
    for line in section.splitlines():
        m = re.match(pattern, line.strip())
        if m:
            name = m.group(1).strip()
            definition = m.group(2).strip()
            if name:
                results.append({
                    "name": name,
                    "definition": definition,
                    "source_ep": source_ep,
                })
    return results


def parse_shops(text: str, source_ep: str) -> list:
    """
    從 ## 店家與地點資訊 表格提取店家
    欄位：店名 | 地點/城市 | 費用 | 特色或評價 | 實用小技巧
    回傳 [{name, location, cost, feature, tips, source_ep}]
    """
    section = get_section(text, "店家與地點資訊")
    if not section:
        return []

    # 檢查是否有「本集未提及」之類的文字
    if "未提及" in section or "未有" in section:
        return []

    results = []
    for line in section.splitlines():
        line = line.strip()
        # 跳過 header 行和分隔行
        if not line.startswith("|"):
            continue
        if re.match(r"^\|\s*[-:]+\s*\|", line):
            continue
        if re.match(r"^\|\s*(店名|Name)\s*\|", line):
            continue

        # 分割欄位
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 2:
            continue

        name_raw = cols[0].strip()
        # 去除 wiki link 格式
        name = re.sub(r"\[\[(.+?)\]\]", r"\1", name_raw).strip()

        if not is_valid_shop_name(name):
            continue
        # 如果店名是地點關鍵字也跳過
        if name in LOCATION_KEYWORDS:
            continue

        location = cols[1].strip() if len(cols) > 1 else ""
        location = re.sub(r"\[\[(.+?)\]\]", r"\1", location).strip()

        cost = cols[2].strip() if len(cols) > 2 else ""
        feature = cols[3].strip() if len(cols) > 3 else ""
        tips = cols[4].strip() if len(cols) > 4 else ""

        # 去除空值或 "-"
        cost = "" if cost in ("-", "—", "–", "") else cost
        feature = "" if feature in ("-", "—", "–", "") else feature
        tips = "" if tips in ("-", "—", "–", "") else tips

        results.append({
            "name": name,
            "location": location,
            "cost": cost,
            "feature": feature,
            "tips": tips,
            "source_ep": source_ep,
        })
    return results


def parse_locations_from_mentions(text: str, source_ep: str) -> list:
    """
    從 ## 提到的人物與地點 提取地點
    格式：[[名字]]、[[名字]]、...
    回傳 [{name, source_ep}]
    """
    section = get_section(text, "提到的人物與地點")
    if not section:
        return []

    results = []
    all_links = re.findall(r"\[\[(.+?)\]\]", section)
    for name in all_links:
        name = name.strip()
        if name in LOCATION_KEYWORDS:
            results.append({"name": name, "source_ep": source_ep})
    return results


def extract_ep_name(filename: str) -> str:
    """從檔名提取集數名稱（不含 .md）"""
    return Path(filename).stem


# ── 頁面讀寫函數 ──────────────────────────────────────────────────────────────
def read_page(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def write_page(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_to_section(text: str, heading: str, new_line: str) -> str:
    """把 new_line 追加到指定段落末尾（在下一個 ## 之前），保持時間順序"""
    pattern = re.compile(
        rf"(## {re.escape(heading)}\n(?:(?!## ).*\n)*)",
        re.MULTILINE
    )
    m = pattern.search(text)
    if m:
        insert_pos = m.end()
        return text[:insert_pos].rstrip("\n") + f"\n{new_line}\n" + text[insert_pos:]
    return text + f"\n## {heading}\n{new_line}\n"


def page_has_ep(content: str, ep_name: str) -> bool:
    """檢查頁面是否已記錄此集數"""
    return f"[[{ep_name}]]" in content


# ── 建立/更新 Concepts 頁（術語） ────────────────────────────────────────────
def upsert_concept_page(term: dict, concept_type: str = "術語"):
    """
    term: {name, definition, source_ep}
    """
    name = CONCEPT_ALIAS_MAP.get(term["name"], term["name"])  # 正規化別名
    definition = term["definition"]
    source_ep = term["source_ep"]
    # sanitize：移除 Windows 路徑非法字元（/ \ : * ? " < > |）
    safe_name = re.sub(r'[/\\:*?"<>|]', '_', name).strip()
    if not safe_name:
        return
    path = CONCEPTS_DIR / f"{safe_name}.md"
    # name 保留原始顯示用（含 /），safe_name 只用於檔名
    existing = read_page(path)

    if not existing:
        # 新建頁面
        content = f"""# {name}

**類型**：{concept_type}

## 定義
{definition}

## 出現集數
- {wiki_link(source_ep)} — {definition}

## 相關概念
"""
        write_page(path, content)
        print(f"  [新建 Concept] {name}")
    else:
        # 追加到現有頁面
        if page_has_ep(existing, source_ep):
            return  # 已記錄此集，跳過

        updated = existing

        # 追加到「出現集數」段落末尾
        ep_entry = f"- {wiki_link(source_ep)} — {definition}"
        updated = append_to_section(updated, "出現集數", ep_entry)

        write_page(path, updated)
        print(f"  [更新 Concept] {name} ← {source_ep}")


# ── 建立/更新 店家/ 頁 ────────────────────────────────────────────────────────
def upsert_shop_page(shop: dict):
    """
    shop: {name, location, cost, feature, tips, source_ep}
    """
    name = shop["name"]
    location = shop["location"]
    cost = shop["cost"]
    feature = shop["feature"]
    tips = shop["tips"]
    source_ep = shop["source_ep"]
    service_type = infer_service_type(feature + " " + tips)

    safe_name = re.sub(r'[\\/:*?"<>|]', "_", name)
    path = VENUES_DIR / f"{safe_name}.md"
    existing = read_page(path)

    cost_row = f"| {cost} | {feature} | {wiki_link(source_ep)} |" if cost else ""

    if not existing:
        cost_section = ""
        if cost_row:
            cost_section = f"""
## 費用
| 費用 | 說明 | 來源 |
|------|------|------|
{cost_row}
"""
        content = f"""# {name}

**類型**：店家
**地點**：{location}
**服務類型**：{service_type}
{cost_section}
## 評價與特色
- {wiki_link(source_ep)}：{feature}{"　小技巧：" + tips if tips else ""}

## 出現集數
- {wiki_link(source_ep)}
"""
        write_page(path, content)
        print(f"  [新建 Entity/店家] {name}")
    else:
        if page_has_ep(existing, source_ep):
            return

        updated = existing

        # 追加費用行
        if cost_row and "## 費用" in updated:
            # 在表格最後一行後追加
            updated = re.sub(
                r"(## 費用\n\|.*?\n\|[-|: ]+\n)((?:\|.*\n)*)",
                lambda m: m.group(1) + m.group(2) + cost_row + "\n",
                updated,
                count=1
            )
        elif cost_row and "## 費用" not in updated:
            # 在「## 評價與特色」前插入費用段落
            fee_section = f"## 費用\n| 費用 | 說明 | 來源 |\n|------|------|------|\n{cost_row}\n\n"
            if "## 評價與特色" in updated:
                updated = updated.replace("## 評價與特色", fee_section + "## 評價與特色", 1)
            else:
                updated += "\n" + fee_section

        # 追加評價（末尾，保持時間順序）
        eval_entry = f"- {wiki_link(source_ep)}：{feature}{'　小技巧：' + tips if tips else ''}"
        updated = append_to_section(updated, "評價與特色", eval_entry)

        # 追加出現集數（末尾）
        ep_entry = f"- {wiki_link(source_ep)}"
        if ep_entry not in updated:
            updated = append_to_section(updated, "出現集數", ep_entry)

        write_page(path, updated)
        print(f"  [更新 Entity/店家] {name} ← {source_ep}")


# ── 建立/更新 地點/ 頁 ───────────────────────────────────────────────────────
def upsert_location_page(location: dict, shops_in_ep: list = None):
    """
    location: {name, source_ep}
    shops_in_ep: 同集出現、且 location 欄包含此地名的店家名稱 list
    """
    name = location["name"]
    source_ep = location["source_ep"]
    country = LOCATION_COUNTRY.get(name, "未知")

    path = PLACES_DIR / f"{name}.md"
    existing = read_page(path)

    shops_in_ep = shops_in_ep or []
    shop_links = "\n".join(f"- {wiki_link(s)}" for s in shops_in_ep)

    if not existing:
        shop_section = f"\n## 提到的店家\n{shop_links}\n" if shop_links else "\n## 提到的店家\n"
        content = f"""# {name}

**類型**：城市 / 地點
**國家**：{country}

## 特色
（待補充）
{shop_section}
## 出現集數
- {wiki_link(source_ep)}
"""
        write_page(path, content)
        print(f"  [新建 Entity/地點] {name}")
    else:
        updated = existing

        if page_has_ep(existing, source_ep):
            # 即使集數已記錄，也嘗試補充新店家（末尾追加）
            for shop_name in shops_in_ep:
                shop_link = f"- {wiki_link(shop_name)}"
                if shop_link not in updated:
                    updated = append_to_section(updated, "提到的店家", shop_link)
            if updated != existing:
                write_page(path, updated)
            return

        # 追加新店家（末尾）
        for shop_name in shops_in_ep:
            shop_link = f"- {wiki_link(shop_name)}"
            if shop_link not in updated:
                updated = append_to_section(updated, "提到的店家", shop_link)

        # 追加出現集數（末尾）
        ep_entry = f"- {wiki_link(source_ep)}"
        if ep_entry not in updated:
            updated = append_to_section(updated, "出現集數", ep_entry)

        write_page(path, updated)
        print(f"  [更新 Entity/地點] {name} ← {source_ep}")


# ── 主處理邏輯 ────────────────────────────────────────────────────────────────
def process_source_file(filepath: Path):
    filename = filepath.name
    ep_name = extract_ep_name(filename)
    text = filepath.read_text(encoding="utf-8")

    print(f"\n處理：{filename}")

    # 1. 提取術語
    terms = parse_terms(text, ep_name)
    print(f"  術語：{len(terms)} 個")
    for term in terms:
        upsert_concept_page(term, concept_type="術語")

    # 2. 提取店家
    shops = parse_shops(text, ep_name)
    print(f"  店家：{len(shops)} 個")
    for shop in shops:
        upsert_shop_page(shop)

    # 3. 提取地點（從「提到的人物與地點」）
    locations = parse_locations_from_mentions(text, ep_name)

    # 同時從店家表格的 location 欄也提取地點
    shop_location_map: dict = {}  # location_name -> [shop_name, ...]
    for shop in shops:
        loc_raw = shop["location"]
        for keyword in LOCATION_KEYWORDS:
            if keyword in loc_raw:
                shop_location_map.setdefault(keyword, [])
                if shop["name"] not in shop_location_map[keyword]:
                    shop_location_map[keyword].append(shop["name"])
                # 只要沒在 locations 清單，就新增
                if not any(l["name"] == keyword for l in locations):
                    locations.append({"name": keyword, "source_ep": ep_name})

    # 去重（同名地點只保留一筆）
    seen_locs = set()
    unique_locations = []
    for loc in locations:
        if loc["name"] not in seen_locs:
            seen_locs.add(loc["name"])
            unique_locations.append(loc)

    print(f"  地點：{len(unique_locations)} 個")
    for loc in unique_locations:
        shops_here = shop_location_map.get(loc["name"], [])
        upsert_location_page(loc, shops_in_ep=shops_here)


def main():
    parser = argparse.ArgumentParser(description="從 Sources 頁提取並建立/更新 Wiki 概念頁")
    parser.add_argument("--test", type=int, metavar="N", help="只跑前 N 個未處理的檔案")
    parser.add_argument("--ep", type=str, metavar="EP",
                        help="只跑指定集數（跳過 processed 記錄），例如 S3EP100")
    parser.add_argument("--force-ep", type=str, metavar="EP",
                        help="強制重跑指定集數並從 processed 移除記錄（用於補救）")
    args = parser.parse_args()

    processed = load_processed()

    # 取得所有 Sources 頁
    all_sources = sorted(SOURCES_DIR.glob("*.md"))

    if args.force_ep:
        # 強制重跑模式：從 processed 清單移除後重跑，讓 entity 頁補上缺漏
        pattern = args.force_ep.upper()
        targets = [f for f in all_sources if pattern in f.name.upper()]
        if not targets:
            print(f"找不到包含 '{args.force_ep}' 的 Sources 頁")
            sys.exit(1)
        # 從 processed 移除
        removed = [n for n in processed if pattern in n.upper()]
        processed = [n for n in processed if pattern not in n.upper()]
        save_processed(processed)
        print(f"強制重跑模式：{targets[0].name}（已從 processed 移除：{removed}）")
    elif args.ep:
        # 指定集數模式（不修改 processed）
        pattern = args.ep.upper()
        targets = [f for f in all_sources if pattern in f.name.upper()]
        if not targets:
            print(f"找不到包含 '{args.ep}' 的 Sources 頁")
            sys.exit(1)
        print(f"指定模式：找到 {len(targets)} 個檔案")
    else:
        # 篩選未處理
        targets = [f for f in all_sources if f.name not in processed]
        print(f"共 {len(all_sources)} 個 Sources 頁，未處理：{len(targets)} 個")

        if args.test:
            targets = targets[:args.test]
            print(f"測試模式：只跑前 {args.test} 個")

    if not targets:
        print("沒有需要處理的檔案，結束")
        return

    total = len(targets)
    for i, filepath in enumerate(targets, 1):
        print(f"\n[{i}/{total}]", end="")
        try:
            process_source_file(filepath)
            if filepath.name not in processed:
                processed.append(filepath.name)
            save_processed(processed)
        except Exception as e:
            print(f"\n  !! 處理 {filepath.name} 時發生錯誤：{e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n完成！共處理 {total} 個 Sources 頁")


if __name__ == "__main__":
    main()
