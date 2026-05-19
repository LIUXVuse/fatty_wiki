"""
batch_create_stubs.py — 批量建立缺失 Wiki stub 頁面

用 Ollama 自動分類並生成每個缺失連結目標的 stub 頁面。

用法：
  python tools/batch_create_stubs.py              # 跑 2+ 次出現的目標
  python tools/batch_create_stubs.py --min 1      # 包含單次出現
  python tools/batch_create_stubs.py --dry-run    # 只列出會做什麼
  python tools/batch_create_stubs.py --limit 50   # 只跑前 N 個
"""

import re
import sys
import json
import time
import argparse
import urllib.request
from pathlib import Path
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE   = Path(__file__).parent.parent
WIKI   = BASE / "Wiki"
DIRS   = {
    "地點": WIKI / "地點",
    "人物": WIKI / "人物",
    "店家": WIKI / "店家",
    "概念": WIKI / "概念",
    "來源": WIKI / "來源",
}

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:27b"

# ── 永遠跳過的目標 ──────────────────────────────────────────────
SKIP_SET = {
    # 外部平台 / 品牌
    "Twitter", "亞馬遜", "Grab", "Telegram", "Swag", "LINE",
    "Facebook", "Instagram", "YouTube", "Google", "TikTok",
    "Reddit", "Netflix", "Spotify", "特斯拉", "Apple",
    # 明顯亂碼 / 格式錯誤
    "中G壢IN 1", "Panda二NI", "W", "Travel",
    # 過於泛用的詞
    "某店", "某地", "某人",
}

# ── 跳過的正則模式 ──────────────────────────────────────────────
SKIP_PATTERNS = [
    r"^[A-Za-z]$",           # 單字母
    r"^\d+\.\d+$",           # 小數（0.3/0.5 已有頁面）
    r"^https?://",           # URL
    r"肥宅老司機.S3EP",       # 來源頁連結格式問題（由 merge_aliases 處理）
]

# ── Ollama 呼叫 ──────────────────────────────────────────────────
def ollama(prompt: str, timeout: int = 90) -> str:
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 600},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            OLLAMA_URL, data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())["response"].strip()
    except Exception as e:
        print(f"    ⚠️  Ollama 失敗：{e}")
        return ""


# ── 從 wiki 抓上下文句 ──────────────────────────────────────────
def get_context(name: str, source_files: list[str], max_snippets: int = 3) -> str:
    snippets = []
    for stem in source_files[:6]:
        for d in DIRS.values():
            f = d / f"{stem}.md"
            if not f.exists():
                f = WIKI / f"{stem}.md"
            if f.exists():
                text = f.read_text(encoding="utf-8", errors="ignore")
                for line in text.splitlines():
                    if f"[[{name}]]" in line or f"[[{name}|" in line:
                        clean = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", line).strip()
                        if len(clean) > 10:
                            snippets.append(clean[:120])
                            break
                if len(snippets) >= max_snippets:
                    break
        if len(snippets) >= max_snippets:
            break
    return " | ".join(snippets) if snippets else "（無額外上下文）"


# ── 讓 Ollama 分類並生成 stub ────────────────────────────────────
CLASSIFY_PROMPT = """你是繁體中文知識庫編輯，正在維護一個成人旅遊 podcast「肥宅老司機」的 wiki。

目標詞條：「{name}」
出現次數：{count}
上下文片段：{context}

任務：
1. 判斷類型（只能選一個）：地點 / 人物 / 店家 / 概念 / 忽略
   - 「忽略」用於：外部品牌、過於模糊、明顯亂碼
2. 如果不是「忽略」，用繁體中文生成一個 Markdown stub 頁面

格式規定（嚴格按照）：
第一行輸出類型，例如：TYPE:地點
然後輸出 Markdown 內容（不要加 ```）。

地點格式：
# {name}
**類型**：城市 / 地點
**國家**：（填入）
**上層地點**：（填入或省略）
## 特色
（1-3句，根據上下文推測，沒資訊就寫「待補充」）
## 提到的店家
## 出現集數

人物格式：
# {name}
**類型**：（主持人/來賓/聽眾投稿者）
**領域**：（填入）
## 簡介
（1-2句）
## 出現集數

店家格式：
# {name}
**類型**：（按摩店/KTV/GoGo Bar 等）
**地點**：（城市），台灣/泰國/...
## 簡介
（1-2句，根據上下文）
## 出現集數

概念格式：
# {name}
## 定義
（1-3句白話定義）
## 出現在
## 相關概念
"""


def classify_and_generate(name: str, count: int, ctx: str) -> tuple[str, str]:
    """回傳 (type_str, content)，type_str 是 地點/人物/店家/概念/忽略"""
    prompt = CLASSIFY_PROMPT.format(name=name, count=count, context=ctx)
    raw = ollama(prompt)
    if not raw:
        return "忽略", ""

    # 解析 TYPE: 行
    lines = raw.splitlines()
    type_str = "概念"
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith("TYPE:"):
            type_str = line[5:].strip()
            content_start = i + 1
            break

    content = "\n".join(lines[content_start:]).strip()
    # 確保 content 開頭是 # 標題
    if content and not content.startswith("#"):
        content = f"# {name}\n\n" + content

    return type_str, content


# ── 主流程 ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min", type=int, default=2, help="最少出現次數（預設 2）")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="最多處理 N 個（0=全部）")
    global OLLAMA_MODEL
    parser.add_argument("--model", default=OLLAMA_MODEL)
    args = parser.parse_args()
    OLLAMA_MODEL = args.model

    # 掃描所有頁面名稱
    all_pages = {f.stem for f in WIKI.rglob("*.md")}

    # 收集缺失目標 + 出現的檔案清單
    missing_files = defaultdict(list)
    for f in WIKI.rglob("*.md"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for l in re.findall(r"\[\[([^\]|#\n]+)", text):
            l = l.strip()
            if l and l not in all_pages:
                missing_files[l].append(f.stem)

    # 從 merge_aliases.py 和 enrich_concepts.py 載入所有別名（不應建新頁）
    alias_values: set[str] = set()
    for script_path in [BASE / "tools" / "merge_aliases.py",
                        BASE / "tools" / "enrich_concepts.py"]:
        try:
            src = script_path.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'"([^"]+)"', src):
                alias_values.add(m.group(1))
        except Exception:
            pass

    # 過濾
    targets = []
    for name, files in missing_files.items():
        count = len(files)
        if count < args.min:
            continue
        if name in SKIP_SET:
            continue
        if any(re.search(p, name) for p in SKIP_PATTERNS):
            continue
        if name in alias_values:
            continue  # 是別名，不建頁（merge_aliases 會修連結）
        targets.append((count, name, files))

    targets.sort(key=lambda x: -x[0])
    if args.limit:
        targets = targets[:args.limit]

    print(f"待處理：{len(targets)} 個目標（min={args.min}，{'dry-run' if args.dry_run else '實際寫入'}）\n")

    created = skipped_existing = skipped_ignore = errors = 0

    for i, (count, name, files) in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] [{count}次] {name}", end=" ... ", flush=True)

        if args.dry_run:
            ctx = get_context(name, files)
            print(f"ctx={ctx[:60]}")
            continue

        ctx = get_context(name, files)
        type_str, content = classify_and_generate(name, count, ctx)

        if type_str == "忽略" or not content:
            print(f"忽略")
            skipped_ignore += 1
            continue

        # 決定存放目錄
        dir_map = {"地點": "地點", "人物": "人物", "店家": "店家", "概念": "概念"}
        folder_key = dir_map.get(type_str, "概念")
        out_dir = DIRS[folder_key]
        # 名稱含非法字元（/ \ : * ? " < > |）→ 跳過
        if re.search(r'[/\\:*?"<>|]', name):
            print(f"跳過（非法字元）")
            skipped_ignore += 1
            continue

        out_path = out_dir / f"{name}.md"

        if out_path.exists():
            print(f"已存在")
            skipped_existing += 1
            continue

        out_path.write_text(content + "\n", encoding="utf-8")
        created += 1
        print(f"✅ {folder_key}/")
        time.sleep(0.1)  # 避免打爆 Ollama

    print(f"\n完成：建立 {created}｜已存在 {skipped_existing}｜忽略 {skipped_ignore}｜錯誤 {errors}")
    print("建議接著跑：")
    print("  python -X utf8 tools/merge_aliases.py")
    print("  python -X utf8 tools/sync_episode_refs.py")
    print("  python -X utf8 tools/generate_category_indexes.py")
    print("  python -X utf8 tools/update_index.py")


if __name__ == "__main__":
    main()
