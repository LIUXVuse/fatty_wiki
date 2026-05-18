"""
MyWiki Ollama 批量處理腳本
用法：python tools/ingest_ollama.py [--limit N] [--ep S3EP5] [--folder 肥宅老司機]

功能：
  掃描 Raw/ 下所有子資料夾（排除 claude/ 和 processed/）
  → 呼叫 Ollama (gemma4) 整理成 Wiki Source 頁
  → 存到 Wiki/Sources/
  → 把原檔移到 Raw/processed/<子資料夾>/

需求：
  pip install requests
  Ollama 在 localhost:11434 跑著，有 gemma4 模型
"""

import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
import re
import json
import shutil
import argparse
import subprocess
import time
import requests
from pathlib import Path
from datetime import date

# ── 路徑設定 ──────────────────────────────────────────────
BASE = Path(__file__).parent.parent
RAW_DIR = BASE / "Raw"
OUT_DIR = BASE / "Wiki" / "來源"
# 排除這些子資料夾（不讓 Ollama 處理）
EXCLUDE_FOLDERS = {"processed", "claude"}
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4"
TODAY = date.today().isoformat()

# gemma4 有 1M context，完整逐字稿直接塞進去
MAX_CHARS = 0  # 0 = 不截斷

# 開頭固定廣播詞（這些行出現就跳過，不算內容）
SKIP_PATTERNS = [
    "大家好,我們是肥宅老司機",
    "大家好，我們是肥宅老司機",
    "在這裡,充滿了各種不正經",
    "在這裡充滿了各種不正經",
    "還有我們夢到的各種奇妙體驗",
    "如有雷同,純屬巧合",
    "如有雷同，純屬巧合",
    "節目內容充滿著",
    "未滿十八歲",
    "未滿18歲",
    "(音樂)",
    "（音樂）",
]

def wait_for_gpu_idle(threshold_mb=5000, poll_sec=30):
    """等到 GPU 記憶體用量低於 threshold_mb 才繼續，避免和其他 Ollama 任務衝突"""
    while True:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            used_mb = int(r.stdout.strip().split("\n")[0])
        except Exception:
            print("  ⚠️  無法讀取 GPU 狀態，直接繼續")
            return
        if used_mb < threshold_mb:
            print(f"  ✅ GPU 空閒（{used_mb} MB），開始執行")
            return
        print(f"  ⏳ GPU 忙碌（{used_mb} MB），等待 {poll_sec} 秒後重試...")
        time.sleep(poll_sec)


def strip_intro(text: str) -> str:
    """移除開頭的固定 jingle 和廣告段落，找到真正的內容起點"""
    lines = text.splitlines()
    # 掃前 60 行，找第一行「不是 jingle 也不是空行」的位置
    content_start = 0
    jingle_zone = True
    for i, line in enumerate(lines[:60]):
        stripped = line.strip()
        if not stripped:
            continue
        is_jingle = any(p in stripped for p in SKIP_PATTERNS)
        if is_jingle:
            jingle_zone = True
            content_start = i + 1
        elif jingle_zone:
            # 第一次遇到非 jingle 行，這裡開始是真正內容
            content_start = i
            break
    return "\n".join(lines[content_start:])

PROMPT_TEMPLATE = """\
你是「肥宅老司機」Podcast 的知識庫整理員。以下是 {ep} 的逐字稿，開頭幾分鐘可能是廣告，請自行略過。

這個節目的內容通常包含：主持人與嘉賓聊成人娛樂體驗、店家評測、妹子點評、搞笑故事、旅遊攻略。
你的任務是把逐字稿裡的精華完整萃取出來，保留所有具體細節，不要過度摘要或省略重要資訊。

請直接輸出以下格式的 Markdown，不要加任何說明文字：

# 肥宅老司機 {ep}

**來源**：肥宅老司機 Podcast {ep}
**日期**：{today}
**作者**：[[肥宅老司機]]
**分類**：播客、台灣

## 本集嘉賓
（列出這集出現的嘉賓名字，若無嘉賓則填「無」）

## 摘要
（2-3 句話說明這集在聊什麼，點出主題和地點）

## 店家與地點資訊
（把所有提到的店家、場所整理成表格，格式如下，店名一律用 [[雙括號]] 包起來：

| 店名 | 地點 | 費用 | 特色或評價 | 實用小技巧 |
| :--- | :--- | :--- | :--- | :--- |
| [[店名A]] | [[城市/國家]] | 費用 | 評價 | 技巧 |

沒有就留空格，不要捏造內容）

## 妹子點評
（逐一記錄嘉賓提到的每位服務人員，格式：
**[編號或暱稱]**（店名，城市）
- 外貌：顏值、身材、年齡感、膚色等描述
- 服務：手技/床技/口技/態度等評價
- 特色：她的絕活或讓人印象深刻的點
- 備註：上班時間、預約方式、注意事項等
若這集無妹子點評則省略此區塊）

## 精彩故事
（用輕鬆口吻記錄嘉賓分享的有趣經歷、爆笑事件、意外狀況、難忘體驗。
保留故事的起承轉合，不要壓縮成一句話。
若這集無特別故事則省略此區塊）

## 實用知識與技巧
（整理嘉賓分享的各種實戰心得、避坑技巧、觀念分享，
例如：如何選妹、如何跟妹子建立關係、旅遊安全、換匯注意事項等）

## 術語與概念
（解釋這集出現的行話、暗語或特殊概念，格式：[[術語]] — 解釋）

## 提到的人物與地點
（用 [[雙括號]] 列出所有嘉賓名、地名、店名）

---

逐字稿：

{transcript}
"""

def extract_ep(filename: str) -> str:
    """從檔名提取集數代號，如 S3EP3_ver.2.mp3.wav.txt → S3EP3"""
    m = re.match(r"(S\d+EP\d+)", filename, re.IGNORECASE)
    return m.group(1).upper() if m else filename.split("_")[0]

def file_priority(path: Path) -> int:
    """版本優先級：ver=0（最高）> draft=1 > talk=2 > 摘要=3（最低）
    注意：_draft 先判斷，避免 _draft_ver 被誤判成 _ver"""
    name = path.name.lower()
    if "_draft" in name: return 1  # draft_ver 仍是草稿，優先判斷
    if "_ver" in name:   return 0
    if "_talk" in name:  return 2
    if "摘要" in name:   return 3
    return 1

def group_by_ep(files: list) -> dict:
    """把檔案按集數分組，回傳 {ep: [Path, ...]}"""
    groups = {}
    for f in files:
        ep = extract_ep(f.name)
        groups.setdefault(ep, []).append(f)
    return groups

def pick_best(files: list) -> Path:
    """從同集的多個檔中選優先級最高、最長的一個"""
    # 先排優先級，再排檔案大小（同優先級取最大）
    return sorted(files, key=lambda f: (file_priority(f), -f.stat().st_size))[0]

def source_page_exists(ep: str) -> bool:
    """檢查這集的 Source 頁是否已存在（用 re 避免 S3EP1 誤中 S3EP10）"""
    pattern = re.compile(re.escape(ep) + r"(?!\d)", re.IGNORECASE)
    for f in OUT_DIR.glob("*.md"):
        if pattern.search(f.name):
            return True
    return False

def call_ollama(prompt: str) -> str:
    """呼叫 Ollama，回傳生成文字"""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 131072, "num_predict": 8192}
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=600)
        resp.raise_for_status()
        return resp.json()["response"].strip()
    except requests.exceptions.ConnectionError:
        print(f"  ❌ 無法連線 Ollama（{OLLAMA_URL}），請確認 Ollama 有在跑")
        return ""
    except Exception as e:
        print(f"  ❌ Ollama 錯誤：{e}")
        return ""

def build_canonical_map() -> dict[str, str]:
    """掃描 Wiki 各資料夾，回傳 {小寫名稱: 正確檔名（不含.md）}"""
    canonical = {}
    for folder in ("概念", "人物", "店家", "地點"):
        for f in (BASE / "Wiki" / folder).glob("*.md"):
            name = f.stem
            canonical[name.lower()] = name
    return canonical


def normalize_links(content: str, canonical: dict[str, str]) -> str:
    """把 Source 頁裡的 [[連結]] 修正為 Wiki 現有頁面的正確大小寫"""
    def replace(m):
        inner = m.group(1)
        # 支援 [[名稱|顯示文字]] 格式
        parts = inner.split("|", 1)
        name = parts[0].strip()
        corrected = canonical.get(name.lower(), name)
        if len(parts) == 2:
            return f"[[{corrected}|{parts[1]}]]"
        return f"[[{corrected}]]"
    return re.sub(r"\[\[([^\]]+)\]\]", replace, content)


def process_ep(ep: str, all_files: list, dry_run: bool = False) -> bool:
    """處理一集（可能有多個檔），選最好的來處理，其餘一起移走"""
    if source_page_exists(ep):
        print(f"  ⏭  {ep} 已有 Source 頁，跳過")
        return False

    best = pick_best(all_files)
    others = [f for f in all_files if f != best]
    label = "摘要" if "摘要" in best.name else "逐字稿"
    print(f"  📖 選用 {best.name}（{label}，{len(others)} 個其他版本略過）")

    try:
        text = best.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"  ❌ 讀取失敗：{e}")
        return False

    text = strip_intro(text)
    transcript = text if not MAX_CHARS else text[:MAX_CHARS]

    if dry_run:
        print(f"  🔍 [dry-run] 內容 {len(text)} 字，其他版本：{[f.name for f in others]}")
        return True

    prompt = PROMPT_TEMPLATE.format(ep=ep, today=TODAY, transcript=transcript)

    print(f"  🤖 送給 Ollama ({MODEL})...")
    result = call_ollama(prompt)
    if not result:
        return False

    canonical = build_canonical_map()
    result = normalize_links(result, canonical)

    out_file = OUT_DIR / f"肥宅老司機-{ep}.md"
    out_file.write_text(result, encoding="utf-8")
    print(f"  ✅ 已寫入 {out_file.name}")

    # 所有相關檔一起移走（保留原本的子資料夾結構）
    source_folder = all_files[0].parent
    processed_dir = BASE / "Raw" / "processed" / source_folder.name
    processed_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in all_files:
        try:
            shutil.move(str(f), processed_dir / f.name)
            moved += 1
        except FileNotFoundError:
            pass  # 已被其他進程移走，跳過
    print(f"  📦 {moved} 個檔已移至 processed/{source_folder.name}/")

    return True

def main():
    wait_for_gpu_idle()
    parser = argparse.ArgumentParser(description="MyWiki Ollama 批量整理腳本")
    parser.add_argument("--limit", type=int, default=0, help="最多處理幾集（0=全部）")
    parser.add_argument("--ep", type=str, default="", help="只處理指定集數，如 S3EP5")
    parser.add_argument("--folder", type=str, default="", help="只處理指定子資料夾，如 肥宅老司機")
    parser.add_argument("--dry-run", action="store_true", help="只列出會處理哪些，不實際呼叫")
    args = parser.parse_args()

    if not RAW_DIR.exists():
        print(f"❌ 找不到資料夾：{RAW_DIR}")
        sys.exit(1)

    # 掃 Raw/ 下所有子資料夾（排除 claude/ processed/）
    all_files = []
    for subfolder in RAW_DIR.iterdir():
        if subfolder.is_dir() and subfolder.name not in EXCLUDE_FOLDERS:
            if args.folder and subfolder.name != args.folder:
                continue
            all_files.extend(subfolder.glob("*.txt"))

    groups = group_by_ep(all_files)

    # 指定單集
    if args.ep:
        groups = {ep: files for ep, files in groups.items() if args.ep.upper() in ep}
        if not groups:
            print(f"❌ 找不到 {args.ep} 的逐字稿")
            sys.exit(1)

    # 按集數排序
    sorted_eps = sorted(groups.keys())
    total = len(sorted_eps)
    print(f"📂 找到 {total} 集（共 {len(all_files)} 個檔）")
    if args.limit:
        print(f"⚙️  限制處理 {args.limit} 集")

    done = 0
    for i, ep in enumerate(sorted_eps):
        if args.limit and done >= args.limit:
            break
        files = groups[ep]
        print(f"\n[{i+1}/{total}] {ep}（{len(files)} 個檔）")
        if process_ep(ep, files, dry_run=args.dry_run):
            done += 1

    print(f"\n🎉 完成！處理了 {done} 集")

if __name__ == "__main__":
    main()
