from __future__ import annotations

import html
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

MOV = Path(r"E:\backup_kenji\mov")
DOCS = Path(r"E:\backup_kenji\mov_docs")
OUT = MOV / "01_farm_archive"
DB = OUT / "farm_archive.sqlite"
TEXT = OUT / "farm_archive.txt"

MIN_CODE, MAX_CODE = 8, 173
CODE_RE = re.compile(r"^n(\d+)([A-Za-z][A-Za-z0-9_-]*)?", re.I)
TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}[,.]\d{3}\s+-->")
TAG_RE = re.compile(r"<[^>]+>")
DATE_FULL_RE = re.compile(r"(?:(20\d{2})[年/.-])?\s*(1[0-2]|0?[1-9])月(?:\s*(3[01]|[12]\d|0?[1-9])日)?")
SEASON_RE = re.compile(r"(早春|春先|春|初夏|梅雨|盛夏|夏|初秋|秋口|秋|晩秋|初冬|冬)")

AG_WORDS = (
    "自然農", "畑", "農", "栽培", "育て", "種", "苗", "植", "収穫", "畝", "土", "草", "野菜",
    "果実", "果樹", "発芽", "播種", "堆肥", "肥料", "耕", "水やり", "剪定", "花", "実", "根",
    "ナス", "トマト", "キュウリ", "大根", "ダイコン", "豆", "芋", "イモ", "ゴーヤ", "稲", "ニンジン",
)
SKIP_PHRASES = ("ご視聴", "チャンネル登録", "ありがとうございました", "Thank you", "Subscribe")


def read_text(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            pass
    return path.read_text(encoding="utf-8", errors="replace")


def code_parts(name: str):
    m = CODE_RE.match(name)
    if not m:
        return None
    number = int(m.group(1))
    if not MIN_CODE <= number <= MAX_CODE:
        return None
    suffix = m.group(2) or ""
    return f"n{number}{suffix.lower()}", number, suffix.lower()


def subtitle_lines(path: Path) -> list[str]:
    text = read_text(path).replace("\\N", " ")
    lines = []
    for raw in text.splitlines():
        line = html.unescape(TAG_RE.sub("", raw)).strip()
        if not line or line.isdigit() or TIME_RE.match(line):
            continue
        line = re.sub(r"\s+", " ", line)
        lines.append(line)
    # Most files alternate Japanese and a translation. Keep lines containing Japanese.
    japanese = [x for x in lines if re.search(r"[ぁ-んァ-ヶ一-龠々]", x)]
    return japanese or lines


def subtitle_priority(path: Path, code: str) -> tuple:
    stem = path.stem.lower()
    # Exact source subtitle first, then Japanese subtitle; translations and copies last.
    exact = 0 if stem == code else 1
    japanese = 0 if stem in (code, code + "ja") else 1
    copy_or_old = 1 if ("コピー" in stem or "old" in stem) else 0
    nesting = len(path.parts)
    return (exact, japanese, copy_or_old, nesting, -path.stat().st_mtime)


def infer_date(lines: list[str], modified: datetime) -> tuple[str, str, str]:
    # Date captions are normally near the beginning; later dates may describe future harvests.
    opening = lines[: max(25, min(80, len(lines) // 3))]
    for line in opening:
        m = DATE_FULL_RE.search(line)
        if not m:
            continue
        year = int(m.group(1)) if m.group(1) else modified.year
        month = int(m.group(2))
        if not m.group(1) and month > modified.month + 3:
            year -= 1
        return f"{year:04d}-{month:02d}", "字幕内の年月表現と字幕更新年から推定", "medium"
    for line in opening:
        m = SEASON_RE.search(line)
        if m:
            return f"{modified.year}年 {m.group(1)}", "字幕内の季節表現と字幕更新年から推定", "medium"
    return modified.strftime("%Y-%m"), "字幕ファイル更新月から推定", "low"


def explain(lines: list[str]) -> str:
    candidates = []
    seen = set()
    for i, line in enumerate(lines):
        line = re.sub(r"^[・●■◆▶▷]+", "", line).strip()
        if len(line) < 5 or len(line) > 110 or any(x in line for x in SKIP_PHRASES):
            continue
        key = re.sub(r"[\s。、！？!?]", "", line)
        if key in seen:
            continue
        seen.add(key)
        score = sum(2 for w in AG_WORDS if w in line)
        score += 2 if i < 12 else (1 if i < 35 else 0)
        score += 1 if line.endswith(("。", "！", "？")) else 0
        candidates.append((score, i, line))
    if not candidates:
        return "字幕から解説文を生成できませんでした。"
    agricultural = any(any(w in line for w in AG_WORDS) for _, _, line in candidates)
    ranked = sorted(candidates, key=lambda x: (-x[0], x[1]))
    chosen = sorted(ranked[:4], key=lambda x: x[1])
    body = " ".join(x[2] for x in chosen)
    prefix = "自然農・栽培に関する記録。" if agricultural else "字幕内容の記録。"
    return prefix + body


def detailed_text(lines: list[str], short_description: str, is_agricultural: int | None) -> str:
    if not lines:
        return "字幕ファイルが見つからないため、詳細テキストは未作成です。"

    # Remove exact repetitions while preserving the chronological order of the SRT.
    cleaned = []
    previous = None
    for line in lines:
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line == previous or any(x in line for x in SKIP_PHRASES):
            continue
        cleaned.append(line)
        previous = line

    section_count = min(5, max(1, (len(cleaned) + 24) // 25))
    chunk_size = max(1, (len(cleaned) + section_count - 1) // section_count)
    chronology = []
    for idx in range(0, len(cleaned), chunk_size):
        chunk = cleaned[idx: idx + chunk_size]
        chronology.append(f"【場面{len(chronology) + 1}】" + " ".join(chunk))

    joined = " ".join(cleaned)
    topics = [word for word in AG_WORDS if word in joined]
    topic_text = "、".join(dict.fromkeys(topics[:18])) if topics else "明瞭な農業キーワードは少ない"
    dates = []
    for line in cleaned:
        for match in DATE_FULL_RE.finditer(line):
            dates.append(match.group(0).strip())
        for match in SEASON_RE.finditer(line):
            dates.append(match.group(0))
    dates = list(dict.fromkeys(x for x in dates if x))

    if is_agricultural == 1:
        observation = (
            "この字幕は、完成した成果だけでなく、作物の状態を観察し、その場で行った作業や判断を記録する"
            "実践ログとして読むことができます。自然農の記録では、草、土、天候、周囲の植物との関係が"
            "重要になるため、作物名だけでなく、失敗・変化・比較・次の作業に触れた記述も資料価値があります。"
            "なお、字幕は映像の要約ではなく場面ごとの説明なので、断定的な栽培指導としてではなく、"
            "撮影時点における観察と実践例として参照するのが適切です。"
        )
    else:
        observation = (
            "農業に直接関係する語が少ないため、自然農本編以外の記録である可能性があります。"
            "ただし自動判定は字幕中の語句に基づくため、映像に畑や作物が含まれていても判定できない場合があります。"
        )
    if dates:
        observation += " 字幕内には時期を示す表現として「" + "、".join(dates[:12]) + "」が見られます。"

    transcript = "\n".join(f"{i + 1:04d}. {line}" for i, line in enumerate(cleaned))
    return (
        "【概要】\n" + short_description + "\n\n"
        "【主な話題・対象】\n" + topic_text + "\n\n"
        "【内容の流れ】\n" + "\n\n".join(chronology) + "\n\n"
        "【補足・所見】\n" + observation + "\n\n"
        "【整形済み字幕全文】\n" + transcript
    )


def find_subtitles() -> dict[str, list[Path]]:
    found: dict[str, list[Path]] = {}
    roots = [DOCS, MOV]
    for root in roots:
        for path in root.rglob("*.srt"):
            # Avoid unrelated archives and translated duplicates when deriving a code.
            parts = code_parts(path.stem)
            if not parts:
                continue
            code, number, suffix = parts
            # Language suffixes are variants, not video-code suffixes.
            suffix_l = suffix.lower()
            for lang in ("ja", "en", "hi", "be", "bn"):
                if suffix_l == lang:
                    code = f"n{number}"
            if suffix_l in ("old", "b2") or suffix_l.startswith("ja"):
                code = f"n{number}"
            found.setdefault(code, []).append(path)
    return found


def find_videos() -> dict[str, list[tuple[int, Path]]]:
    found: dict[str, list[tuple[int, Path]]] = {}
    excluded = {"arc", "tmp", "join_movie"}
    for path in MOV.rglob("*.mp4"):
        if any(part.lower() in excluded for part in path.relative_to(MOV).parts[:-1]):
            continue
        # The code is fundamentally the containing folder name. This prevents a
        # work file such as n154a0a1.mp4 from being mistaken for code n154a0.
        ancestor_code = None
        for parent in path.parents:
            if parent == MOV.parent:
                break
            parsed = code_parts(parent.name)
            if parsed:
                ancestor_code = parsed[0]
                break
        if not ancestor_code:
            continue
        rx = re.compile(rf"^{re.escape(ancestor_code)}a1(?:b(\d+))?\.mp4$", re.I)
        m = rx.match(path.name)
        if not m:
            continue
        number = int(re.match(r"n(\d+)", ancestor_code).group(1))
        if not MIN_CODE <= number <= MAX_CODE:
            continue
        version = int(m.group(1) or 0)
        found.setdefault(ancestor_code, []).append((version, path))
    return found


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    subtitles = find_subtitles()
    videos = find_videos()
    folder_codes = {}
    for p in MOV.iterdir():
        if p.is_dir() and (parts := code_parts(p.name)):
            code, number, suffix = parts
            folder_codes[code] = p

    # n123short is the folder code; its files use the older abbreviation n123s.
    if "n123short" in folder_codes and "n123s" in subtitles:
        subtitles.setdefault("n123short", []).extend(subtitles.pop("n123s"))

    codes = set(subtitles) | set(videos) | set(folder_codes)
    codes = {c for c in codes if MIN_CODE <= int(re.match(r"n(\d+)", c).group(1)) <= MAX_CODE}
    records = []
    for code in sorted(codes, key=lambda c: (int(re.match(r"n(\d+)", c).group(1)), c)):
        number = int(re.match(r"n(\d+)", code).group(1))
        srt_candidates = subtitles.get(code, [])
        srt = sorted(srt_candidates, key=lambda p: subtitle_priority(p, code))[0] if srt_candidates else None
        lines = subtitle_lines(srt) if srt else []
        modified = datetime.fromtimestamp(srt.stat().st_mtime) if srt else None
        if modified:
            estimated, basis, confidence = infer_date(lines, modified)
            description = explain(lines)
        else:
            estimated, basis, confidence = "", "字幕なし", "unknown"
            description = "字幕ファイルが見つからないため、解説文は未作成です。"
        candidates = videos.get(code, [])
        latest = sorted(candidates, key=lambda x: (x[0], x[1].stat().st_mtime, str(x[1])), reverse=True)[0][1] if candidates else None
        is_ag = 1 if any(w in " ".join(lines) for w in AG_WORDS) else (0 if lines else None)
        detail = detailed_text(lines, description, is_ag)
        records.append({
            "video_code": code, "code_number": number, "estimated_shooting_period": estimated,
            "date_estimation_basis": basis, "date_confidence": confidence,
            "video_filename": latest.name if latest else "", "video_path": str(latest) if latest else "",
            "subtitle_path": str(srt) if srt else "", "subtitle_modified_at": modified.isoformat(timespec="seconds") if modified else "",
            "description": description, "detailed_text": detail, "is_agricultural": is_ag,
        })

    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript("""
    PRAGMA journal_mode=DELETE;
    CREATE TABLE archive (
      video_code TEXT PRIMARY KEY,
      code_number INTEGER NOT NULL,
      estimated_shooting_period TEXT,
      date_estimation_basis TEXT,
      date_confidence TEXT CHECK(date_confidence IN ('medium','low','unknown')),
      video_filename TEXT,
      video_path TEXT,
      subtitle_path TEXT,
      subtitle_modified_at TEXT,
      description TEXT NOT NULL,
      detailed_text TEXT NOT NULL,
      is_agricultural INTEGER CHECK(is_agricultural IN (0,1) OR is_agricultural IS NULL)
    );
    CREATE INDEX idx_archive_code_number ON archive(code_number);
    CREATE INDEX idx_archive_period ON archive(estimated_shooting_period);
    CREATE VIEW archive_browse AS
      SELECT video_code AS 動画コード, estimated_shooting_period AS 推定撮影時期,
             video_filename AS 動画ファイル名, video_path AS 動画ファイルパス,
             description AS 動画解説テキスト, detailed_text AS 動画詳細テキスト
      FROM archive ORDER BY code_number, video_code;
    CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    cols = list(records[0])
    con.executemany(
        f"INSERT INTO archive ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
        [[r[c] for c in cols] for r in records],
    )
    present_numbers = {r["code_number"] for r in records}
    missing = [f"n{x}" for x in range(MIN_CODE, MAX_CODE + 1) if x not in present_numbers]
    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "range": f"n{MIN_CODE}～n{MAX_CODE}",
        "record_count": str(len(records)),
        "missing_numeric_codes": ", ".join(missing),
        "source_roots": f"{MOV}; {DOCS}",
    }
    con.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", metadata.items())
    con.commit()
    con.close()

    with TEXT.open("w", encoding="utf-8-sig", newline="\n") as f:
        f.write("自然農アーカイブ（閲覧用）\n")
        f.write("=" * 40 + "\n")
        f.write(f"作成日時: {metadata['created_at']}\n対象範囲: {metadata['range']}\n収録件数: {len(records)}\n")
        f.write(f"数値コードの欠番: {metadata['missing_numeric_codes'] or 'なし'}\n")
        f.write("注: 推定撮影時期は字幕内表現を優先し、見つからない場合は字幕更新月を使用。\n")
        f.write("注: 動画は a1 系列のうち b 番号が最大のものを採用。\n\n")
        for r in records:
            ag = "農業関連" if r["is_agricultural"] == 1 else ("農業外の可能性" if r["is_agricultural"] == 0 else "判定不能")
            f.write(f"[{r['video_code']}]\n")
            f.write(f"推定撮影時期: {r['estimated_shooting_period'] or '不明'}（{r['date_estimation_basis']} / 確度:{r['date_confidence']}）\n")
            f.write(f"動画ファイル名: {r['video_filename'] or 'なし'}\n動画ファイルパス: {r['video_path'] or 'なし'}\n")
            f.write(f"字幕ファイルパス: {r['subtitle_path'] or 'なし'}\n分類: {ag}\n")
            f.write(f"動画解説テキスト: {r['description']}\n\n")
            f.write(f"動画詳細テキスト:\n{r['detailed_text']}\n\n")

    print(f"DB={DB}")
    print(f"TEXT={TEXT}")
    print(f"RECORDS={len(records)}")
    print(f"WITH_VIDEO={sum(bool(r['video_path']) for r in records)}")
    print(f"WITH_SUBTITLE={sum(bool(r['subtitle_path']) for r in records)}")
    print(f"MISSING={','.join(missing)}")


if __name__ == "__main__":
    main()
