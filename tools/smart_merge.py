"""
smart_merge.py — 智慧合併重複 Entity 頁面

用法：
  python smart_merge.py --plan      # 分析並輸出合併計畫（不修改任何檔案）
  python smart_merge.py --execute   # 執行合併計畫
  python smart_merge.py --review    # 輸出需要人工確認的疑問清單
"""

import os, re, sys, json
from itertools import combinations

sys.stdout.reconfigure(encoding='utf-8')

ENTITIES_DIR = os.path.join(os.path.dirname(__file__), '..', 'Wiki', 'Entities')
WIKI_DIR     = os.path.join(os.path.dirname(__file__), '..', 'Wiki')
PLAN_FILE    = os.path.join(os.path.dirname(__file__), 'merge_plan.json')

# ── 讀取 Entity ──────────────────────────────────────────────

def parse_entity(filepath):
    info = {'type': '', 'location': '', 'service': '', 'raw': ''}
    try:
        with open(filepath, encoding='utf-8') as f:
            content = f.read()
        info['raw'] = content
        for line in content.splitlines():
            line = line.strip()
            if line.startswith('**類型**'):    info['type']     = line.split('：', 1)[-1].strip()
            elif line.startswith('**地點**'):  info['location'] = line.split('：', 1)[-1].strip()
            elif line.startswith('**服務類型**'): info['service'] = line.split('：', 1)[-1].strip()
    except Exception:
        pass
    return info

def load_all():
    entities = {}
    for fname in os.listdir(ENTITIES_DIR):
        if fname.endswith('.md'):
            name = fname[:-3]
            entities[name] = parse_entity(os.path.join(ENTITIES_DIR, fname))
    return entities

# ── 名稱正規化（去掉括號補充說明）────────────────────────────

BRACKET_RE = re.compile(r'\s*[\(（\[].*?[\)）\]]')

def strip_brackets(name):
    return BRACKET_RE.sub('', name).strip()

def is_bracket_variant(a, b):
    """b 是 a 加上括號補充說明，或反之。"""
    ca, cb = strip_brackets(a), strip_brackets(b)
    if ca == cb and (ca != a or cb != b):   # 有一個有括號
        return True
    if ca == b or cb == a:                  # 一個是另一個的 base
        return True
    return False

def location_compatible(loc_a, loc_b):
    """地點相容：一個為空，或有共同的地名關鍵字。"""
    if not loc_a or not loc_b:
        return True
    # 取地點裡每個中文詞（2字以上），有交集就算相容
    def tokens(s):
        return set(re.findall(r'[\u4e00-\u9fff]{2,}', s))
    return bool(tokens(loc_a) & tokens(loc_b))

# ── 選正規名稱（保留較簡單的，即沒有括號的那個）────────────────

def canonical_of(a, b):
    """沒有括號的那個當主頁；都有或都沒有，選較短的。"""
    a_has = bool(BRACKET_RE.search(a))
    b_has = bool(BRACKET_RE.search(b))
    if a_has and not b_has: return b, a
    if b_has and not a_has: return a, b
    return (a, b) if len(a) <= len(b) else (b, a)

# ── 合併兩個 Entity 頁面的文字內容 ──────────────────────────────

def extract_section(content, header):
    """抽取特定標題下的內容（不含下一個 ## 標題之前）。"""
    pattern = rf'##\s*{re.escape(header)}\s*\n(.*?)(?=\n##|\Z)'
    m = re.search(pattern, content, re.DOTALL)
    return m.group(1).strip() if m else ''

def merge_list_section(content_a, content_b, header):
    """合併兩個 section 的列表項，去除完全重複行。"""
    sec_a = extract_section(content_a, header)
    sec_b = extract_section(content_b, header)
    lines = []
    seen = set()
    for line in (sec_a + '\n' + sec_b).splitlines():
        stripped = line.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            lines.append(line)
    return '\n'.join(lines)

def merge_entity_content(canonical_name, canonical_content, dup_name, dup_content):
    """把 dup 的資訊合入 canonical，回傳合併後的內容。"""
    merged = canonical_content

    # 加入別名
    if '**別名**' not in merged:
        # 插在第一個空行後的 metadata 區
        alias_line = f'**別名**：{dup_name}'
        merged = re.sub(r'(\*\*[^*]+\*\*：[^\n]+\n)(?!\*\*)',
                        r'\1' + alias_line + '\n', merged, count=1)
    else:
        merged = re.sub(r'(\*\*別名\*\*：.*)',
                        lambda m: m.group(1) + f'、{dup_name}' if dup_name not in m.group(1) else m.group(1),
                        merged)

    # 合併「評價與特色」
    for header in ['評價與特色', '特色', '評價']:
        dup_sec = extract_section(dup_content, header)
        if dup_sec:
            if header in merged:
                merged_sec = merge_list_section(canonical_content, dup_content, header)
                merged = re.sub(rf'(##\s*{header}\s*\n).*?(?=\n##|\Z)',
                                r'\1' + merged_sec + '\n', merged, flags=re.DOTALL)
            else:
                merged += f'\n\n## {header}\n{dup_sec}\n'

    # 合併「出現集數」
    dup_eps = extract_section(dup_content, '出現集數')
    if dup_eps:
        if '出現集數' in merged:
            merged_eps = merge_list_section(canonical_content, dup_content, '出現集數')
            merged = re.sub(r'(##\s*出現集數\s*\n).*?(?=\n##|\Z)',
                            r'\1' + merged_eps + '\n', merged, flags=re.DOTALL)
        else:
            merged += f'\n\n## 出現集數\n{dup_eps}\n'

    return merged

# ── 全庫連結替換 ──────────────────────────────────────────────

def update_links_in_wiki(old_name, new_name):
    """把 Wiki/ 下所有 .md 檔案的 [[old_name]] 替換成 [[new_name]]。"""
    count = 0
    for root, _, files in os.walk(WIKI_DIR):
        for fname in files:
            if not fname.endswith('.md'):
                continue
            path = os.path.join(root, fname)
            try:
                with open(path, encoding='utf-8') as f:
                    content = f.read()
                new_content = content.replace(f'[[{old_name}]]', f'[[{new_name}]]')
                if new_content != content:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    count += 1
            except Exception:
                pass
    return count


def scan_bare_text(old_name):
    """掃描 Wiki/ 下所有 .md 是否還有不帶 [[]] 的裸字引用舊名稱。"""
    hits = []
    for root, _, files in os.walk(WIKI_DIR):
        for fname in files:
            if not fname.endswith('.md'):
                continue
            path = os.path.join(root, fname)
            # 跳過已刪除的舊 Entity 自身
            if os.path.basename(path) == old_name + '.md':
                continue
            try:
                with open(path, encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        if old_name in line and f'[[{old_name}]]' not in line:
                            hits.append((path, i, line.rstrip()))
            except Exception:
                pass
    return hits

# ── Phase 1：建立合併計畫 ─────────────────────────────────────

def build_plan(entities):
    auto_merges = []   # 確定可自動合併
    review_list = []   # 需要人工確認

    names = list(entities.keys())
    processed = set()

    for a, b in combinations(names, 2):
        if a in processed or b in processed:
            continue
        if not is_bracket_variant(a, b):
            continue

        ia, ib = entities[a], entities[b]
        canon, dup = canonical_of(a, b)

        if location_compatible(ia['location'], ib['location']):
            auto_merges.append({
                'canonical': canon,
                'duplicate': dup,
                'reason': '括號變體，地點相容'
            })
            processed.add(dup)
        else:
            review_list.append({
                'a': a, 'a_loc': ia['location'],
                'b': b, 'b_loc': ib['location'],
                'reason': '括號變體但地點不同，需人工確認'
            })

    return auto_merges, review_list

# ── Phase 2：執行合併 ─────────────────────────────────────────

def execute_plan(plan):
    for item in plan:
        canon = item['canonical']
        dup   = item['duplicate']

        canon_path = os.path.join(ENTITIES_DIR, canon + '.md')
        dup_path   = os.path.join(ENTITIES_DIR, dup + '.md')

        if not os.path.exists(canon_path):
            print(f'  [SKIP] 找不到主檔：{canon}.md')
            continue
        if not os.path.exists(dup_path):
            print(f'  [SKIP] 找不到副檔：{dup}.md（可能已刪）')
            continue

        with open(canon_path, encoding='utf-8') as f:
            canon_content = f.read()
        with open(dup_path, encoding='utf-8') as f:
            dup_content = f.read()

        merged = merge_entity_content(canon, canon_content, dup, dup_content)

        with open(canon_path, 'w', encoding='utf-8') as f:
            f.write(merged)

        link_count = update_links_in_wiki(dup, canon)
        os.remove(dup_path)

        print(f'  ✓ [{dup}] → [{canon}]，更新 {link_count} 個連結')

        bare = scan_bare_text(dup)
        if bare:
            print(f'  ⚠️  仍有 {len(bare)} 處裸字引用（無[[]]），需手動確認：')
            for path, lineno, line in bare[:5]:
                print(f'     {path}:{lineno}: {line.strip()[:80]}')

# ── 主程式 ───────────────────────────────────────────────────

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else '--plan'
    entities = load_all()

    if mode == '--plan':
        auto, review = build_plan(entities)
        with open(PLAN_FILE, 'w', encoding='utf-8') as f:
            json.dump({'auto': auto, 'review': review}, f, ensure_ascii=False, indent=2)
        print(f'計畫已存到 merge_plan.json')
        print(f'  自動合併：{len(auto)} 組')
        print(f'  待確認：  {len(review)} 組')
        print()
        print('=== 自動合併預覽 ===')
        for item in auto:
            print(f'  [{item["duplicate"]}] → [{item["canonical"]}]')
        print()
        print('=== 待確認清單 ===')
        for item in review:
            print(f'  {item["a"]} ({item["a_loc"]})  vs  {item["b"]} ({item["b_loc"]})')

    elif mode == '--execute':
        if not os.path.exists(PLAN_FILE):
            print('找不到 merge_plan.json，請先執行 --plan')
            return
        with open(PLAN_FILE, encoding='utf-8') as f:
            plan = json.load(f)
        print(f'開始執行 {len(plan["auto"])} 組自動合併...')
        execute_plan(plan['auto'])
        print('完成。')

    elif mode == '--review':
        if not os.path.exists(PLAN_FILE):
            print('找不到 merge_plan.json，請先執行 --plan')
            return
        with open(PLAN_FILE, encoding='utf-8') as f:
            plan = json.load(f)
        print(f'共 {len(plan["review"])} 組待確認：\n')
        for item in plan['review']:
            print(f'  {item["a"]}（{item["a_loc"]}）')
            print(f'  {item["b"]}（{item["b_loc"]}）')
            print()

if __name__ == '__main__':
    main()
