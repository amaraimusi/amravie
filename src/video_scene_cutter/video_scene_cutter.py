#!/usr/bin/env python3
"""MP4動画から指定した時間範囲を切り出すコマンドラインツール。"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


TIMESTAMP_PATTERN = re.compile(
    r"^(?P<hours>\d+):(?P<minutes>[0-5]\d):(?P<seconds>[0-5]\d)[,.](?P<milliseconds>\d{3})$"
)


def timestamp_to_milliseconds(value: str) -> int:
    """「時:分:秒,ミリ秒」を整数のミリ秒へ変換する。"""
    match = TIMESTAMP_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError(
            "タイムスタンプは HH:MM:SS,mmm 形式で指定してください "
            "（例: 00:03:41,338）。"
        )

    parts = {name: int(number) for name, number in match.groupdict().items()}
    return (
        ((parts["hours"] * 60 + parts["minutes"]) * 60 + parts["seconds"])
        * 1000
        + parts["milliseconds"]
    )


def milliseconds_to_ffmpeg_time(milliseconds: int) -> str:
    """ミリ秒をFFmpegが解釈する秒表記へ変換する。"""
    return "{:.3f}".format(milliseconds / 1000.0)


def default_output_path(input_path: Path, start_ms: int, end_ms: int) -> Path:
    """入力ファイルと同じ場所に作る既定の出力パスを返す。"""
    return input_path.with_name(
        "{}_cut_{:010d}_{:010d}.mp4".format(input_path.stem, start_ms, end_ms)
    )


def find_ffmpeg(explicit_path: Optional[str]) -> str:
    """利用するFFmpeg実行ファイルを探す。"""
    if explicit_path:
        candidate = Path(explicit_path).expanduser()
        if not candidate.is_file():
            raise FileNotFoundError("FFmpegが見つかりません: {}".format(candidate))
        return str(candidate)

    found = shutil.which("ffmpeg")
    if found is None:
        raise FileNotFoundError(
            "FFmpegが見つかりません。PATHへ追加するか --ffmpeg で場所を指定してください。"
        )
    return found


def cut_scene(
    input_path: Path,
    output_path: Path,
    start_ms: int,
    end_ms: int,
    ffmpeg_path: str,
    overwrite: bool = False,
) -> None:
    """FFmpegを使い、指定範囲を映像・音声ともに切り出す。"""
    if not input_path.is_file():
        raise FileNotFoundError("入力動画が見つかりません: {}".format(input_path))
    if input_path.suffix.lower() != ".mp4":
        raise ValueError("入力ファイルにはMP4動画を指定してください。")
    if input_path == output_path:
        raise ValueError("出力ファイルには入力動画と異なるパスを指定してください。")
    if start_ms < 0:
        raise ValueError("開始時刻は0以上にしてください。")
    if end_ms <= start_ms:
        raise ValueError("終了時刻は開始時刻より後にしてください。")
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            "出力ファイルは既に存在します。上書きする場合は --overwrite を指定してください: "
            "{}".format(output_path)
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration_ms = end_ms - start_ms
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if overwrite else "-n",
        "-ss",
        milliseconds_to_ffmpeg_time(start_ms),
        "-i",
        str(input_path),
        "-t",
        milliseconds_to_ffmpeg_time(duration_ms),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    output_existed = output_path.exists()
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        if not output_existed and output_path.exists():
            output_path.unlink()
        raise RuntimeError("動画の切り出しに失敗しました。") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MP4動画から、タイムスタンプで指定した範囲を切り出します。"
    )
    parser.add_argument("input", type=Path, help="入力MP4ファイル")
    parser.add_argument("start", help="開始時刻（HH:MM:SS,mmm）")
    parser.add_argument("end", help="終了時刻（HH:MM:SS,mmm）")
    parser.add_argument(
        "-o", "--output", type=Path, help="出力MP4ファイル（省略時は入力動画と同じ場所）"
    )
    parser.add_argument("--overwrite", action="store_true", help="既存の出力ファイルを上書き")
    parser.add_argument("--ffmpeg", help="ffmpeg実行ファイルのパス")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        start_ms = timestamp_to_milliseconds(args.start)
        end_ms = timestamp_to_milliseconds(args.end)
        input_path = args.input.expanduser().resolve()
        output_path = (
            args.output.expanduser().resolve()
            if args.output
            else default_output_path(input_path, start_ms, end_ms)
        )
        ffmpeg_path = find_ffmpeg(args.ffmpeg)
        cut_scene(
            input_path,
            output_path,
            start_ms,
            end_ms,
            ffmpeg_path,
            overwrite=args.overwrite,
        )
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        print("エラー: {}".format(exc), file=sys.stderr)
        return 1

    print("切り出し動画を保存しました: {}".format(output_path))
    print("切り出し時間: {:.3f}秒".format((end_ms - start_ms) / 1000.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
