"""
merge_aliases.py — 合併別名頁面
用法：
  python tools/merge_aliases.py            # 執行全部合併
  python tools/merge_aliases.py --dry-run  # 只列出會做什麼，不實際修改
  python tools/merge_aliases.py --group LASAI  # 只跑指定主名那組

功能：
  1. 把 ALIAS_MAP 裡每組別名合併進主名頁面
     - 合併「出現集數」（去重，按集號排序）
     - 合併「故事與知識點」/「分享內容」（去重，以集號為 key）
     - 更新「首次出現」為最早集號
  2. 刪除別名頁面
  3. 全站替換 [[別名]] → [[主名]]（人物 + 店家 + 地點 + 概念 + 來源）
  4. MOVE_TO_概念：把分類錯誤的頁面移到 概念/
"""

import re
import sys
import json
import shutil
import argparse
import urllib.request
from pathlib import Path

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:27b"


def merge_definitions(main_name: str, main_def: str, alias_defs: list[str],
                      old_names: list[str]) -> str:
    """用 Ollama 把多個定義融合成一段，並把舊名字替換成新名字。"""
    # 先把舊名字替換掉（純文字，非連結）
    def replace_old_names(text: str) -> str:
        for old in old_names:
            text = re.sub(re.escape(old), main_name, text)
        return text

    main_def = replace_old_names(main_def.strip())
    alias_defs = [replace_old_names(d.strip()) for d in alias_defs if d.strip()]

    # 過濾掉與主定義幾乎相同的別名定義
    unique_alias = [d for d in alias_defs if d and d != main_def and len(d) > 10]
    if not unique_alias:
        return main_def  # 別名定義空或重複，直接用主定義

    combined = f"主定義：{main_def}\n\n" + "\n\n".join(
        f"補充定義 {i+1}：{d}" for i, d in enumerate(unique_alias)
    )

    prompt = f"""你是知識庫編輯。請把以下幾段關於「{main_name}」的定義，融合成一段流暢的繁體中文定義（100 字以內）。
只輸出融合後的定義文字，不要標題、不要編號、不要解釋。

{combined}"""

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1}
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            OLLAMA_URL, data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())["response"].strip()
        return result if result else main_def
    except Exception as e:
        print(f"    ⚠️  Ollama 定義融合失敗（{e}），保留原定義")
        return main_def

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE       = Path(__file__).parent.parent
WIKI       = BASE / "Wiki"
PEOPLE     = WIKI / "人物"
VENUES     = WIKI / "店家"
PLACES     = WIKI / "地點"
CONCEPTS   = WIKI / "概念"
SOURCES    = WIKI / "來源"
# 所有可能放頁面的資料夾（供 find_file 搜尋）
ALL_PAGE_DIRS = [PEOPLE, VENUES, PLACES, CONCEPTS]

# ─────────────────────────────────────────────────────────────
# 合併對照表：{主名: [別名1, 別名2, ...]}
# 主名 = 保留的頁面名稱（不含 .md）
# ─────────────────────────────────────────────────────────────
ALIAS_MAP = {
    # ── 大阪新地（新地 = 遊廓地區，≠ 新帝；「新帝」為 Ollama 常見誤寫）────
    "飛田新地": ["飛田新帝"],
    "松島新地": ["松島新帝", "松島", "松島 (Matsushima)"],
    # ── 喇賽（LASAI）組 — 中文為正規名，英文為別名 ────────────
    "喇賽": ["LASAI", "LASAY", "LASAN", "LASAGNE", "LaSalle",
             "喇賽哥", "喇塞", "啦塞", "拉塞", "打賽"],  # 打賽=喇賽 音近誤字

    # ── 小瓢蟲 組 ──────────────────────────────────────────────
    "小瓢蟲": ["竹科小瓢蟲", "老棒(小瓢蟲)", "老棒 (小瓢蟲)",
               "足科小飄蟲", "竹科小嫖蟲", "小飄蟲", "臺灣上湧小飄蟲"],

    # ── 地點 ──────────────────────────────────────────────────
    "西勢美": ["西四美"],     # 西四美 = 台語音近誤寫，正確為西勢美

    # ── 人物 ──────────────────────────────────────────────────
    "吉米": ["Jimmy", "Jimmy哥", "吉米 (Jimmy)", "吉米(Jimmy)",
              "君米哥", "居米哥"],               # 君米/居米 均為吉米音近誤字
    "魯邦": ["魯邦Mike", "魯邦麥可"],
    "Mario": ["瑪莉歐(Mario)", "馬利歐(Mario)",
              "瑪莉歐 (Mario)", "馬利歐 (Mario)", "瑪麗歐 (Mario)"],
    "安迪": ["安滴啦", "安滴老", "安迪烙", "安迪老"],
    "中年大叔貝斯手": ["中年大叔背死手"],
    "小書童": ["小書桶"],              # 桶(tǒng) vs 童(tóng) 音近
    "Scott": ["史考特"],
    "Steven": ["史蒂芬", "史蒂芬大師"],
    "詹姆士": ["詹姆", "James"],
    "老馬哥": ["老馬"],
    "老雞": ["老機", "老基"],              # 老機/老基 = 老雞（主持人音近字）
    "亞當叔叔": ["亞當士", "亞當斯大人"],
    "Sayuri": ["Sayuri Complex"],
    "基德": ["怪盜基德"],
    "Lawrence": ["勞倫斯", "Lawrence 越南導遊服務"],
    "小鐘": ["小鐘 (sohoboy0629)", "Soho Boy 0629"],

    # ── 店家 ──────────────────────────────────────────────────
    "伊林龍筋": ["一一", "一一老師", "一一老師龍筋按摩",
                 "伊林", "伊林農金店", "伊林農金",
                 "伊林龍京店", "伊林龍京",             # 龍京=龍筋 音近字
                 "伊林龍津店", "伊林龍津",             # 龍津=龍筋 音近字
                 "伊琳龍筋店", "伊琳龍筋"],            # 林/琳 異體字
    "Wonder Massage": ["Wonder"],          # 不合併「Wonder Massage 對面破舊店」
    "廣州台琴": ["廣州台勤", "廣州臺琴"],
    "烏日儷晶養生館": ["烏日麗金", "烏日麗境", "烏日利京", "烏日郵輪",
                       "烏日麗晶",                        # 客人常用暱稱（郵輪 = 儷晶）
                       "烏日利金", "烏日立金",            # 麗金 的音近誤字
                       "烏日利晶", "烏日力晶"],           # 儷晶 的音近誤字
    "道": ["道 / Donuts", "Donuts"],        # 首爾江南高端店；Donuts 為同店舊稱/別稱
    "永登埔": ["永登埔紅燈區", "永登埔玻璃屋", "永登埔玻璃櫥窗"],  # 同一地區，Ollama 拆成多頁
    "伊利": ["伊利論壇"],                   # 同一論壇平台
    "天使城 GoGo Bar": ["天使城 Go Go Bar"],
    "Second Floor": ["Second Flow Bar"],
    "永珍": ["萬象"],                       # 寮國首都 Vientiane
    "富都": ["富都(Fu Du)", "富都 Boss KTV", "富都酒店"],
    "吉原": ["吉原泡泡浴店家", "吉原高級店"],
    "內壢按摩抓龍筋工作室": ["內力按摩抓龍筋工作室"],   # 內力=內壢 音近地名誤字
    "津久診所": ["金九診所"],                            # 金九=津久 音近誤字
    "永心藥局": ["永新中西藥局", "永新中心藥局", "永勳藥局"],  # 同一家藥局，永勳=逐字稿誤寫，Ollama 拆成兩頁
    "Cherry": ["Cherry (櫻桃)"],            # 越南同一家店
    "大可汗": ["大可寒 (摸摸茶)", "大可寒(摸摸茶)"],
    "五月花": ["五月花 KTV"],

    # ── 地名 ──────────────────────────────────────────────────
    "寮國": ["老撾"],                       # Laos：台灣叫寮國，大陸叫老撾
    "永登埔": ["永登浦"],                   # 首爾永登浦區，埔/浦錯字
    "台灣阿誠": ["臺灣阿誠"],               # 台/臺 異體字

    # ── 越南奧黛店（áo dài）── 奧/澳 音近，黛/代 音近 ──────────
    "奧黛店": ["奧代店", "澳代店"],
    "奧黛": ["奧代"],                  # Concepts/ 裡的概念頁

    # ── 曼谷蛇美咖啡 ── 蛇/舍/捨 音近 ──────────────────────────
    "蛇美咖啡": ["舍美", "捨美", "舍美 (音譯)"],

    # ── 地名：芭提雅（Pattaya）── 達(ㄉㄚ) 誤聽為 提(ㄊㄧ) ─────
    "芭提雅": ["芭達雅", "芭堤雅", "Pattaya", "帕塔亞", "帕達亞"],
    "芭提雅 GoGo Bar": ["芭達雅 GoGo Bar"],

    # ── 芭提雅六巷（Soi 6）── 6/六 阿拉伯/中文數字（不加 SOI6，太通用）──
    "六巷": ["6巷"],

    # ── 胡志明市（Ho Chi Minh City）── 市/城 後綴多餘 ────────────
    "胡志明": ["胡志明市", "胡志明城"],

    # ── 圖山（越南 Đồ Sơn，海防附近海灘城市）── 屠/土/圖 音近 ───
    "圖山": ["屠山", "土山"],

    # ── 長平（東莞）── 坪/平 音近錯字 ───────────────────────────
    "長平": ["長坪", "東莞長坪", "長平區"],

    # ── 台灣地名別名 ─────────────────────────────────────────────
    "萬華區": ["萬華"],                    # 台北萬華區
    "林森北": ["林森北路"],               # 台北林森北路
    "Tijuana": ["提華納", "提瓦那", "蒂華納", "蒂瓦那"],  # Tijuana 各種音譯
    "中壢": ["桃園中壢"],                  # 桃園中壢 = 中壢
    "中國": ["中國大陸"],                  # 台灣說法
    "普吉": ["普吉島"],                    # 泰國 Phuket
    "芽籠": ["牙籠", "Geylang"],           # 新加坡 Geylang
    "拉斯維加斯": ["Vegas", "維加斯"],     # Las Vegas
    "洛杉磯": ["LA"],                      # LA 縮寫
    "新北": ["新北市"],                    # 多餘「市」後綴
    "台北": ["台北市"],                    # 多餘「市」後綴
    "烏日": ["台中烏日"],                  # 冗餘地名前綴
    "曼谷": ["泰國曼谷"],                  # 冗餘國名前綴
    "海防": ["越南海防"],                  # 冗餘國名前綴
    "湖口": ["新竹湖口"],                  # 冗餘地名前綴
    "溫哥華": ["加拿大溫哥華"],            # 冗餘國名前綴
    "京拿都": ["金拿都"],                  # 吉隆坡 Chow Kit，京/金 音近
    "東京": ["日本東京", "Tokyo"],          # 冗餘前綴 / 英文名
    "大阪": ["日本大阪"],                  # 冗餘前綴
    "松島新地": ["松島"],                  # 大阪松島新地，Ollama 常漏「新地」
    "永登埔": ["永登浦", "永登普"],        # 首爾永登浦區多種誤字
    # Nana Plaza 有獨立頁面，只需合併拼寫變體連結（不刪頁）
    "Nana Plaza": ["NANA Plaza", "Nana 廣場"],  # 注意：Nana 單獨可能指其他店，不合入
    # 烏日儷晶養生館 已在 ── 店家 ── 區塊定義（含全部別名）
    "龍津店": ["龍津"],                    # 台中龍津店
    "伊林龍筋": ["伊林龍京店", "伊林龍京", "伊林龍經店",
                 "伊林龍鯨店", "伊林龍鯨"],               # 鯨=筋 音近誤字
    "福岡": ["福岡中州"],                  # 中州是福岡的紅燈區，合入福岡
    "Mr. Lee": ["Mr.Lee"],                 # 人名格式統一
    "巴塞隆納": ["巴塞"],                  # 西班牙城市

    # ── 概念 音近字錯誤 / 合併 ────────────────────────────────
    "走腎不走心": ["走勝不走心"],          # 腎/勝 音近
    "龍筋": ["龍經", "隆經", "龍精", "龍頸按摩"],  # 筋/經/隆/精/頸 音近；龍精按摩定義與龍筋相同
    "抓龍筋": ["抓龍精", "按龍機", "按龍經"],  # 精/機/經 均為筋的誤字
    "毒龍": ["獨龍", "獨龍磚", "獨龍鑽", "賭龍"],  # 獨/毒/賭 同音
    "共筆": ["共比"],                          # 比/筆 同音
    "老點": ["老店"],                          # 店/點 同音
    "口爆": ["口報"],
    "口爆店": ["口報店"],
    "外國人料金": ["外國人料理"],
    "武鬥派": ["五豆派"],                      # 五豆/武鬥 音近
    "泰洗": ["太習"],                          # 太習=泰洗 誤字
    "4P": ["四批"],                            # 批/P 音近
    "低能量震波": ["正波與震波"],              # 同概念，名稱誤寫
    "舔狗": ["田狗"],                          # 田/舔 音近
    "日按": ["日暗"],                          # 暗/按 音近
    "日洗": ["日襲"],                          # 日襲=日洗 誤字
    "Heart to Heart": ["哈土哈", "哈圖"],      # 音譯誤字
    "客評": ["客品"],                          # 評/品 音近
    "偷時": ["偷師"],                          # 師/時 音近
    "素股": ["豎鼓"],                          # 豎鼓=素股 誤字
    "聖水": ["腎水"],                          # 腎/聖 音近
    "龍宮": ["農工"],                          # 農工=龍宮 誤字
    "雞頭": ["機頭"],                          # 機/雞 同音
    "清水溝": ["親水溝"],                      # 親/清 音近
    "短鐘": ["短中"],                          # 中/鐘 音近
    "鵝寶寶": ["餓寶寶"],                      # 餓/鵝 同音
    "輕功": ["親工"],                          # 親/輕 音近，均指口交服務
    "半凹全": ["半拗拳"],                      # 拗/凹 音近
    "長鍾": ["長盅 _ 短盅", "常中", "長中"],    # 長盅=長鍾；常/長、長/長中 音近
    "短鐘": ["短中"],                          # 中/鐘 音近（短中已在上方，此為備援）

    # ── Concepts 重複頁合併 ───────────────────────────────────
    "脫衣舞酒吧": ["脫衣舞酒吧 (Strip Club)"],

    # ── 2026-05-19 補救：路徑 bug 造成的重複概念頁 ───────────
    # enrich_concepts 路徑 bug 修前，0.3/0.5/1 被拆成多個 stub
    "0.3_0.5_1": ["0.3 _ 0.5 _ 1", "0.3 _ 0.5", "0.5 _ 1"],

    # ── 2026-05-19 補救：主持人「老師」= 「老濕」(同音字) ────
    "老濕": ["老師", "老司"],

    # ── 2026-05-19 補救：人物/店家/地點別名 ─────────────────────
    "東莞冠希（Beaky）": ["Beaky", "東莞冠希"],   # 現更名為 Beaky
    "烏日利京": ["烏日利晶", "烏日利晶按摩", "烏日利菁"],  # 烏日店家音近字（利京/利晶/利菁 同音 lì jīng）
    "索格": ["索格學園", "索閣", "索閣學園"],              # 線上預約平台，不是實體店
    "芽籠": ["牙籠"],                              # 新加坡 Geylang 音近字

    # ── 2026-05-19 人物合併 ────────────────────────────────────
    "艾力克斯": ["艾莉克斯"],                      # Alex 音譯不同寫法

    # ── 2026-05-19 店家合併（括號版刪除）────────────────────────
    "Caviar": ["Caviar (魚子醬)"],                 # 同一家曼谷店
    "Vendone Hotel": ["Vendone Hotel (VD Hotel)"], # 同一家胡志明市店

    # ── 2026-05-19 概念合併 ────────────────────────────────────
    "水箭龜": ["水見鬼"],    # 同義詞，Ollama 音近字
    "141": ["141論壇"],      # 同一平台，論壇即平台本身

    # ── 2026-05-25 人物別名（S3EP264）────────────────────────────
    "大口袋": ["大摳呆"],                        # 台語「大摳呆」= 大支很胖，同音字寫成大口袋
    "小藥師": ["洨藥師", "小鑰匙"],              # 洨藥師=台語暱稱（洨=臭），小鑰匙=逐字稿誤寫
    "私台": ["師台", "師臺", "私檯"],             # 私檯/私台=固定坐台制，師台=逐字稿誤寫（逐字稿「私」常被辨識成「師」）
    "公台": ["攻台", "公檯"],                     # 公台/公檯=公開輪轉坐台（公家的概念，妹子輪流換），攻台=逐字稿誤字

    # ── 2026-05-25 名稱修正（用戶確認）────────────────────────────
    "八爺": ["巴爺"],                             # 八/巴 同音 bā yé，逐字稿誤字，同一來賓
    "無心插柳柳橙汁": ["無心插柳柳成枝", "無心插柳柳成蔭"],  # 橙汁/成枝 同音（chéng zhī），pun 梗名，whisper 選錯字
    "富國 KTV": ["復國 KTV", "復國 (Phu Quoc)"],  # 富國=Phú Quốc 富國島，復國=逐字稿誤字

    # ── 2026-05-25 人物合併 ────────────────────────────────────
    "加藤鷹": ["加藤英"],                        # 英/鷹 同音誤字（日本 AV 男優課程講師）
    "五木旅人": ["五目旅人"],                    # 目/木 音近誤字
    "店小兒": ["電小二"],                        # 電/店、二/兒 音近誤字
    "月光光": ["岳光光"],                        # 岳/月 同音誤字
    "肆意妄為": ["四億萬為"],                    # 四/肆、億/意、萬/妄 音近誤字（寮國攻略來賓）
    "老王": ["雞頭老王"],                        # 雞頭老王為全稱，老王為常用稱呼
    "優君": ["悠君"],                            # 悠/優 同音誤字（日本風俗業深度玩家）
    "科比": ["Coby"],                            # Coby 英文名，科比為中文名
    "包養網": ["包洋網"],                        # 洋/養 同音誤字（成人媒合平台）
    "艋舺公園": ["蒙甲公園"],                   # 蒙甲=艋舺 音近誤字（台北萬華地標）

    # ── 來源頁連結格式修正（空格→連字號）──────────────────────
    "肥宅老司機-S3EP2": ["肥宅老司機 S3EP2"],
}

# ─────────────────────────────────────────────────────────────
# 把分類錯誤的概念頁移到 概念/
# ─────────────────────────────────────────────────────────────
MOVE_TO_CONCEPTS = [
    "GoGo Bar",
    "外送茶",
    "KTV",
    "半套店",
    "脫衣舞酒吧",
    "定點",
    "公寓式酒店",
    "人妖店",
    "洗浴店 (桑拿)",
    "外圍",
    "愛情賓館 (Love Hotel)",
    "泡泡浴店家",
    # 已刪除（2026-05-18 深度整理合併）：
    # "GoGo Bar (如 Rainbow 3, Nana Plaza)" → 合入 GoGo Bar.md
    # "KTV酒店" / "KTV 酒店 (一般)"         → 合入 KTV.md
    # "脫衣舞酒吧 (Strip Club)"              → 合入 脫衣舞酒吧.md
    # "定點 (酒店)"                          → 合入 定點.md
    # "外圍 (獨立)"                          → 合入 外圍.md
]


# ═══════════════════════════════════════════════════════════════
# 工具函數
# ═══════════════════════════════════════════════════════════════

def ep_num(ep_ref: str) -> int:
    """從 [[肥宅老司機-S3EP42]] 或 [[S3EP42]] 提取集號整數，找不到回傳 9999"""
    m = re.search(r'EP(\d+)', ep_ref, re.IGNORECASE)
    return int(m.group(1)) if m else 9999


def find_file(name: str) -> Path | None:
    """在 人物/ 店家/ 地點/ 概念/ 找指定名稱的 .md 檔"""
    for folder in ALL_PAGE_DIRS:
        p = folder / f"{name}.md"
        if p.exists():
            return p
    return None


def parse_sections(content: str) -> dict:
    """
    把 markdown 內容切成 {section_title: section_text} 的 dict。
    第一個 # 標題前的 header 部分存在 key '__header__'。
    """
    sections = {}
    current_title = "__header__"
    current_lines = []

    for line in content.splitlines(keepends=True):
        m = re.match(r'^(#{1,3})\s+(.+)', line)
        if m and m.group(1) in ("##", "###"):
            sections[current_title] = "".join(current_lines)
            current_title = line.rstrip()
            current_lines = []
        else:
            current_lines.append(line)

    sections[current_title] = "".join(current_lines)
    return sections


def extract_ep_bullets(section_text: str) -> dict:
    """
    從「## 出現集數」段落，提取 {集號int: '整行文字'} dict。
    例：'- [[肥宅老司機-S3EP42]] — 東莞體驗' → {42: '該行'}
    """
    result = {}
    for line in section_text.splitlines():
        if not line.strip().startswith("-"):
            continue
        refs = re.findall(r'\[\[.*?EP(\d+).*?\]\]', line, re.IGNORECASE)
        if refs:
            ep = int(refs[0])
            result[ep] = line
    return result


def extract_story_sections(sections: dict) -> dict:
    """
    從 sections dict 提取 '### S3EPxx' 層級的子段落，
    回傳 {集號int: '### 標題\n內容'} dict。
    """
    result = {}
    for title, body in sections.items():
        if not title.startswith("###"):
            continue
        m = re.search(r'EP(\d+)', title, re.IGNORECASE)
        if m:
            ep = int(m.group(1))
            result[ep] = title + "\n" + body
    return result


def rebuild_content(main_name: str, header: str,
                    ep_bullets: dict, story_sections: dict,
                    extra_sections: dict) -> str:
    """
    從各部分重新組合最終 markdown 內容。
    - header: # 標題 + **類型** 等 metadata
    - ep_bullets: {集號: 行文字}
    - story_sections: {集號: ### 段落文字}
    - extra_sections: 其他非集號的 ## 段落 {## 標題: 文字}
    """
    parts = []

    # ── header（更新首次出現集號）──
    if ep_bullets:
        earliest = min(ep_bullets.keys())
        # 找到最早的完整 [[連結]]（從 bullet 裡取）
        earliest_line = ep_bullets[earliest]
        earliest_ref = re.search(r'\[\[.*?\]\]', earliest_line)
        if earliest_ref:
            ref_str = earliest_ref.group(0)
            header = re.sub(
                r'\*\*首次出現\*\*：\[\[.*?\]\]',
                f'**首次出現**：{ref_str}',
                header
            )
    parts.append(header.rstrip())

    # ── 出現集數 ──
    if ep_bullets:
        sorted_eps = sorted(ep_bullets.keys())
        bullets = "\n".join(ep_bullets[e] for e in sorted_eps)
        parts.append(f"\n## 出現集數\n{bullets}")

    # ── 故事與知識點 ──
    if story_sections:
        sorted_stories = sorted(story_sections.keys())
        story_text = "\n\n".join(story_sections[e].rstrip() for e in sorted_stories)
        parts.append(f"\n## 故事與知識點\n\n{story_text}")

    # ── 其他段落（保留非集號的 ## 段落，如「簡介」「相關人物」等）──
    for title, body in extra_sections.items():
        if body.strip():
            parts.append(f"\n{title}\n{body.rstrip()}")

    return "\n".join(parts) + "\n"


# ═══════════════════════════════════════════════════════════════
# 核心操作
# ═══════════════════════════════════════════════════════════════

def update_wiki_links(old_names: list[str], new_name: str, dry_run: bool):
    """全站替換 [[別名]] → [[主名]]，掃 Wiki/ 所有 .md。
    同時處理衍生複合詞：若 [[舊名店]] 不存在但 [[新名店]] 存在，也一併替換。"""
    # 建立所有頁面名稱集合，用來判斷衍生複合詞是否有效
    existing_pages: set[str] = set()
    for d in ALL_PAGE_DIRS + [SOURCES]:
        for p in d.glob("*.md"):
            existing_pages.add(p.stem)

    # 建立完整替換對照表（含衍生複合詞）
    replace_map: dict[str, str] = {}
    for old in old_names:
        replace_map[old] = new_name
        # 衍生複合詞：老名+後綴 → 新名+後綴（僅當目標頁存在時）
        for suffix in ("店", "按摩", "服務", "課"):
            derived_old = old + suffix
            derived_new = new_name + suffix
            if derived_new in existing_pages:
                replace_map[derived_old] = derived_new

    changed_files = 0
    for md_file in WIKI.rglob("*.md"):
        try:
            original = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        updated = original
        for old, new in replace_map.items():
            # 替換 [[old]] 和 [[old|...]] 兩種形式
            updated = re.sub(
                r'\[\[' + re.escape(old) + r'(\|[^\]]+)?\]\]',
                f'[[{new}]]',
                updated
            )
        if updated != original:
            changed_files += 1
            if not dry_run:
                md_file.write_text(updated, encoding="utf-8")
            else:
                print(f"    🔗 [dry] 會更新連結：{md_file.relative_to(BASE)}")
    return changed_files


def merge_group(main_name: str, aliases: list[str], dry_run: bool) -> bool:
    """合併一組別名進主名頁面"""
    main_path = find_file(main_name)

    # 收集所有別名內容
    alias_data = []   # [(alias_name, path, content)]
    for alias in aliases:
        p = find_file(alias)
        if p is None:
            print(f"    ⚠️  找不到 {alias}.md，跳過")
            continue
        try:
            content = p.read_text(encoding="utf-8")
            alias_data.append((alias, p, content))
        except Exception as e:
            print(f"    ❌ 讀取失敗 {alias}.md：{e}")

    if not alias_data and main_path is None:
        print(f"    ❌ 主名和所有別名都找不到，跳過")
        return False

    # 讀或建立主名頁面
    source_path_to_delete = None  # 用來建立主名的原始別名檔（建立後要刪除）
    if main_path and main_path.exists():
        main_content = main_path.read_text(encoding="utf-8")
    else:
        # 用第一個找到的別名內容建立主名頁面
        first_alias, first_path, first_content = alias_data[0]
        main_content = re.sub(
            r'^# .+', f'# {main_name}', first_content, count=1, flags=re.MULTILINE
        )
        alias_data = alias_data[1:]  # 第一個已用來建立主名，不再重複合併
        main_path = first_path.parent / f"{main_name}.md"
        source_path_to_delete = first_path  # 建立完要刪除原始別名檔
        print(f"    🆕 主名頁面不存在，從 {first_alias}.md 建立")

    # 解析主名頁面
    main_sections = parse_sections(main_content)
    header = main_sections.get("__header__", "")

    # 合併出現集數
    combined_eps = {}
    for sec_title, sec_body in main_sections.items():
        if "出現集數" in sec_title:
            combined_eps.update(extract_ep_bullets(sec_body))

    # 合併故事段落
    combined_stories = extract_story_sections(main_sections)

    # 收集其他 ## 段落（非出現集數、非故事）
    other_sections = {}
    for title, body in main_sections.items():
        if title == "__header__":
            continue
        if "出現集數" in title or title.startswith("###"):
            continue
        if title.startswith("## 故事") or title.startswith("## 分享"):
            continue
        other_sections[title] = body

    # 收集別名的定義（供之後 Ollama 融合）
    alias_definitions = []

    # 逐一把別名內容合併進來
    for alias_name, alias_path, alias_content in alias_data:
        alias_sections = parse_sections(alias_content)

        # 合併集數
        for sec_title, sec_body in alias_sections.items():
            if "出現集數" in sec_title:
                new_eps = extract_ep_bullets(sec_body)
                for ep_num_key, ep_line in new_eps.items():
                    if ep_num_key not in combined_eps:
                        combined_eps[ep_num_key] = ep_line

        # 合併故事段落
        new_stories = extract_story_sections(alias_sections)
        for ep_key, story_text in new_stories.items():
            if ep_key not in combined_stories:
                combined_stories[ep_key] = story_text

        # 收集別名定義
        for title, body in alias_sections.items():
            if "定義" in title and body.strip():
                alias_definitions.append(body.strip())

        # 合併其他段落（定義另外處理，其餘段落只補缺）
        for title, body in alias_sections.items():
            if title == "__header__" or "出現集數" in title:
                continue
            if title.startswith("###"):
                continue
            if title.startswith("## 故事") or title.startswith("## 分享"):
                continue
            if "定義" in title:
                continue  # 定義另外處理
            if title not in other_sections and body.strip():
                other_sections[title] = body

    # 融合定義（有別名定義才呼叫 Ollama）
    def_key = next((k for k in other_sections if "定義" in k), "## 定義")
    main_def = other_sections.get(def_key, "").strip()
    if alias_definitions:
        merged_def = merge_definitions(main_name, main_def, alias_definitions, aliases)
        other_sections[def_key] = "\n" + merged_def + "\n"
    elif main_def:
        # 即使沒別名定義，也把舊名字替換掉
        fixed = main_def
        for old in aliases:
            fixed = re.sub(re.escape(old), main_name, fixed)
        if fixed != main_def:
            other_sections[def_key] = "\n" + fixed + "\n"

    # 重新組合內容
    new_content = rebuild_content(
        main_name, header, combined_eps, combined_stories, other_sections
    )

    # 寫入主名頁面
    if not dry_run:
        main_path.write_text(new_content, encoding="utf-8")
        print(f"    ✅ 主名頁面已更新：{main_name}.md（{len(combined_eps)} 集）")

        # 刪除別名頁面（含用來建立主名的原始別名檔）
        to_delete = list(alias_data)
        if source_path_to_delete:
            to_delete.insert(0, (source_path_to_delete.stem, source_path_to_delete, ""))
        for alias_name, alias_path, _ in to_delete:
            try:
                alias_path.unlink()
                print(f"    🗑️  已刪除：{alias_name}.md")
            except Exception as e:
                print(f"    ❌ 刪除失敗 {alias_name}.md：{e}")
    else:
        alias_names = [a for a, _, _ in alias_data]
        if source_path_to_delete:
            alias_names.insert(0, source_path_to_delete.stem)
        print(f"    [dry] 主名：{main_name}.md，合併後 {len(combined_eps)} 集")
        print(f"    [dry] 會刪除：{alias_names}")

    # 全站更新連結
    all_old_names = aliases  # 所有別名（包括不存在的，以防 Sources 裡有提及）
    link_count = update_wiki_links(all_old_names, main_name, dry_run)
    print(f"    🔗 連結更新：{link_count} 個檔案")

    return True


def move_to_concepts(name: str, dry_run: bool):
    """把人物/店家/地點裡分類錯誤的概念頁移到 概念/"""
    src = find_file(name)
    dst = CONCEPTS / f"{name}.md"

    if src is None:
        print(f"    ⚠️  找不到 {name}.md，跳過")
        return
    if dst.exists():
        print(f"    ℹ️  概念/{name}.md 已存在，跳過")
        return

    if not dry_run:
        shutil.move(str(src), str(dst))
    print(f"    {'[dry] ' if dry_run else ''}📂 {name}.md：{src.parent.name} → 概念/")


# ═══════════════════════════════════════════════════════════════
# 主程式
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="合併別名 Entity 頁面")
    parser.add_argument("--dry-run", action="store_true",
                        help="只列出計劃，不實際修改任何檔案")
    parser.add_argument("--group", type=str, default="",
                        help="只跑指定主名那一組，例如 --group LASAI")
    parser.add_argument("--no-move", action="store_true",
                        help="跳過 Entities → Concepts 的搬移步驟")
    args = parser.parse_args()

    if args.dry_run:
        print("🔍 DRY RUN 模式 — 不會修改任何檔案\n")

    # ── Step 1：合併別名 ──────────────────────────────────────
    print("=" * 60)
    print("Step 1：合併別名頁面")
    print("=" * 60)

    # 去重（ALIAS_MAP 裡 LASAI 定義了兩次，取最後一次）
    alias_map = {}
    for main, aliases in ALIAS_MAP.items():
        alias_map[main] = aliases

    merged = skipped = 0
    for main_name, aliases in alias_map.items():
        if args.group and main_name != args.group:
            continue
        print(f"\n▶ {main_name} ← {aliases}")
        ok = merge_group(main_name, aliases, args.dry_run)
        if ok:
            merged += 1
        else:
            skipped += 1

    print(f"\n合併完成：{merged} 組成功，{skipped} 組跳過")

    # ── Step 2：搬移分類錯誤的頁面 ───────────────────────────
    if not args.no_move:
        print("\n" + "=" * 60)
        print("Step 2：Entities → Concepts 分類修正")
        print("=" * 60)
        for name in MOVE_TO_CONCEPTS:
            move_to_concepts(name, args.dry_run)

    print("\n🎉 全部完成！")
    if not args.dry_run:
        print("建議跑一次 health check 確認結果：python tools/health_check.py")


if __name__ == "__main__":
    main()
