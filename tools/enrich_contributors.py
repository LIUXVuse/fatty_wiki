#!/usr/bin/env python -X utf8
"""
enrich_contributors.py — 補充投稿者、來賓、主持人資訊

對每集逐字稿 + Sources 頁：
1. 讓 Ollama 提取三類人的故事和知識點
2. 更新 Sources 頁（加三個段落）
3. 建立/更新每個人的 Entities 頁（跨集累積）

用法：
  python -X utf8 tools/enrich_contributors.py          # 全部跑
  python -X utf8 tools/enrich_contributors.py --test 3 # 只跑前 3 個未處理集
  python -X utf8 tools/enrich_contributors.py --ep S3EP100  # 只跑特定集
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

# 從 merge_aliases 載入別名表，建立反查字典 {alias_lower: canonical}
def _build_reverse_alias() -> dict:
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from merge_aliases import ALIAS_MAP
        rev = {}
        for canonical, aliases in ALIAS_MAP.items():
            for alias in aliases:
                rev[alias.lower()] = canonical
        return rev
    except Exception:
        return {}

REVERSE_ALIAS = _build_reverse_alias()

BASE       = Path(__file__).parent.parent
SOURCES    = BASE / "Wiki" / "來源"
PEOPLE     = BASE / "Wiki" / "人物"
PROCESSED  = BASE / "Raw" / "processed"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "gemma3:27b"


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

SIMILAR_WARN_THRESHOLD = 0.65
MERGE_SUGGESTIONS = BASE / "tools" / "merge_suggestions.txt"

def _char_jaccard(a: str, b: str) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)

def find_similar_entity(name: str) -> str | None:
    """找最相似的現有 Entity 名稱，超過閾值就回傳，讓呼叫者決定怎麼處理。"""
    best_score, best_name = 0.0, None
    for f in PEOPLE.glob("*.md"):
        existing = f.stem
        if existing.lower() == name.lower():
            return None  # 完全一樣交給正常流程
        score = _char_jaccard(name, existing)
        if score > best_score:
            best_score, best_name = score, existing
    return best_name if best_score >= SIMILAR_WARN_THRESHOLD else None

def warn_similar(new_name: str, existing_name: str):
    msg = f"[疑似重複] 新建 [{new_name}] 但已有相似實體 [{existing_name}]，請用 smart_merge 確認\n"
    print(f"  ⚠️  {msg.strip()}", flush=True)
    with open(MERGE_SUGGESTIONS, "a", encoding="utf-8") as f:
        f.write(msg)

NOT_A_PERSON = {
    "老雞", "老濕", "老師", "主持人",
    "apple podcast", "spotify", "youtube", "ig", "facebook",
    "各位聽眾", "各位弟兄", "大家",
    "匿名留言", "匿名", "ig 弟兄", "另一位弟兄", "某弟兄", "路過弟兄",
}

PROMPT_TEMPLATE = """\
你是資料提取助手。以下是播客逐字稿和已整理摘要。

【本集嘉賓（已知）】
{guests}

【已整理摘要】
{sources_page}

【逐字稿】
{transcript}

請提取以下三類人的貢獻，嚴格按格式輸出：

=== 投稿者 ===
（從「感謝XXX分享/投稿/來信」找，排除老雞、老濕、各位弟兄、匿名等非人名）
名字：XXX
故事標題：一句話
故事摘要：2-4句
知識點：
- 知識點1
---

=== 來賓 ===
（只寫本集嘉賓列表裡的人，找他們在逐字稿裡分享了什麼）
名字：XXX
分享主題：一句話
內容摘要：2-4句
知識點：
- 知識點1
---

=== 主持人 ===
（只寫老雞和老濕各自的觀點，不需要故事，只要洞察/建議/點評）
名字：老雞
觀點：
- 觀點1
- 觀點2
---
名字：老濕
觀點：
- 觀點1
---

若某類別沒有內容，該類別整個省略。
"""


def is_valid_name(name: str) -> bool:
    return name.lower().strip() not in NOT_A_PERSON and len(name.strip()) >= 2


def call_ollama(prompt: str, timeout: int = 300) -> str:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 4096, "num_ctx": 32768},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


def extract_guests_from_sources(sources_text: str) -> list[str]:
    """從 Sources 頁「## 本集嘉賓」段落提取嘉賓名字"""
    m = re.search(r"##\s*本集嘉賓\s*\n([\s\S]+?)(?=\n##|\Z)", sources_text)
    if not m:
        return []
    raw = m.group(1)
    guests = []
    for line in raw.splitlines():
        line = line.strip().lstrip("-•*").strip()
        # 去掉 [[...]] 括號，取名字部分
        line = re.sub(r"\[\[(.+?)\]\]", r"\1", line)
        # 去掉括號後的說明
        line = re.sub(r"[（(].+", "", line).strip()
        if line and is_valid_name(line):
            guests.append(line)
    return guests


def parse_sections(text: str) -> dict:
    """
    將 Ollama 輸出依 === 投稿者 ===、=== 來賓 ===、=== 主持人 === 分段。
    回傳 {"contributors": str, "guests": str, "hosts": str}
    """
    result = {"contributors": "", "guests": "", "hosts": ""}
    pattern = re.compile(r"===\s*(投稿者|來賓|主持人)\s*===", re.MULTILINE)
    parts = pattern.split(text)
    # parts: [前置文字, 標題1, 內容1, 標題2, 內容2, ...]
    i = 1
    while i < len(parts) - 1:
        label = parts[i].strip()
        content = parts[i + 1]
        if label == "投稿者":
            result["contributors"] = content
        elif label == "來賓":
            result["guests"] = content
        elif label == "主持人":
            result["hosts"] = content
        i += 2
    return result


def parse_contributor_blocks(section_text: str) -> list[dict]:
    """解析投稿者段落，回傳 [{name, title, summary, tips}]"""
    results = []
    blocks = re.split(r"\n---+\n?", section_text.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        name  = re.search(r"名字[：:]\s*(.+)", block)
        title = re.search(r"故事標題[：:]\s*(.+)", block)
        summ  = re.search(r"故事摘要[：:]\s*([\s\S]+?)(?=知識點[：:]|$)", block)
        tips_match = re.search(r"知識點[：:]([\s\S]+)", block)
        if not name or not is_valid_name(name.group(1)):
            continue
        tips_raw = tips_match.group(1).strip() if tips_match else ""
        tips = [t.lstrip("-• ").strip() for t in tips_raw.splitlines() if t.strip().lstrip("-• ")]
        results.append({
            "name":    name.group(1).strip(),
            "title":   title.group(1).strip() if title else "（無標題）",
            "summary": summ.group(1).strip() if summ else "",
            "tips":    tips,
        })
    return results


def parse_guest_blocks(section_text: str) -> list[dict]:
    """解析來賓段落，回傳 [{name, topic, summary, tips}]"""
    results = []
    blocks = re.split(r"\n---+\n?", section_text.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        name  = re.search(r"名字[：:]\s*(.+)", block)
        topic = re.search(r"分享主題[：:]\s*(.+)", block)
        summ  = re.search(r"內容摘要[：:]\s*([\s\S]+?)(?=知識點[：:]|$)", block)
        tips_match = re.search(r"知識點[：:]([\s\S]+)", block)
        if not name or not is_valid_name(name.group(1)):
            continue
        tips_raw = tips_match.group(1).strip() if tips_match else ""
        tips = [t.lstrip("-• ").strip() for t in tips_raw.splitlines() if t.strip().lstrip("-• ")]
        results.append({
            "name":    name.group(1).strip(),
            "topic":   topic.group(1).strip() if topic else "（無主題）",
            "summary": summ.group(1).strip() if summ else "",
            "tips":    tips,
        })
    return results


def parse_host_blocks(section_text: str) -> dict:
    """解析主持人段落，回傳 {"老雞": [...觀點], "老濕": [...觀點]}"""
    result = {"老雞": [], "老濕": []}
    blocks = re.split(r"\n---+\n?", section_text.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        name_m = re.search(r"名字[：:]\s*(.+)", block)
        if not name_m:
            continue
        name = name_m.group(1).strip()
        if name not in result:
            continue
        views_match = re.search(r"觀點[：:]([\s\S]+)", block)
        if views_match:
            raw = views_match.group(1).strip()
            views = [t.lstrip("-• ").strip() for t in raw.splitlines() if t.strip().lstrip("-• ")]
            result[name].extend(views)
    return result


def build_contributors_section(contributors: list[dict]) -> str:
    if not contributors:
        return ""
    section = "\n## 投稿者\n"
    for c in contributors:
        section += f"\n### {c['name']}\n"
        section += f"**故事**：{c['title']}\n\n"
        section += f"{c['summary']}\n"
        if c["tips"]:
            section += "\n**知識點**：\n"
            for t in c["tips"]:
                section += f"- {t}\n"
    return section


def build_guests_section(guests: list[dict]) -> str:
    if not guests:
        return ""
    section = "\n## 來賓分享\n"
    for g in guests:
        section += f"\n### {g['name']}\n"
        section += f"**主題**：{g['topic']}\n\n"
        section += f"{g['summary']}\n"
        if g["tips"]:
            section += "\n**知識點**：\n"
            for t in g["tips"]:
                section += f"- {t}\n"
    return section


def build_hosts_section(hosts: dict) -> str:
    if not hosts["老雞"] and not hosts["老濕"]:
        return ""
    section = "\n## 主持人觀點\n"
    for host_name in ["老雞", "老濕"]:
        views = hosts.get(host_name, [])
        if views:
            section += f"\n### {host_name}\n"
            for v in views:
                section += f"- {v}\n"
    return section


def is_fully_processed(sources_text: str) -> bool:
    """Sources 頁同時含有 ## 來賓分享 和 ## 主持人觀點，且兩段都有實際內容才算完整處理。
    只有標題沒有內容（Ollama 無輸出）不算完整，下次仍會重試。"""
    import re as _re
    for heading in ("## 來賓分享", "## 主持人觀點"):
        if heading not in sources_text:
            return False
        # 確認段落有實際內容（不只是標題行）
        m = _re.search(re.escape(heading) + r'\n(.*?)(?=\n##|\Z)', sources_text, _re.DOTALL)
        if not m or not m.group(1).strip():
            return False
    return True


def remove_old_contributors_section(text: str) -> str:
    """移除舊的投稿者/來賓/主持人段落，重跑時防止重複插入"""
    for heading in ["投稿者", "來賓分享", "主持人觀點"]:
        pattern = re.compile(rf"\n## {re.escape(heading)}\n[\s\S]+?(?=\n## |\Z)", re.MULTILINE)
        text = pattern.sub("", text)
    return text


def update_sources_page(
    sources_path: Path,
    contributors: list[dict],
    guests: list[dict],
    hosts: dict,
):
    """在 Sources 頁補充/更新三個段落"""
    text = sources_path.read_text(encoding="utf-8")

    # 先移除舊的 ## 投稿者 段落
    text = remove_old_contributors_section(text)

    contrib_section = build_contributors_section(contributors)
    guests_section  = build_guests_section(guests)
    hosts_section   = build_hosts_section(hosts)

    insert_block = contrib_section + guests_section + hosts_section

    if "## 提到的人物與地點" in text:
        text = text.replace("## 提到的人物與地點", insert_block + "\n## 提到的人物與地點")
    else:
        text = text.rstrip() + "\n" + insert_block

    sources_path.write_text(text, encoding="utf-8")


def update_contributor_entity(name: str, ep_id: str, sources_filename: str, c: dict):
    """建立或更新投稿者 Entities 頁"""
    # 如果是已知別名，導向正確主名（例如「老師」→「老濕」）
    canonical = REVERSE_ALIAS.get(name.lower())
    if canonical:
        print(f"  [別名正規化] {name} → {canonical}", flush=True)
        name = canonical
    safe_name   = re.sub(r'[\\/:*?"<>|]', "_", name)
    entity_path = PEOPLE / f"{safe_name}.md"
    ep_ref      = sources_filename.replace(".md", "")
    ep_link     = f"[[{ep_ref}]]"

    story_block = f"\n### {ep_id} — {c['title']}\n{c['summary']}\n"
    if c["tips"]:
        story_block += "\n**知識點**：\n"
        for t in c["tips"]:
            story_block += f"- {t}\n"

    if entity_path.exists():
        text = entity_path.read_text(encoding="utf-8")
        if ep_id in text:
            return
        appearance = f"- {ep_link} — {c['title']}"
        if "## 出現集數" in text:
            # 追加到末尾，保持時間順序
            text = re.sub(r'(## 出現集數\n(?:(?!## ).*\n)*)',
                          lambda m: m.group(1).rstrip('\n') + f'\n{appearance}\n',
                          text, count=1)
        else:
            text += f"\n## 出現集數\n{appearance}\n"
        if "## 故事與知識點" in text:
            text = text.rstrip() + "\n" + story_block
        else:
            text += f"\n## 故事與知識點\n{story_block}"
        entity_path.write_text(text, encoding="utf-8")
    else:
        similar = find_similar_entity(name)
        if similar:
            warn_similar(name, similar)
        content  = f"# {name}\n\n"
        content += "**類型**：聽眾投稿者\n"
        content += f"**首次出現**：{ep_link}\n\n"
        content += f"## 出現集數\n- {ep_link} — {c['title']}\n\n"
        content += f"## 故事與知識點\n{story_block}"
        entity_path.write_text(content, encoding="utf-8")


def update_guest_entity(name: str, ep_id: str, sources_filename: str, g: dict):
    """建立或更新來賓 Entities 頁"""
    # 如果是已知別名，導向正確主名
    canonical = REVERSE_ALIAS.get(name.lower())
    if canonical:
        print(f"  [別名正規化] {name} → {canonical}", flush=True)
        name = canonical
    safe_name   = re.sub(r'[\\/:*?"<>|]', "_", name)
    entity_path = PEOPLE / f"{safe_name}.md"
    ep_ref      = sources_filename.replace(".md", "")
    ep_link     = f"[[{ep_ref}]]"

    share_block = f"\n### {ep_id} — {g['topic']}\n{g['summary']}\n"
    if g["tips"]:
        share_block += "\n**知識點**：\n"
        for t in g["tips"]:
            share_block += f"- {t}\n"

    if entity_path.exists():
        text = entity_path.read_text(encoding="utf-8")
        if ep_id in text:
            return
        appearance = f"- {ep_link} — {g['topic']}"
        if "## 出現集數" in text:
            text = re.sub(r'(## 出現集數\n(?:(?!## ).*\n)*)',
                          lambda m: m.group(1).rstrip('\n') + f'\n{appearance}\n',
                          text, count=1)
        else:
            text += f"\n## 出現集數\n{appearance}\n"
        if "## 分享內容" in text:
            text = text.rstrip() + "\n" + share_block
        else:
            text += f"\n## 分享內容\n{share_block}"
        entity_path.write_text(text, encoding="utf-8")
    else:
        similar = find_similar_entity(name)
        if similar:
            warn_similar(name, similar)
        content  = f"# {name}\n\n"
        content += "**類型**：來賓\n"
        content += f"**首次出現**：{ep_link}\n\n"
        content += f"## 出現集數\n- {ep_link} — {g['topic']}\n\n"
        content += f"## 分享內容\n{share_block}"
        entity_path.write_text(content, encoding="utf-8")


def update_host_entity(host_name: str, ep_id: str, views: list[str]):
    """建立或更新主持人 Entities 頁（老雞.md / 老濕.md）"""
    if not views:
        return
    safe_name   = re.sub(r'[\\/:*?"<>|]', "_", host_name)
    entity_path = PEOPLE / f"{safe_name}.md"

    views_block = f"\n### {ep_id}\n"
    for v in views:
        views_block += f"- {v}\n"

    if entity_path.exists():
        text = entity_path.read_text(encoding="utf-8")
        if ep_id in text:
            return
        if "## 觀點累積" in text:
            text = text.rstrip() + "\n" + views_block
        else:
            text += f"\n## 觀點累積\n{views_block}"
        entity_path.write_text(text, encoding="utf-8")
    else:
        content  = f"# {host_name}\n\n"
        content += "**類型**：主持人\n\n"
        content += f"## 觀點累積\n{views_block}"
        entity_path.write_text(content, encoding="utf-8")


def find_transcript(ep_id: str) -> Path | None:
    """在 Raw/processed/ 所有子資料夾找逐字稿"""
    if not PROCESSED.exists():
        return None
    for folder in PROCESSED.iterdir():
        if not folder.is_dir():
            continue
        candidates = list(folder.glob(f"{ep_id}*.txt"))
        if not candidates:
            continue
        for keyword in ["_ver", "_draft", "_talk"]:
            for f in candidates:
                if keyword in f.name and "摘要" not in f.name:
                    return f
        for f in candidates:
            if "摘要" not in f.name:
                return f
    return None


def get_ep_id_from_sources(filename: str) -> str:
    """肥宅老司機-S3EP100.md → S3EP100"""
    m = re.search(r"(S\d+EP\d+)", filename)
    if m:
        return m.group(1)
    return filename.replace("肥宅老司機-", "").replace(".md", "")


def main():
    wait_for_gpu_idle()
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", type=int, default=0, help="只跑前 N 個未處理集")
    parser.add_argument("--ep",   type=str, default="",  help="只跑特定集數（例如 S3EP100）")
    args = parser.parse_args()

    all_sources = sorted(SOURCES.glob("肥宅老司機-S3EP*.md"))

    if args.ep:
        all_sources = [s for s in all_sources if args.ep in s.name]
    elif args.test:
        pending = [
            s for s in all_sources
            if not is_fully_processed(s.read_text(encoding="utf-8"))
        ]
        all_sources = pending[: args.test]
    else:
        all_sources = [
            s for s in all_sources
            if not is_fully_processed(s.read_text(encoding="utf-8"))
        ]

    print(f"共 {len(all_sources)} 集待處理\n", flush=True)

    for i, sources_path in enumerate(all_sources, 1):
        ep_id = get_ep_id_from_sources(sources_path.name)
        print(f"[{i}/{len(all_sources)}] {ep_id}", flush=True)

        transcript_path = find_transcript(ep_id)
        if not transcript_path:
            print(f"  找不到逐字稿，跳過", flush=True)
            continue

        sources_text = sources_path.read_text(encoding="utf-8")
        transcript   = transcript_path.read_text(encoding="utf-8", errors="ignore")[:6000]
        guests_list  = extract_guests_from_sources(sources_text)
        guests_str   = "\n".join(guests_list) if guests_list else "（本集無嘉賓）"

        print(f"  本集嘉賓：{guests_list or '無'}", flush=True)
        print(f"  送給 Ollama 提取...", flush=True)

        prompt = PROMPT_TEMPLATE.format(
            guests=guests_str,
            sources_page=sources_text[:3000],
            transcript=transcript,
        )

        try:
            raw_result = call_ollama(prompt)
        except Exception as e:
            print(f"  Ollama 錯誤：{e}", flush=True)
            continue

        sections     = parse_sections(raw_result)
        contributors = parse_contributor_blocks(sections["contributors"])
        guests_data  = parse_guest_blocks(sections["guests"])
        hosts_data   = parse_host_blocks(sections["hosts"])

        print(f"  投稿者 {len(contributors)} 人：{[c['name'] for c in contributors]}", flush=True)
        print(f"  來賓   {len(guests_data)} 人：{[g['name'] for g in guests_data]}", flush=True)
        print(f"  主持人觀點：老雞 {len(hosts_data['老雞'])} 條 / 老濕 {len(hosts_data['老濕'])} 條", flush=True)

        update_sources_page(sources_path, contributors, guests_data, hosts_data)

        for c in contributors:
            if is_valid_name(c["name"]):
                update_contributor_entity(c["name"], ep_id, sources_path.name, c)
                print(f"  [投稿者] {c['name']} Entities 已更新", flush=True)

        for g in guests_data:
            if is_valid_name(g["name"]):
                update_guest_entity(g["name"], ep_id, sources_path.name, g)
                print(f"  [來賓]   {g['name']} Entities 已更新", flush=True)

        for host_name in ["老雞", "老濕"]:
            update_host_entity(host_name, ep_id, hosts_data.get(host_name, []))
            if hosts_data.get(host_name):
                print(f"  [主持人] {host_name} Entities 已更新", flush=True)

        time.sleep(1)

    print("\n完成！", flush=True)


if __name__ == "__main__":
    main()
