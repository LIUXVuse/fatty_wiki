#!/usr/bin/env python -u
# -*- coding: utf-8 -*-
"""
enrich_concept_defs.py — 用 Ollama 重新合成概念頁的「## 定義」段落
用法：
  python -X utf8 tools/enrich_concept_defs.py           # 全部符合條件的
  python -X utf8 tools/enrich_concept_defs.py --name GoGo Bar  # 只跑指定概念
  python -X utf8 tools/enrich_concept_defs.py --test 5  # 只跑前 5 個
"""

import re
import sys
import time
import json
import argparse
import requests
from pathlib import Path

# ── 路徑設定 ────────────────────────────────────────────────────────────────
BASE         = Path(__file__).parent.parent
CONCEPTS_DIR = BASE / "Wiki" / "概念"
SOURCES_DIR  = BASE / "Wiki" / "來源"
OLLAMA_URL   = "http://localhost:11434/api/generate"
MODEL        = "gemma3:27b"

# ── 輔助：讀概念頁，提取「## 出現集數」裡的來源名稱 ────────────────────────
def extract_sources(text: str) -> list[str]:
    """從 ## 出現集數 段落提取 [[xxx]] 連結。"""
    m = re.search(r"##\s*出現集數(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if not m:
        return []
    return re.findall(r"\[\[([^\]]+)\]\]", m.group(1))

# ── 輔助：讀概念頁，取得現有定義長度 ──────────────────────────────────────
def get_definition_len(text: str) -> int:
    m = re.search(r"##\s*定義\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if not m:
        return 0
    return len(m.group(1).strip())

# ── 輔助：從來源頁收集含概念名的上下文段落 ────────────────────────────────
def collect_context(name: str, source_names: list[str], max_sources=5, window=200) -> str:
    snippets = []
    for src in source_names[:max_sources]:
        path = SOURCES_DIR / f"{src}.md"
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        idx = content.find(name)
        if idx == -1:
            continue
        start = max(0, idx - window)
        end   = min(len(content), idx + len(name) + window)
        snippet = content[start:end].strip()
        snippets.append(f"[來源：{src}]\n{snippet}")
    return "\n\n".join(snippets)[:3000]

# ── 輔助：呼叫 Ollama ────────────────────────────────────────────────────────
def ask_ollama(name: str, context: str) -> str | None:
    prompt = (
        f"你是一個知識庫編輯，根據以下資料，用繁體中文為「{name}」寫一段定義。\n\n"
        "要求：\n"
        "- 2-3 句話，說明：這是什麼、在哪裡用、有什麼特色或注意事項\n"
        "- 用白話，國中生能懂\n"
        "- 只輸出定義本身，不要標題、編號、引用符號\n\n"
        f"參考資料：\n{context}\n\n"
        f"{name} 的定義："
    )
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"    Ollama 錯誤：{e}", file=sys.stderr)
        return None

# ── 輔助：把新定義寫回概念頁 ────────────────────────────────────────────────
def update_definition(path: Path, text: str, new_def: str) -> str:
    new_block = f"## 定義\n{new_def}\n"
    # 如果已有 ## 定義，替換它（到下一個 ## 為止）
    if re.search(r"##\s*定義", text):
        text = re.sub(
            r"##\s*定義\s*\n.*?(?=\n##|\Z)",
            new_block,
            text,
            count=1,
            flags=re.DOTALL,
        )
    else:
        # 插入在 ## 出現集數 之前
        text = re.sub(
            r"(##\s*出現集數)",
            new_block + "\n\\1",
            text,
            count=1,
        )
    path.write_text(text, encoding="utf-8")
    return text

# ── 主流程 ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="只處理指定概念名稱")
    parser.add_argument("--test", type=int, metavar="N", help="只跑前 N 個")
    args = parser.parse_args()

    # 收集候選概念頁
    if args.name:
        candidates = [CONCEPTS_DIR / f"{args.name}.md"]
        candidates = [p for p in candidates if p.exists()]
    else:
        candidates = sorted(CONCEPTS_DIR.glob("*.md"))

    # 篩選符合條件的頁面
    targets = []
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        def_len = get_definition_len(text)
        sources = extract_sources(text)
        need_update = def_len < 15
        enough_data = len(sources) >= 3
        if need_update or enough_data:
            targets.append((path, text, sources))

    if args.test:
        targets = targets[:args.test]

    total = len(targets)
    if total == 0:
        print("沒有符合條件的概念頁。")
        return

    print(f"共 {total} 個概念頁需要更新\n")

    for i, (path, text, sources) in enumerate(targets, 1):
        name = path.stem
        context = collect_context(name, sources)

        if not context:
            print(f"[{i}/{total}] {name}  → 跳過（無資料）")
            continue

        new_def = ask_ollama(name, context)
        if not new_def:
            print(f"[{i}/{total}] {name}  → 跳過（Ollama 失敗）")
            continue

        update_definition(path, text, new_def)
        print(f"[{i}/{total}] {name}  → 已更新")
        time.sleep(1)

    print("\n完成。")

if __name__ == "__main__":
    main()
