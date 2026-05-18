#!/usr/bin/env python -X utf8
"""
enrich_places.py — 補充地點頁的 ## 特色 段落

對每個 特色 還是「待補充」的地點頁：
1. 收集所有提到該地點的來源頁摘要
2. 用 Ollama 生成 2-4 句話的特色描述
3. 更新 地點/.md 的 ## 特色 段落

用法：
  python -X utf8 tools/enrich_places.py           # 全部跑
  python -X utf8 tools/enrich_places.py --place 曼谷  # 只跑指定地點
  python -X utf8 tools/enrich_places.py --test 3  # 只跑前 3 個
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

BASE       = Path(__file__).parent.parent
PLACES_DIR = BASE / "Wiki" / "地點"
SOURCES_DIR = BASE / "Wiki" / "來源"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "gemma4"

PLACEHOLDER = "（待補充）"


def ollama(prompt: str, timeout: int = 120) -> str:
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
        }, timeout=timeout)
        return r.json().get("response", "").strip()
    except Exception as e:
        print(f"  ⚠️  Ollama 錯誤：{e}")
        return ""


def collect_source_snippets(place_name: str, max_chars: int = 4000) -> str:
    """從所有來源頁收集提到該地點的段落，限制總長度"""
    snippets = []
    total = 0
    for src in sorted(SOURCES_DIR.glob("*.md")):
        text = src.read_text(encoding="utf-8")
        if place_name not in text:
            continue
        # 只取摘要段落，減少雜訊
        summary = ""
        m = re.search(r"## 摘要\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
        if m:
            summary = m.group(1).strip()[:500]
        # 取提到地點的上下文（前後各 200 字）
        for match in re.finditer(re.escape(place_name), text):
            start = max(0, match.start() - 150)
            end = min(len(text), match.end() + 200)
            ctx = text[start:end].strip().replace("\n", " ")
            if ctx not in summary:
                summary += f"\n{ctx}"
        if summary:
            label = src.stem
            snippet = f"[{label}]\n{summary[:600]}"
            snippets.append(snippet)
            total += len(snippet)
            if total >= max_chars:
                break
    return "\n\n".join(snippets)


def generate_feature(place_name: str, snippets: str) -> str:
    if not snippets:
        return ""
    prompt = f"""你是一個旅遊知識庫編輯，根據以下來自播客和旅遊指南的資料，用繁體中文寫出「{place_name}」的特色描述。

要求：
- 2-4 句話，涵蓋：地理位置/定位、主要娛樂類型、消費水平概念、特別注意事項
- 客觀、具體、不帶評論性語氣
- 只輸出特色描述本身，不要標題、不要引用符號

參考資料：
{snippets}

{place_name}的特色："""

    result = ollama(prompt)
    # 清理可能的多餘格式
    result = re.sub(r'^[#*\-\s]+', '', result).strip()
    return result


def update_place_feature(path: Path, feature_text: str):
    text = path.read_text(encoding="utf-8")
    if PLACEHOLDER not in text:
        return False
    updated = text.replace(f"## 特色\n{PLACEHOLDER}", f"## 特色\n{feature_text}", 1)
    if updated == text:
        # 嘗試不同空白格式
        updated = re.sub(
            r"(## 特色\n)\s*（待補充）",
            r"\g<1>" + feature_text,
            text, count=1
        )
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--place", type=str, default="", help="只跑指定地點")
    parser.add_argument("--test",  type=int, default=0, help="只跑前 N 個")
    args = parser.parse_args()

    all_places = sorted(PLACES_DIR.glob("*.md"))

    if args.place:
        targets = [p for p in all_places if args.place in p.stem]
    else:
        # 只處理 特色 還是待補充的
        targets = [
            p for p in all_places
            if PLACEHOLDER in p.read_text(encoding="utf-8")
        ]

    if args.test:
        targets = targets[:args.test]

    print(f"共 {len(targets)} 個地點待補充特色\n")

    for i, place_path in enumerate(targets, 1):
        name = place_path.stem
        print(f"[{i}/{len(targets)}] {name}", flush=True)

        snippets = collect_source_snippets(name)
        if not snippets:
            print(f"  找不到相關來源，跳過")
            continue

        print(f"  收集到 {len(snippets)} 字的來源資料，送 Ollama...", flush=True)
        feature = generate_feature(name, snippets)

        if not feature:
            print(f"  Ollama 無回應，跳過")
            continue

        if update_place_feature(place_path, feature):
            print(f"  ✓ 已更新：{feature[:60]}...")
        else:
            print(f"  ✗ 更新失敗（格式不符）")

        time.sleep(1)  # 避免連打

    print(f"\n完成！")


if __name__ == "__main__":
    main()
