"""
sync_whisper.py — 自動複製 whisper.cpp 輸出到 MyWiki

每周一 17:00 由 Windows 工作排程器呼叫。
把 E:/projects/whisper.cpp/output/ 裡的新 .txt 複製到
E:/projects/MyWiki/Raw/肥宅老司機/

改名資料夾時只需修改 DEST_DIR 這一行。
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

# ── 路徑設定（改名時只改這一行）────────────────────────────
SRC_DIR  = Path(r"E:\projects\whisper.cpp\output")
DEST_DIR = Path(r"E:\projects\fatty_wiki\Raw\肥宅老司機")
LOG_FILE = Path(r"E:\projects\fatty_wiki\tools\sync_whisper_log.txt")
# ───────────────────────────────────────────────────────────

def load_log() -> set:
    if not LOG_FILE.exists():
        return set()
    return set(LOG_FILE.read_text(encoding="utf-8").splitlines())

def append_log(filenames: list[str]):
    with LOG_FILE.open("a", encoding="utf-8") as f:
        for name in filenames:
            f.write(name + "\n")

def main():
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    copied_log = load_log()
    new_files = [
        f for f in SRC_DIR.glob("*.txt")
        if f.name not in copied_log
    ]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not new_files:
        print(f"[{timestamp}] 無新檔案，結束。")
        return

    copied = []
    for f in sorted(new_files):
        dest = DEST_DIR / f.name
        shutil.copy2(f, dest)
        copied.append(f.name)
        print(f"[{timestamp}] 複製：{f.name}")

    append_log(copied)
    print(f"[{timestamp}] 完成，共複製 {len(copied)} 個檔案。")

if __name__ == "__main__":
    main()
