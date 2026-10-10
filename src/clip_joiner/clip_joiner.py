#!/usr/bin/env python3
"""ClipJoiner - join normalized MP4 clips without re-encoding."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


class ClipJoinerError(RuntimeError):
    """An error suitable for display to a command-line user."""


@dataclass(frozen=True)
class Clip:
    path: Path
    duration: Decimal
    start: Decimal
    end: Decimal
    media: Dict[str, Any]


def natural_sort_key(path: Path) -> Tuple[Tuple[int, Any], ...]:
    """Return a case-insensitive Explorer-like natural filename key."""
    parts = re.split(r"(\d+)", path.name.casefold())
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)


def find_mp4_files(input_dir: Path) -> List[Path]:
    return [p for p in input_dir.iterdir() if p.is_file() and p.suffix.casefold() == ".mp4"]


def sort_files(files: Sequence[Path], mode: str, reverse: bool) -> List[Path]:
    if mode == "name":
        key = natural_sort_key
    elif mode == "mtime":
        key = lambda p: (p.stat().st_mtime_ns, natural_sort_key(p))
    else:
        key = lambda p: (p.stat().st_ctime_ns, natural_sort_key(p))
    return sorted(files, key=key, reverse=reverse)


def resolve_executable(name: str) -> str:
    """Prefer the project-bundled binary, then search PATH."""
    candidate = Path(__file__).resolve().parent.parent / f"{name}.exe"
    if candidate.is_file():
        return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    raise ClipJoinerError(f"{name} が見つかりません。PATHへ追加するか、同梱実行ファイルを配置してください。")


def run_process(command: Sequence[str], description: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command), check=True, shell=False, text=True, encoding="utf-8",
            errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise ClipJoinerError(f"{description}を開始できません: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "詳細情報なし").strip()
        raise ClipJoinerError(f"{description}に失敗しました。\n{detail}") from exc


def probe_media(path: Path, ffprobe: str) -> Dict[str, Any]:
    command = [
        ffprobe, "-v", "error", "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,pix_fmt,"
        "avg_frame_rate,time_base,sample_rate,channels", "-of", "json", str(path),
    ]
    result = run_process(command, f"ffprobe解析 ({path.name})")
    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ClipJoinerError(f"ffprobe結果が不正です ({path.name}): {exc}") from exc
    videos = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    if not videos:
        raise ClipJoinerError(f"映像ストリームがありません: {path.name}")
    try:
        duration = Decimal(str(info.get("format", {}).get("duration")))
    except (InvalidOperation, TypeError):
        raise ClipJoinerError(f"有効なdurationを取得できません: {path.name}")
    if not duration.is_finite() or duration <= 0:
        raise ClipJoinerError(f"durationが不正です: {path.name} ({duration})")
    info["_duration_decimal"] = duration
    return info


def _rate(value: Any) -> str:
    try:
        return str(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return str(value)


def _signature(info: Dict[str, Any]) -> Dict[str, Any]:
    videos = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    audios = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    video = videos[0]
    audio = audios[0] if audios else None
    return {
        "video_stream_count": len(videos),
        "audio_stream_count": len(audios),
        "video codec": video.get("codec_name"),
        "width": video.get("width"),
        "height": video.get("height"),
        "pixel format": video.get("pix_fmt"),
        "frame rate": _rate(video.get("avg_frame_rate")),
        "video time_base": video.get("time_base"),
        "audio codec": audio.get("codec_name") if audio else None,
        "audio sample rate": audio.get("sample_rate") if audio else None,
        "audio channels": audio.get("channels") if audio else None,
    }


def check_compatibility(probed: Sequence[Tuple[Path, Dict[str, Any]]]) -> None:
    reference_path, reference_info = probed[0]
    reference = _signature(reference_info)
    problems: List[str] = []
    for path, info in probed[1:]:
        current = _signature(info)
        differences = [
            f"{field}: {reference[field]!r} → {current[field]!r}"
            for field in reference if current[field] != reference[field]
        ]
        if differences:
            problems.append(f"  {path.name} (基準: {reference_path.name})\n    " + "\n    ".join(differences))
    if problems:
        raise ClipJoinerError("入力動画の形式が一致しないため連結できません。\n" + "\n".join(problems))


def calculate_clip_positions(probed: Sequence[Tuple[Path, Dict[str, Any]]]) -> List[Clip]:
    clips: List[Clip] = []
    position = Decimal("0")
    for path, info in probed:
        duration = info["_duration_decimal"]
        end = position + duration
        clips.append(Clip(path, duration, position, end, info))
        position = end
    return clips


def format_timestamp(seconds: Decimal) -> str:
    milliseconds = int((seconds * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def resolve_output_paths(input_dir: Path, output: Optional[Path]) -> Tuple[Path, Path, Path]:
    video = output if output is not None else input_dir.parent / f"{input_dir.name}.mp4"
    return video, video.with_suffix(".sqlite"), video.with_suffix(".txt")


def _concat_path(path: Path) -> str:
    # FFmpeg concat quoting: close the quote, escape one apostrophe, reopen it.
    return str(path.resolve()).replace("\\", "/").replace("'", "'\\''")


def build_concat_list(paths: Sequence[Path], destination: Path) -> None:
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for path in paths:
            handle.write(f"file '{_concat_path(path)}'\n")


def join_videos(paths: Sequence[Path], output: Path, ffmpeg: str, audio_codec: str = "copy") -> None:
    list_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", prefix="clip_joiner_",
            dir=output.parent, delete=False,
        ) as handle:
            list_path = Path(handle.name)
        build_concat_list(paths, list_path)
        codecs = ["-c", "copy"] if audio_codec == "copy" else [
            "-c:v", "copy", "-c:a", "ac3", "-b:a", "192k", "-ar", "48000",
        ]
        run_process([
            ffmpeg, "-hide_banner", "-nostdin", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path), "-map", "0",
            *codecs, "-movflags", "+faststart", str(output),
        ], "FFmpegによる動画連結")
    finally:
        if list_path is not None:
            list_path.unlink(missing_ok=True)


def verify_joined_video(path: Path, ffprobe: str) -> Decimal:
    return probe_media(path, ffprobe)["_duration_decimal"]


def create_database(
    path: Path, clips: Sequence[Clip], output: Path, input_dir: Path,
    actual_duration: Decimal, sort_mode: str, reverse: bool, audio_codec: str,
) -> None:
    total = clips[-1].end
    with sqlite3.connect(str(path)) as db:
        db.executescript("""
            CREATE TABLE clips (
                id INTEGER PRIMARY KEY, filename TEXT NOT NULL,
                duration_seconds REAL NOT NULL, start_seconds REAL NOT NULL,
                end_seconds REAL NOT NULL, duration_timestamp TEXT NOT NULL,
                start_timestamp TEXT NOT NULL, end_timestamp TEXT NOT NULL
            );
            CREATE TABLE join_info (
                output_filename TEXT NOT NULL, created_at TEXT NOT NULL,
                total_duration_seconds REAL NOT NULL, total_duration_timestamp TEXT NOT NULL,
                actual_duration_seconds REAL NOT NULL, actual_duration_timestamp TEXT NOT NULL,
                duration_difference_seconds REAL NOT NULL, clip_count INTEGER NOT NULL,
                sort_mode TEXT NOT NULL, reverse INTEGER NOT NULL, input_directory TEXT NOT NULL,
                audio_codec TEXT NOT NULL
            );
        """)
        db.executemany(
            "INSERT INTO clips VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(i, c.path.name, str(c.duration), str(c.start), str(c.end),
              format_timestamp(c.duration), format_timestamp(c.start), format_timestamp(c.end))
             for i, c in enumerate(clips, 1)],
        )
        db.execute(
            "INSERT INTO join_info VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(output), datetime.now().astimezone().isoformat(timespec="seconds"), str(total),
             format_timestamp(total), str(actual_duration), format_timestamp(actual_duration),
             str(abs(actual_duration - total)), len(clips), sort_mode, int(reverse), str(input_dir),
             audio_codec),
        )


def export_text_report(database: Path, report: Path) -> None:
    with sqlite3.connect(str(database)) as db:
        db.row_factory = sqlite3.Row
        info = db.execute("SELECT * FROM join_info").fetchone()
        clips = db.execute("SELECT * FROM clips ORDER BY id").fetchall()
    lines = [
        "ClipJoiner", "動画連結情報", "", "入力フォルダ:", info["input_directory"], "",
        "出力動画:", info["output_filename"], "", "並び順:",
        info["sort_mode"] + (" (逆順)" if info["reverse"] else ""), "", "素材数:",
        str(info["clip_count"]), "", "----------------------------------------", "",
    ]
    for clip in clips:
        lines += [f"[{clip['id']}]", "ファイル名:", clip["filename"], "", "尺:",
                  clip["duration_timestamp"], "", "開始:", clip["start_timestamp"], "",
                  "終了:", clip["end_timestamp"], "", "----------------------------------------", ""]
    lines += ["素材合計尺:", info["total_duration_timestamp"], "", "完成動画尺:",
              info["actual_duration_timestamp"], "", "差（秒）:",
              str(info["duration_difference_seconds"]), ""]
    report.write_text("\n".join(lines), encoding="utf-8")


def _positive_decimal(value: str) -> Decimal:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("数値を指定してください") from exc
    if not number.is_finite() or number < 0:
        raise argparse.ArgumentTypeError("0以上の有限な数値を指定してください")
    return number


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ClipJoiner", description="正規化済みMP4を無劣化で順番に連結します。")
    parser.add_argument("input_dir", type=Path, help="MP4素材があるフォルダ")
    parser.add_argument("output_file", type=Path, nargs="?", help="出力MP4（省略時は入力フォルダ名）")
    parser.add_argument("--sort", choices=("name", "mtime", "ctime"), default="name", help="連結順 (既定: name)")
    parser.add_argument("--reverse", action="store_true", help="連結順を逆転")
    parser.add_argument("--overwrite", action="store_true", help="既存の3出力を上書き")
    parser.add_argument("--audio-codec", choices=("copy", "ac3"), default="copy",
                        help="音声方式。copyは無変換、ac3は192kbpsへ変換 (既定: copy)")
    parser.add_argument("--duration-tolerance", type=_positive_decimal, default=Decimal("0.1"), metavar="SECONDS", help="尺差の警告値 (既定: 0.1秒)")
    return parser.parse_args(argv)


def _validate_paths(args: argparse.Namespace, outputs: Sequence[Path]) -> None:
    if not args.input_dir.is_dir():
        raise ClipJoinerError(f"入力フォルダが存在しません: {args.input_dir}")
    if outputs[0].suffix.casefold() != ".mp4":
        raise ClipJoinerError("出力動画の拡張子は .mp4 にしてください。")
    if not outputs[0].parent.is_dir():
        raise ClipJoinerError(f"出力先フォルダが存在しません: {outputs[0].parent}")
    existing = [str(p) for p in outputs if p.exists()]
    if existing and not args.overwrite:
        raise ClipJoinerError("出力ファイルが既に存在します。--overwrite 指定時のみ上書きできます。\n  " + "\n  ".join(existing))


def _temporary_output(final: Path) -> Path:
    fd, name = tempfile.mkstemp(prefix=f".{final.stem}_", suffix=final.suffix, dir=final.parent)
    os.close(fd)
    path = Path(name)
    path.unlink()
    return path


def _replace_with_retry(source: Path, destination: Path, attempts: int = 20) -> None:
    """Replace a result file, tolerating short-lived Windows scanner locks."""
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in (5, 32) or attempt == attempts - 1:
                raise ClipJoinerError(
                    "完成ファイルを正式名へ移動できません。出力動画を開いている再生ソフト、"
                    "エクスプローラーのプレビュー、または同期ソフトを閉じて再実行してください。"
                    f"\n対象: {destination}\nWindowsエラー: {exc}"
                ) from exc
            time.sleep(0.25)


def print_input_summary(input_dir: Path, output: Path, clips: Sequence[Clip]) -> None:
    print("\nClipJoiner\n")
    print(f"入力: {input_dir}\n出力: {output}\n対象: {len(clips)}ファイル\n\n連結順:")
    for index, clip in enumerate(clips, 1):
        audio = any(s.get("codec_type") == "audio" for s in clip.media.get("streams", []))
        print(f"{index}. {clip.path.name}  {format_timestamp(clip.duration)}  音声: {'あり' if audio else 'なし'}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    temporary: List[Path] = []
    try:
        args = parse_args(argv)
        input_dir = args.input_dir.resolve()
        output_arg = args.output_file.resolve() if args.output_file else None
        outputs = resolve_output_paths(input_dir, output_arg)
        _validate_paths(args, outputs)
        files = sort_files(find_mp4_files(input_dir), args.sort, args.reverse)
        if not files:
            raise ClipJoinerError("入力フォルダ直下にMP4ファイルがありません。")
        if len(files) == 1:
            print("警告: 連結対象が1本しかありません。", file=sys.stderr)
        ffmpeg, ffprobe = resolve_executable("ffmpeg"), resolve_executable("ffprobe")
        probed = [(path, probe_media(path, ffprobe)) for path in files]
        check_compatibility(probed)
        clips = calculate_clip_positions(probed)
        print_input_summary(input_dir, outputs[0], clips)

        temporary = [_temporary_output(path) for path in outputs]
        join_videos(files, temporary[0], ffmpeg, args.audio_codec)
        actual = verify_joined_video(temporary[0], ffprobe)
        create_database(temporary[1], clips, outputs[0], input_dir, actual, args.sort, args.reverse,
                        args.audio_codec)
        export_text_report(temporary[1], temporary[2])
        difference = abs(actual - clips[-1].end)
        for temp, final in zip(temporary, outputs):
            _replace_with_retry(temp, final)
        temporary.clear()

        print("\n----------------------------------------\n\nClipJoiner 完了\n")
        print(f"素材数: {len(clips)}\n出力動画: {outputs[0]}\nSQLite: {outputs[1]}\n確認テキスト: {outputs[2]}")
        print(f"素材合計尺: {format_timestamp(clips[-1].end)}\n完成動画尺: {format_timestamp(actual)}\n差: {difference}秒")
        if difference > args.duration_tolerance:
            print(f"警告: 尺の差が許容値 {args.duration_tolerance}秒を超えています。", file=sys.stderr)
        print("\n----------------------------------------")
        return 0
    except ClipJoinerError as exc:
        print(f"\nエラー: {exc}", file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error) as exc:
        print(f"\nエラー: 出力処理に失敗しました: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n処理を中断しました。", file=sys.stderr)
        return 130
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
