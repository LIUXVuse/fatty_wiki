"""
enrich_related_concepts.py — 自動填充「相關概念」段落

Phase 1：規則式（不需 Ollama）
  - 明確分組：暗黑系列、獨龍系列、戀愛派系列…
  - 後綴自動配對：X/X店、X/X課、X/X率、X/X網…

Phase 2：共現 + Ollama（跑完 Phase 1 再用）
  - 讀每個概念的「出現集數」，找共同出現的其他概念
  - 丟給 Ollama 過濾出真正語意相關的

用法：
  python -X utf8 tools/enrich_related_concepts.py           # Phase 1
  python -X utf8 tools/enrich_related_concepts.py --phase2  # Phase 1 + 2
  python -X utf8 tools/enrich_related_concepts.py --dry-run # 只顯示，不寫
"""

import re
import sys
import json
import argparse
import urllib.request
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

CONCEPTS_DIR = Path(__file__).parent.parent / "Wiki" / "概念"
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:27b"

# ─────────────────────────────────────────────────────────────────────
# Phase 1：明確分組（每組內互相連結）
# 格式：[(名稱, 說明), ...]  說明 = 填入對方相關概念時用的文字
# 若 說明 為 None，用預設「相關概念」
# ─────────────────────────────────────────────────────────────────────
EXPLICIT_GROUPS = [
    # 地下經濟系列
    [("暗黑", "地下娛樂產業的統稱"),
     ("暗黑GDP", "地下娛樂產業的經濟規模估算"),
     ("暗黑團", "組織性地下娛樂消費群體")],

    # 毒龍系列（獨龍/獨龍磚/獨龍鑽 是誤字，已在 ALIAS_MAP 合併）
    [("毒龍", "對肛門或會陰進行口舌刺激的服務"),
     ("Rimming", "舔肛服務的英文說法"),
     ("DATY", "舔陰服務，與毒龍屬同類型口技")],

    # 龍筋系列
    [("龍筋", "針對男性生殖系統的深層按摩"),
     ("抓龍筋", "龍筋按摩的動詞形式"),
     ("攝護腺保養", "相關前列腺保養概念"),
     ("前列腺按摩", "相關按摩服務"),
     ("前列腺高潮", "相關生理反應")],

    # 戀愛觀念系列
    [("戀愛客", "以戀愛感為主要訴求的消費者"),
     ("戀愛感", "服務中的戀愛氛圍"),
     ("戀愛派", "重視戀愛感的消費風格")],

    # 消費風格三派
    [("肉體派", "以身材外貌為主要選擇標準"),
     ("彈性派", "依情境彈性調整偏好"),
     ("戀愛派", "重視戀愛感的消費風格")],

    # 草食 vs 肉食
    [("肉食男", "主動積極型男性"),
     ("草食男", "被動保守型男性")],

    # 照片真實度
    [("圖文不符", "照片與本人落差大"),
     ("圖文相符", "照片與本人相符")],

    # 直球系列
    [("直球", "直接表達需求的溝通方式"),
     ("直球對決", "雙方直接交涉的情境")],

    # 金魚系列
    [("金魚店", "只看不買的觀光型消費場所"),
     ("金魚缸", "展示型服務環境")],

    # 外送服務
    [("外送", "叫外送服務的行為"),
     ("外送茶", "茶類外送服務的統稱")],

    # 小飛系列（手部服務）
    [("小飛", "手部服務的簡稱"),
     ("小飛機", "手部服務的完整說法")],

    # 仙人系列
    [("仙人指路", "引導消費者的介紹人"),
     ("仙人跳", "以美色誘騙的詐騙手法")],

    # HPV 相關
    [("HPV 9+1", "九價 HPV 疫苗加強版"),
     ("HPV 疫苗", "預防 HPV 的疫苗"),
     ("PrEP", "預防性投藥，降低性病風險")],

    # 黑色服務
    [("黑服", "地下違規服務的簡稱"),
     ("黑服務", "非法或違規的服務項目")],

    # 服務人數
    [("一對一", "單人服務模式"),
     ("一對多", "多人同時服務模式"),
     ("雙飛", "同時兩位服務人員")],

    # 公台系列
    [("公台制", "公共坐台計費制度"),
     ("公台店", "採公台制的店家"),
     ("坐檯", "坐台服務"),
     ("台費", "進入店內的基本費用"),
     ("做台費", "服務人員的台費收入")],

    # 原味系列
    [("原味", "未洗滌的衣物等個人物品"),
     ("原味內褲", "穿過的內褲作為商品")],

    # 回沖
    [("回沖", "服務人員主動回來找客人"),
     ("回沖率", "回沖發生的頻率統計")],

    # 141 論壇
    [("141", "141 討論版社群"),
     ("141論壇", "141 討論版網站")],

    # 互動系列
    [("互動", "服務過程中的互動品質"),
     ("互動房", "強調互動性的包廂類型")],

    # CD 系列
    [("CD", "換裝服務或易裝相關"),
     ("CD時間", "換裝服務的計時方式")],

    # 日洗日暗
    [("日洗", "白天場次的洗浴服務"),
     ("日洗日暗", "白天與夜晚洗浴服務的合稱"),
     ("日暗", "夜晚場次的洗浴服務")],

    # 包養系列
    [("包養", "長期金錢換取陪伴的關係"),
     ("包養網", "包養媒合的平台"),
     ("Sugar Daddy", "付費包養的年長男性"),
     ("Gold Digger", "尋求包養的對象")],

    # 泡泡浴
    [("泡泡浴", "日本泡泡浴服務"),
     ("泡泡浴店家", "提供泡泡浴的店家")],

    # 服務派系
    [("親工", "親密接觸為主的服務"),
     ("親女", "以女友感為主的服務風格"),
     ("GFE", "女友體驗服務（Girlfriend Experience）")],

    # 射精相關服務
    [("口爆", "口交至射精的服務"),
     ("口爆店", "以口爆為主要服務的店家"),
     ("中出", "體內射精"),
     ("BBBJ", "不帶套的口交服務")],

    # 半套
    [("半套", "不含性交的部分服務"),
     ("半套店", "提供半套服務的店家"),
     ("全套", "包含完整性服務"),
     ("全餐", "完整服務套餐")],

    # 點店系列
    [("點三", "0.3 等級計費標準"),
     ("點三店", "採點三計費的店家"),
     ("點五", "0.5 等級計費標準"),
     ("點五店", "採點五計費的店家")],

    # SOP 系列
    [("SOP", "標準作業流程服務"),
     ("SOPLAND", "SOP 服務的聚集區域")],

    # 前列腺系列（與龍筋重疊，單獨也保留）
    [("前列腺按摩", "針對前列腺的按摩服務"),
     ("前列腺高潮", "透過前列腺刺激達到的高潮"),
     ("攝護腺保養", "前列腺保養概念"),
     ("海底輪", "能量中心，與前列腺位置相近")],

    # 出圈 / 升級
    [("升級", "服務等級提升"),
     ("出圈", "超出原本規範的服務行為")],

    # 男娘 / Ladyboy
    [("男娘", "外表女性化的男性"),
     ("Ladyboy", "泰國變性人或跨性別者")],

    # Raw 系列
    [("Raw", "不帶套的性行為"),
     ("Raw Dogging", "裸體性行為（無保護）"),
     ("BBFS", "不帶套的完整服務"),
     ("BBBJ", "不帶套的口交服務")],

    # 時間管理
    [("時間管理大師", "同時維持多段關係的人"),
     ("多邊形戰士", "多方關係的玩家")],

    # 音樂課 / 體育課（隱語）
    [("音樂", "成人娛樂的隱語之一"),
     ("音樂課", "以音樂課隱語的服務")],

    [("體育", "成人娛樂的隱語之一"),
     ("體育課", "以體育課隱語的服務")],

    # 泰國洗浴
    [("泰洗", "泰國洗浴服務"),
     ("泰浴", "泰式沐浴服務"),
     ("NURU", "泰式或日式裸體油壓服務")],
]

# ─────────────────────────────────────────────────────────────────────
# 後綴自動配對規則
# 格式：(後綴, 正向說明, 反向說明)
# 正向 = 有後綴那頁加進無後綴那頁的相關概念
# 反向 = 無後綴那頁加進有後綴那頁的相關概念
# ─────────────────────────────────────────────────────────────────────
SUFFIX_RULES = [
    ("店",   "提供此服務的店家類型",     "此店家的核心服務概念"),
    ("店家", "提供此服務的店家",         "此店家的核心服務概念"),
    ("課",   "以課程為隱語的相同概念",   "隱語原型"),
    ("率",   "量化此行為的統計指標",     "此指標所衡量的行為"),
    ("網",   "相關媒合平台或網站",       "此平台的核心主題"),
    ("論壇", "相關討論社群",             "此論壇討論的核心主題"),
    ("房",   "提供此服務的包廂形式",     "此包廂的核心服務"),
    ("感",   "此概念的主觀體驗描述",     "此感受的來源概念"),
]


def read_md(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_md(path: Path, content: str, dry_run: bool):
    if dry_run:
        print(f"  [DRY] 不寫入 {path.name}")
    else:
        path.write_text(content, encoding="utf-8")


def get_existing_related(text: str) -> set[str]:
    """取出已有的相關概念名稱（[[X]] 格式）"""
    if "## 相關概念" not in text:
        return set()
    idx = text.index("## 相關概念")
    section = text[idx:]
    # 只看到下一個 ## 為止
    next_h2 = re.search(r"\n## ", section[3:])
    if next_h2:
        section = section[:next_h2.start() + 3]
    return set(re.findall(r"\[\[([^\]]+)\]\]", section))


def add_related(text: str, to_add: list[tuple[str, str]]) -> tuple[str, int]:
    """
    在 ## 相關概念 段落末尾追加尚未存在的條目。
    to_add: [(concept_name, description), ...]
    回傳 (新文字, 新增數量)
    """
    existing = get_existing_related(text)
    new_entries = [(n, d) for n, d in to_add if n not in existing]
    if not new_entries:
        return text, 0

    if "## 相關概念" not in text:
        text = text.rstrip() + "\n\n## 相關概念\n"

    idx = text.index("## 相關概念")
    section_start = idx + len("## 相關概念")

    insert_lines = "\n".join(f"- [[{n}]] — {d}" for n, d in new_entries)

    # 找插入點：段落末尾（下個 ## 前，或文件末尾）
    rest = text[section_start:]
    next_h2 = re.search(r"\n## ", rest)
    if next_h2:
        insert_pos = section_start + next_h2.start()
        new_text = text[:insert_pos] + "\n" + insert_lines + text[insert_pos:]
    else:
        new_text = text.rstrip() + "\n" + insert_lines + "\n"

    return new_text, len(new_entries)


def concept_path(name: str) -> Path | None:
    p = CONCEPTS_DIR / f"{name}.md"
    return p if p.exists() else None


# ─────────────────────────────────────────────────────────────────────
# Phase 1：規則式填充
# ─────────────────────────────────────────────────────────────────────
def phase1(dry_run: bool):
    print("=== Phase 1：規則式填充 ===\n")
    total_added = 0
    files_updated = set()

    def apply_link(source_name: str, target_name: str, desc: str):
        nonlocal total_added
        p = concept_path(source_name)
        if not p:
            return
        text = read_md(p)
        new_text, n = add_related(text, [(target_name, desc)])
        if n:
            write_md(p, new_text, dry_run)
            print(f"  {source_name} ← [[{target_name}]] ({desc[:20]}...)" if len(desc) > 20 else f"  {source_name} ← [[{target_name}]] ({desc})")
            total_added += n
            files_updated.add(source_name)

    # 明確分組：每組內互相連結
    for group in EXPLICIT_GROUPS:
        names = [item[0] for item in group]
        descs = {item[0]: item[1] for item in group}
        for i, (name, _) in enumerate(group):
            for j, (other_name, other_desc) in enumerate(group):
                if i == j:
                    continue
                apply_link(name, other_name, other_desc)

    print()

    # 後綴自動配對
    all_names = set(f.stem for f in CONCEPTS_DIR.glob("*.md"))
    for suffix, fwd_desc, rev_desc in SUFFIX_RULES:
        for name in sorted(all_names):
            if name.endswith(suffix):
                base = name[:-len(suffix)]
                if base in all_names and base:
                    apply_link(base, name, fwd_desc)
                    apply_link(name, base, rev_desc)

    print(f"\nPhase 1 完成：{len(files_updated)} 個檔案，新增 {total_added} 條相關概念連結")
    return files_updated


# ─────────────────────────────────────────────────────────────────────
# Phase 2：共現 + Ollama
# ─────────────────────────────────────────────────────────────────────
def build_cooccurrence():
    """建立共現矩陣：{概念A: {概念B: 共現次數}}"""
    ep_to_concepts = defaultdict(set)

    for md in CONCEPTS_DIR.glob("*.md"):
        text = md.read_text(encoding="utf-8")
        concept = md.stem
        eps = re.findall(r"\[\[肥宅老司機-(S3EP\d+)\]\]", text)
        for ep in eps:
            ep_to_concepts[ep].add(concept)

    cooccur = defaultdict(lambda: defaultdict(int))
    for ep, concepts in ep_to_concepts.items():
        lst = list(concepts)
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                cooccur[lst[i]][lst[j]] += 1
                cooccur[lst[j]][lst[i]] += 1

    return cooccur


def ask_ollama(concept: str, definition: str, candidates: list[str]) -> list[str]:
    """問 Ollama 從候選清單裡選出真正語意相關的概念（最多 5 個）"""
    candidate_str = "\n".join(f"- {c}" for c in candidates[:30])
    prompt = f"""你是成人娛樂知識庫的編輯。

概念：「{concept}」
定義：{definition or "（未知）"}

以下是在相同場合出現的其他概念，請從中挑出語意真正相關的（最多 5 個），輸出 JSON 陣列，只含概念名稱：

{candidate_str}

輸出格式（只要 JSON，不要解釋）：
["概念A", "概念B"]"""

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1}
    }).encode("utf-8")

    try:
        req = urllib.request.Request(OLLAMA_URL,
                                     data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())["response"].strip()
        # 找 JSON 陣列
        match = re.search(r"\[.*?\]", result, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"  Ollama 錯誤：{e}")
    return []


def get_definition(text: str) -> str:
    if "## 定義" not in text:
        return ""
    idx = text.index("## 定義")
    section = text[idx + 5:]
    next_h2 = re.search(r"\n## ", section)
    if next_h2:
        section = section[:next_h2.start()]
    return section.strip()[:200]


def phase2(dry_run: bool, skip_names: set[str]):
    print("\n=== Phase 2：共現 + Ollama 填充 ===\n")
    cooccur = build_cooccurrence()
    total_added = 0
    files_done = 0

    mds = sorted(CONCEPTS_DIR.glob("*.md"))
    empty_mds = []
    for md in mds:
        text = md.read_text(encoding="utf-8")
        existing = get_existing_related(text)
        if len(existing) < 2:  # 少於 2 個才補
            empty_mds.append(md)

    print(f"需要補充的概念：{len(empty_mds)} 個\n")

    for md in empty_mds:
        concept = md.stem
        text = read_md(md)
        definition = get_definition(text)

        # 從共現取前 20 個候選（排除已有的）
        existing = get_existing_related(text)
        candidates = sorted(cooccur[concept].items(), key=lambda x: -x[1])
        candidate_names = [c for c, _ in candidates if c not in existing][:20]

        if not candidate_names:
            continue

        print(f"[{concept}] 候選 {len(candidate_names)} 個 → 問 Ollama...")
        selected = ask_ollama(concept, definition, candidate_names)

        if not selected:
            print(f"  → Ollama 無回應，跳過")
            continue

        to_add = [(n, "共現相關概念") for n in selected
                  if n in set(c for c, _ in candidates)]

        new_text, n = add_related(text, to_add)
        if n:
            write_md(md, new_text, dry_run)
            print(f"  → 新增 {n} 個：{[x[0] for x in to_add]}")
            total_added += n
            files_done += 1
        else:
            print(f"  → 無新增")

    print(f"\nPhase 2 完成：{files_done} 個檔案，新增 {total_added} 條連結")


# ─────────────────────────────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase2",   action="store_true", help="也跑 Phase 2（Ollama）")
    parser.add_argument("--dry-run",  action="store_true", help="只顯示，不寫入")
    parser.add_argument("--only-phase2", action="store_true", help="只跑 Phase 2")
    args = parser.parse_args()

    if not args.only_phase2:
        updated = phase1(args.dry_run)
    else:
        updated = set()

    if args.phase2 or args.only_phase2:
        phase2(args.dry_run, updated)
