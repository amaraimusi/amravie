import re
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(r"E:\backup_kenji\mov")
OUT = Path(r"C:\Users\user\git\amravie\mini_tomato_candidates.txt")
DEST = ROOT / "n175"
DB = DEST / "mini_tomato_scenes.sqlite"
REPORT = DEST / "mini_tomato_scenes.txt"
TARGET = re.compile(r"ミニ\s*[・･]?\s*トマト|プチ\s*トマト")
TIME = re.compile(r"(\d\d):(\d\d):(\d\d)[,.](\d{3})\s*-->\s*(\d\d):(\d\d):(\d\d)[,.](\d{3})")


def seconds(parts):
    h, m, s, ms = map(int, parts)
    return h * 3600 + m * 60 + s + ms / 1000


def stamp(value):
    ms = round((value - int(value)) * 1000)
    total = int(value)
    h, total = divmod(total, 3600)
    m, s = divmod(total, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(path):
    text = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    entries = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        time_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            continue
        match = TIME.search(lines[time_index])
        if not match:
            continue
        content = " ".join(lines[time_index + 1 :])
        content = re.sub(r"<[^>]+>", "", content).strip()
        entries.append({"start": seconds(match.groups()[:4]), "end": seconds(match.groups()[4:]), "text": content})
    return entries


def preferred_srt(folder):
    code = folder.name
    choices = [folder / f"{code}ja.srt", folder / f"{code}.srt"]
    for choice in choices:
        if choice.exists():
            return choice
    files = sorted(p for p in folder.glob("*.srt") if "old" not in p.name.lower() and "コピー" not in p.name)
    return files[0] if files else None


SUMMARIES = [
    "暑さで生育不良だった株が台風でさらに弱り、被害状況を観察している。",
    "台風から約10日後も株が回復せず、品種自体の耐暑性不足を疑い、次回は耐熱品種を選ぶ方針を語る。",
    "小苗、食害後の再生株、発芽直後の苗、結実株が同時に存在し、生育段階の違いと生命力を見せる。",
    "畑に適応してほぼ自生状態になった株から実を収穫し、人の管理は支柱による補助だけと説明する。",
    "多種類を播種した場所で若い苗を発見し、期待したキュウリに代わってこの株を育てることにする。",
    "発芽したキュウリの隣で育つ株を確認し、混植区画の配置を紹介する。",
    "放任でも育つが、上方向へ誘引すると生育・収穫・手入れがしやすいとして麻ひも誘引を予定する。",
    "無肥料・無農薬・不耕起・雨水のみで多数結実した株を収穫し、古い実から種を絞り出して発酵処理する。",
    "梅雨の草刈りと収穫後、伸びた枝を切って挿し木し、採取済みの種を多品種ミックスへ加える。",
    "採取した種を含むミックス種子を、株が育つ区画へ播く準備をする。",
    "ミニトマトを含むミックス種子を、掘り出したジャガイモ跡の空間へ播く。",
    "梅雨明け後の株の衰弱、挿し木の活着、猛暑期の種採り、次世代苗の発芽までを時系列で観察する。",
    "ゴーヤ主体の無肥料・無農薬・不耕起区画で、ミニトマトも一緒に育てている混植風景。",
    "ショウガと株の間の空きスペースへナス苗を定植し、限られた空間を混植に活用する。",
    "生育した枝を麻ひもで誘引済みの状態を確認し、その後ゴーヤの観察へ移る。",
    "虫に食べられやすいキュウリと対照的に、自然に出た苗が問題なく成長した様子。",
    "約50日前には小株だったものが大きくなった様子を追跡し、暑さの中でも成長継続を確認する。",
    "草の中に見落としていた株を発見し、支柱がないため今後枝が乱れる可能性を述べる。",
    "上部を覆う枝でナスが日陰になったため、ひもで上へ引き上げ、双方の採光と生育を改善する。",
    "夏野菜の茂みを撤去せず、その中へ株を増やして寒い時期の主役へ自然に交代させる省力的な計画。",
    "上へ誘引した株から枝を採り、挿し木に適する9月に株数を増やす計画。",
    "先行して大きく育った株の枝を採取し、挿し木で増殖しようとしている。",
    "切りたての枝を土へ挿し、成功率の高い挿し木で株を増やす。早い実は食用でなく種採り用にする。",
    "涼しい時期の挿し木を観察するが、別株は翌日にしおれ、水やりして回復を待つ。",
    "ゴーヤ、シカクマメ、ツルムラサキ等と枝葉が複雑に絡み合う、協生農法区画の混沌とした状態。",
    "枝葉を束ねて日照と通風を確保し、挿し木苗の周囲へエダマメを播く混植実験。",
    "挿し木苗のそばで粘土団子を作り、食用収穫より生態系形成を重視した区画づくりを語る場面。",
    "挿し木苗側に置いた粘土団子が割れ、葉野菜やニンジンが発芽している様子を確認する。",
    "約50日前に挿した枝の約7割が活着。誘引後に新たな枝を直挿しし、周囲へミックス種子も播く。",
    "シカクマメなどとともに少量収穫し、もっと多く植えておけばよかったと振り返る。",
    "かつて栽培に使った古い支柱を確認し、区画再整備の対象にする。",
    "多くの実を支えてきた古い支柱を、名残惜しみながら撤去する。",
    "複数作物の枝蔓を麻ひもでまとめて誘引し、混植区画の支柱も補強する。",
    "弱い大玉品種と対照的に、ゴーヤの中でも力強く育つミニトマトを観察する。",
    "11月中旬、直挿しした枝が順調に活着。涼しい時期を選んだことが成功要因と考察する。",
    "ミニトマトを含む多種類の蔓が複雑に絡むため、まとめて束ねて管理する。",
    "11月末の寒さの中でも、他の夏野菜とともに青々と支柱を覆っている状態を観察する。",
    "荒れた混植区画を放置する予定だったが、枝の誘引が必要だったことに気づき管理を再開する。",
    "コーヒー若木の周囲でゴーヤ、シカクマメ等と混植している区画全体の紹介。",
    "低温で各作物の成長が止まる中、残ったゴーヤが株の日照・空間を奪う協生栽培の難しさを示す。",
    "冬に株が力を増し青い実を付け始め、春の色づきを期待する。",
    "前年採取の種を冬の土へ播き、10℃以上という発芽条件と低温による発芽遅延・低率を見込む。",
    "播種した覚えのない苗が遅れて自然発芽しているのを発見する。",
    "ジャガイモ収穫跡に自然発芽した複数株を残し、周囲の草を踏んで根切りする。",
    "自然発芽株へ支柱を立て、剪定せず上へ誘引するソバージュ農法で株を大きくする。",
    "ミニトマトを含む複数作物の手入れ・植付・播種を終えた区画のまとめ。",
    "以前は多品種混植だった草地で、現在はミニトマトだけが伸びている様子。",
    "草刈り済み区画の足元で株を確認し、管理した場所の良好な生育を紹介する。",
    "ナスが育たない場所に代わって自然発芽株が現れ、作物の適地差が見える。",
    "池のそばの自然発芽株について、鳥の糞かこぼれ種か由来を推測する。",
    "自然発芽株を安定した4脚支柱へ固定し、空所にゴーヤと追加のミニトマト種を播く。乱れやすい枝を広範囲で支える設計。",
    "冬のジャガイモ区画で苗を発見し、耐寒性を確かめる冬越し実験として残す。",
    "自然発芽株を移植した『1m共生畑』で、ショウガやウリ科など多種類を同所栽培する。",
    "自然発芽株を採苗し、根を切った株も生命力と暖かい気温を頼りに挿し木して、1m共生畑の中心作物にする。",
    "移植後のしおれと回復、自然発芽苗、他作物との生育差を観察し、倒れた枝をピラミッド支柱へ誘引する。",
    "自然発芽株を掘り上げて移植し、その周囲へ複数野菜を配置する小規模共生区画を畑全体へ展開する。",
    "3月下旬、時期をずらして植えた株同士に現れた生育差を比較する。",
    "上部から麻ひもを垂らし、枝を真上へ引き上げる誘引作業。",
    "数日後に実が赤く色づき、その年最初の収穫を行う。",
    "4月、草に囲まれながら伸びる株を4脚支柱と麻ひもで上へ誘引し、結実開始を確認する。",
    "春の端境期に、サヤインゲンとともにごく少量の実を収穫する。",
    "自然発芽株、ナス、ショウガ、サツマイモ等を同じ小区画へ投入する多品種混植。",
    "共生畑でキュウリに続いてミニトマト、その後ゴーヤが伸びると生育順を予測する。",
    "木の下の半日陰でも育つ株と、葉に落ちたクワの実や動物の糞を観察する。",
    "実を付け始めても枝の成長が止まらず、拡張に合わせて4脚支柱を追加する。",
    "他の夏作物とともに順調に生育し、周辺の草や枯木を活用した区画を観察する。",
    "実が小さく必要養分が少ないため、この無肥料寄りの環境へ適応しやすいと考察する。",
    "急枯れ株を青枯れ病の疑いで除去する一方、健全株は次々に赤い実を付け収穫期へ入る。",
    "収穫物と、実の上を移動する見慣れないクモを映し、畑の生態系の豊かさを感じる場面。",
    "背丈の高い草に押されて弱った株のため空間を確保しつつ、草を支柱に使うシカクマメは残す選択的草管理。",
    "畑の各所で結実し、古いナスやシカクマメと同じ場所で共生している様子。",
    "草だらけに見える畑の中で、状態の良い株を確認する。",
    "次々と熟す実を映し、その日の収穫へつなげる場面。",
    "軽量な女竹の4脚支柱は普段の支持には十分だが、台風には弱いため補強する。",
    "台風後に麻ひもで再誘引。周囲の草が風除けとなり、低い位置の株は被害が少なかったと分析する。",
    "ゴーヤや自然薯の蔓の下でも株が育つ現在の混植風景から、2か月前の春の状態へ回想が移る。",
    "長期間にわたり実を付け続ける株を観察し、他の収穫期作物と比較する。",
    "収穫が長く続いているが、株の状態からまもなく終盤に入ると見込む。",
    "ミニトマトの収穫期終了を告げ、主な収穫対象がシカクマメへ交代した季節の転換。",
]

DATE_OVERRIDES = {
    3: ("2024年5月上旬", "字幕に明記"), 8: ("2024年5月上旬", "字幕に明記"),
    9: ("2024年6月中旬", "字幕に明記"), 10: ("2024年6月中旬", "直前の字幕の時系列から推定"),
    11: ("2024年6月中旬", "直前の字幕の時系列から推定"), 12: ("2024年6月下旬〜7月上旬", "字幕に明記"),
    19: ("2024年夏", "字幕に『夏の真っ盛り』と明記"), 21: ("2024年9月", "字幕に明記"),
    35: ("2024年11月中旬", "字幕に明記"), 37: ("2024年11月下旬", "字幕に明記"),
    57: ("2026年3月下旬", "字幕に明記"), 60: ("2026年4月", "字幕に明記"),
    76: ("2026年6月ごろ（末尾で同年4月へ回想）", "字幕の『2か月前の4月』から推定"),
}

def season(month):
    return {12:"冬", 1:"冬", 2:"冬", 3:"早春", 4:"春", 5:"晩春", 6:"初夏", 7:"夏", 8:"盛夏", 9:"初秋", 10:"秋", 11:"晩秋"}[month]

lines = []
records = []
scene_no = 0
for number in range(89, 174):
    folder = ROOT / f"n{number}"
    if not folder.is_dir():
        continue
    srt = preferred_srt(folder)
    if not srt:
        continue
    entries = parse_srt(srt)
    hits = [i for i, entry in enumerate(entries) if TARGET.search(entry["text"])]
    if not hits:
        continue
    groups = []
    for hit in hits:
        if groups and entries[hit]["start"] - entries[groups[-1][-1]]["end"] <= 35:
            groups[-1].append(hit)
        else:
            groups.append([hit])
    expanded = []
    for group in groups:
        lo, hi = max(0, group[0] - 2), min(len(entries) - 1, group[-1] + 2)
        if expanded and entries[lo]["start"] - entries[expanded[-1][1]]["end"] <= 12:
            expanded[-1][1] = hi
        else:
            expanded.append([lo, hi])
    for lo, hi in expanded:
        scene_no += 1
        context = " ".join(entry["text"] for entry in entries[lo : hi + 1])
        modified = datetime.fromtimestamp(srt.stat().st_mtime)
        estimate, basis = DATE_OVERRIDES.get(scene_no, (f"{modified.year}年{modified.month}月ごろ（{season(modified.month)}）", "字幕ファイル更新月を主な手掛かりに推定"))
        records.append({
            "scene_id": scene_no, "video_code": f"n{number}",
            "start_timestamp": stamp(entries[lo]["start"]), "end_timestamp": stamp(entries[hi]["end"]),
            "scene_summary": SUMMARIES[scene_no - 1], "subtitle_excerpt": context,
            "estimated_shooting_period": estimate, "estimation_basis": basis,
            "source_srt": str(srt), "source_modified_at": modified.isoformat(timespec="seconds"),
        })
        lines.extend([
            f"SCENE {scene_no:03d} | n{number} | {stamp(entries[lo]['start'])} --> {stamp(entries[hi]['end'])}",
            f"SOURCE {srt} | modified {srt.stat().st_mtime}",
            context,
            "",
        ])

OUT.write_text("\n".join(lines), encoding="utf-8")
assert len(SUMMARIES) == len(records), (len(SUMMARIES), len(records))
DEST.mkdir(parents=True, exist_ok=True)
if DB.exists():
    DB.unlink()
with sqlite3.connect(DB) as conn:
    conn.execute("""CREATE TABLE mini_tomato_scenes (
        scene_id INTEGER PRIMARY KEY,
        video_code TEXT NOT NULL,
        start_timestamp TEXT NOT NULL,
        end_timestamp TEXT NOT NULL,
        scene_summary TEXT NOT NULL,
        subtitle_excerpt TEXT NOT NULL,
        estimated_shooting_period TEXT,
        estimation_basis TEXT,
        source_srt TEXT NOT NULL,
        source_modified_at TEXT
    )""")
    conn.executemany("""INSERT INTO mini_tomato_scenes VALUES (
        :scene_id, :video_code, :start_timestamp, :end_timestamp, :scene_summary,
        :subtitle_excerpt, :estimated_shooting_period, :estimation_basis,
        :source_srt, :source_modified_at
    )""", records)
    conn.execute("CREATE INDEX idx_mini_tomato_video ON mini_tomato_scenes(video_code)")
    conn.execute("CREATE INDEX idx_mini_tomato_period ON mini_tomato_scenes(estimated_shooting_period)")

report = [
    "ミニトマト関連シーン一覧（n89〜n173）",
    "=" * 44,
    f"収録シーン数: {len(records)}",
    "対象: 実在する n89〜n173 の各ディレクトリ内の SRT（欠番を除く）",
    "注記: タイムスタンプは編集時に余裕を持って切り出せるよう、関連発言の前後字幕を含む。",
    "      撮影時期は字幕の明記を優先し、それ以外は字幕ファイル更新月を手掛かりにした推定。",
    "",
]
for row in records:
    report.extend([
        f"[{row['scene_id']:03d}] {row['video_code']}  {row['start_timestamp']} --> {row['end_timestamp']}",
        f"推定撮影時期: {row['estimated_shooting_period']}（{row['estimation_basis']}）",
        f"場面: {row['scene_summary']}",
        f"字幕抜粋: {row['subtitle_excerpt']}",
        f"出典: {row['source_srt']}",
        "",
    ])
REPORT.write_text("\n".join(report), encoding="utf-8-sig")
print(f"{len(records)} scenes written to {DB} and {REPORT}")
