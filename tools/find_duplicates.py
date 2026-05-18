"""
find_duplicates.py
掃描 Wiki/Entities/ 的所有實體，找出名稱相似的疑似重複配對。
輸出：依相似度排序的候選清單，附上各檔案的地點與類型。
"""

import os
import re
import sys
from itertools import combinations

sys.stdout.reconfigure(encoding='utf-8')

ENTITIES_DIR = os.path.join(os.path.dirname(__file__), '..', 'Wiki', 'Entities')
SIMILARITY_THRESHOLD = 0.45  # 調高 = 只看高度相似，調低 = 更多候選

# ---------- 讀取實體基本資訊 ----------

def parse_entity(filepath):
    """從 md 檔案抽出 類型、地點、服務類型。"""
    info = {'type': '', 'location': '', 'service': ''}
    try:
        with open(filepath, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('**類型**'):
                    info['type'] = line.split('：', 1)[-1].strip()
                elif line.startswith('**地點**'):
                    info['location'] = line.split('：', 1)[-1].strip()
                elif line.startswith('**服務類型**'):
                    info['service'] = line.split('：', 1)[-1].strip()
    except Exception:
        pass
    return info


def load_entities():
    entities = {}
    for fname in os.listdir(ENTITIES_DIR):
        if not fname.endswith('.md'):
            continue
        name = fname[:-3]  # 去掉 .md
        path = os.path.join(ENTITIES_DIR, fname)
        info = parse_entity(path)
        entities[name] = info
    return entities

# ---------- 相似度計算 ----------

def char_jaccard(a, b):
    """字符集的 Jaccard 相似度（適合中文）。"""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def substring_bonus(a, b):
    """若其中一個是另一個的子字串，給額外加分。"""
    if a in b or b in a:
        return 0.3
    # 最長公共子字串長度 / 較短字串長度
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    best = 0
    for i in range(len(shorter)):
        for j in range(i + 2, len(shorter) + 1):
            sub = shorter[i:j]
            if sub in longer:
                best = max(best, j - i)
    return best / len(shorter) * 0.5 if shorter else 0


def similarity(a, b):
    # 移除括號內補充說明再比較
    clean = lambda s: re.sub(r'[\(（].*?[\)）]', '', s).strip()
    ca, cb = clean(a), clean(b)
    base = char_jaccard(ca, cb)
    bonus = substring_bonus(ca, cb)
    return min(1.0, base + bonus)


# ---------- 主程式 ----------

def main():
    entities = load_entities()
    names = sorted(entities.keys())
    print(f"共 {len(names)} 個實體，開始配對比對...\n")

    candidates = []
    for a, b in combinations(names, 2):
        score = similarity(a, b)
        if score >= SIMILARITY_THRESHOLD:
            candidates.append((score, a, b))

    candidates.sort(reverse=True)

    print(f"找到 {len(candidates)} 組疑似重複（閾值 {SIMILARITY_THRESHOLD}）：\n")
    print(f"{'分數':>5}  {'實體A':<30} {'實體B':<30} {'A地點/類型':<20} {'B地點/類型'}")
    print("-" * 120)

    for score, a, b in candidates:
        ia, ib = entities[a], entities[b]
        a_info = f"{ia['location']} {ia['type']} {ia['service']}".strip()
        b_info = f"{ib['location']} {ib['type']} {ib['service']}".strip()
        print(f"{score:5.2f}  {a:<30} {b:<30} {a_info:<20} {b_info}")

    print(f"\n共 {len(candidates)} 組。建議從分數 0.7+ 開始人工確認。")


if __name__ == '__main__':
    main()
