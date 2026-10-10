import json
import sqlite3
import subprocess
from pathlib import Path

DB = Path(r"E:\backup_kenji\mov\n175\mini_tomato_scenes.sqlite")
REPORT = Path(r"E:\backup_kenji\mov\n175\mini_tomato_scenes.txt")


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"]), {item["codec_type"] for item in data.get("streams", [])}


with sqlite3.connect(DB) as conn:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(mini_tomato_scenes)")}
    for name, kind in (("processing_note", "TEXT"), ("validation_status", "TEXT"), ("actual_duration_seconds", "REAL")):
        if name not in existing:
            conn.execute(f"ALTER TABLE mini_tomato_scenes ADD COLUMN {name} {kind}")
    conn.execute(
        "UPDATE mini_tomato_scenes SET processing_note=? WHERE video_code='n112'",
        ("元動画n112a1.mp4のAAC音声に破損フレームがあり、切り出し時にデコード警告。映像は完了したが環境音に瞬間的な欠落の可能性あり。",),
    )
    conn.execute("UPDATE mini_tomato_scenes SET processing_note=NULL WHERE video_code<>'n112'")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM mini_tomato_scenes ORDER BY scene_id").fetchall()
    failures = []
    total_bytes = 0
    for row in rows:
        path = Path(row["cut_path"])
        status = "ok"
        actual = None
        try:
            total_bytes += path.stat().st_size
            actual, streams = probe(path)
            expected = float(row["cut_duration_seconds"])
            if "video" not in streams:
                status = "error:no_video_stream"
            elif actual + 0.15 < expected:
                status = f"error:short_duration expected={expected:.3f} actual={actual:.3f}"
        except Exception as exc:
            status = f"error:{type(exc).__name__}"
        conn.execute(
            "UPDATE mini_tomato_scenes SET validation_status=?, actual_duration_seconds=? WHERE scene_id=?",
            (status, actual, row["scene_id"]),
        )
        if status != "ok":
            failures.append((row["scene_id"], status))
    conn.commit()

    rows = conn.execute("SELECT * FROM mini_tomato_scenes ORDER BY scene_id").fetchall()
    lines = [
        "ミニトマト関連シーン一覧（n89〜n173）",
        "=" * 44,
        f"収録・切り出しシーン数: {len(rows)}",
        f"検証OK: {sum(row['validation_status'] == 'ok' for row in rows)}",
        "入力例外: n121はa1欠落のためa0、n125・n172はa1欠落のためa3b3を代替使用。",
        "音声注意: n112の元動画AACに破損フレームがあり、環境音に瞬間的な欠落の可能性あり。",
        "",
    ]
    for row in rows:
        lines.extend([
            f"[{row['scene_id']:03d}] {row['video_code']} / 動画内シーン {row['video_scene_number']:02d}",
            f"時間: {row['start_timestamp']} --> {row['end_timestamp']}（指定 {row['cut_duration_seconds']:.3f}秒 / 実尺 {row['actual_duration_seconds']:.3f}秒）",
            f"検証: {row['validation_status']}",
            f"推定撮影時期: {row['estimated_shooting_period']}（{row['estimation_basis']}）",
            f"場面: {row['scene_summary']}",
            f"切り出し動画: {row['cut_path']}",
            f"入力動画: {row['source_video']} [{row['source_video_kind']}]",
            *((f"備考: {row['processing_note']}",) if row["processing_note"] else ()),
            f"字幕抜粋: {row['subtitle_excerpt']}",
            f"出典字幕: {row['source_srt']}",
            "",
        ])
    REPORT.write_text("\n".join(lines), encoding="utf-8-sig")
    print(f"rows={len(rows)} ok={len(rows)-len(failures)} failures={failures} bytes={total_bytes}")
