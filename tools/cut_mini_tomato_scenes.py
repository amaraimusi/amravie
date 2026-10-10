import importlib.util
import re
import sqlite3
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"E:\backup_kenji\mov")
DB = ROOT / "n175" / "mini_tomato_scenes.sqlite"
OUT_DIR = ROOT / "n175" / "src"
REPORT = ROOT / "n175" / "mini_tomato_scenes.txt"
CUTTER_PATH = Path(r"C:\Users\user\git\amravie\src\video_scene_cutter\video_scene_cutter.py")


def load_cutter():
    spec = importlib.util.spec_from_file_location("video_scene_cutter", CUTTER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def choose_source(code):
    folder = ROOT / code
    patterns = [
        (re.compile(rf"^{re.escape(code)}a1(?:b(\d+))?\.mp4$", re.I), "a1_latest"),
        (re.compile(rf"^{re.escape(code)}a0(?:b(\d+))?\.mp4$", re.I), "fallback_a0"),
        (re.compile(rf"^{re.escape(code)}a3(?:b(\d+))?\.mp4$", re.I), "fallback_a3"),
    ]
    for pattern, kind in patterns:
        candidates = []
        for path in folder.glob("*.mp4"):
            match = pattern.fullmatch(path.name)
            if match:
                candidates.append((int(match.group(1) or 0), path))
        if candidates:
            return max(candidates, key=lambda item: item[0])[1], kind
    raise FileNotFoundError(f"利用可能な編集済み動画がありません: {code}")


def duration_seconds(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def ensure_columns(conn):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(mini_tomato_scenes)")}
    columns = {
        "video_scene_number": "INTEGER",
        "cut_filename": "TEXT",
        "cut_path": "TEXT",
        "source_video": "TEXT",
        "source_video_kind": "TEXT",
        "cut_duration_seconds": "REAL",
        "cut_status": "TEXT",
    }
    for name, kind in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE mini_tomato_scenes ADD COLUMN {name} {kind}")


def render_report(conn):
    rows = conn.execute("SELECT * FROM mini_tomato_scenes ORDER BY scene_id").fetchall()
    columns = [item[0] for item in conn.execute("SELECT * FROM mini_tomato_scenes LIMIT 0").description]
    records = [dict(zip(columns, row)) for row in rows]
    lines = [
        "ミニトマト関連シーン一覧（n89〜n173）",
        "=" * 44,
        f"収録シーン数: {len(records)}",
        f"切り出し成功数: {sum(r['cut_status'] == 'completed' for r in records)}",
        "注記: n121はa1欠落のためa0、n125・n172はa1欠落のためa3b3を代替使用。",
        "",
    ]
    for row in records:
        lines.extend([
            f"[{row['scene_id']:03d}] {row['video_code']} / 動画内シーン {row['video_scene_number']:02d}",
            f"時間: {row['start_timestamp']} --> {row['end_timestamp']}（{row['cut_duration_seconds']:.3f}秒）",
            f"推定撮影時期: {row['estimated_shooting_period']}（{row['estimation_basis']}）",
            f"場面: {row['scene_summary']}",
            f"切り出し動画: {row['cut_path']}",
            f"入力動画: {row['source_video']} [{row['source_video_kind']}]",
            f"字幕抜粋: {row['subtitle_excerpt']}",
            f"出典字幕: {row['source_srt']}",
            "",
        ])
    REPORT.write_text("\n".join(lines), encoding="utf-8-sig")


def main():
    cutter = load_cutter()
    ffmpeg = cutter.find_ffmpeg(None)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as conn:
        ensure_columns(conn)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM mini_tomato_scenes ORDER BY scene_id").fetchall()
        sources = {code: choose_source(code) for code in {row["video_code"] for row in rows}}
        max_ends = defaultdict(int)
        for row in rows:
            max_ends[row["video_code"]] = max(max_ends[row["video_code"]], cutter.timestamp_to_milliseconds(row["end_timestamp"]))
        for code, (source, _) in sorted(sources.items(), key=lambda item: int(item[0][1:])):
            actual_ms = round(duration_seconds(source) * 1000)
            if actual_ms < max_ends[code]:
                raise ValueError(f"動画尺不足: {source} ({actual_ms}ms < {max_ends[code]}ms)")

        counters = defaultdict(int)
        total = len(rows)
        for index, row in enumerate(rows, 1):
            code = row["video_code"]
            counters[code] += 1
            number = counters[code]
            source, source_kind = sources[code]
            filename = f"{code}_mini_tomato_{number:02d}.mp4"
            output = OUT_DIR / filename
            start_ms = cutter.timestamp_to_milliseconds(row["start_timestamp"])
            end_ms = cutter.timestamp_to_milliseconds(row["end_timestamp"])
            print(f"[{index:02d}/{total}] {code} scene {number:02d} -> {filename}", flush=True)
            cutter.cut_scene(source, output, start_ms, end_ms, ffmpeg, overwrite=True)
            conn.execute(
                """UPDATE mini_tomato_scenes SET
                video_scene_number=?, cut_filename=?, cut_path=?, source_video=?, source_video_kind=?,
                cut_duration_seconds=?, cut_status='completed' WHERE scene_id=?""",
                (number, filename, str(output), str(source), source_kind, (end_ms - start_ms) / 1000, row["scene_id"]),
            )
            conn.commit()
        conn.row_factory = None
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mini_tomato_cut_filename ON mini_tomato_scenes(cut_filename)")
        render_report(conn)
        print(f"Completed: {total} scenes", flush=True)


if __name__ == "__main__":
    main()
