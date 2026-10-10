#!/usr/bin/env python3
"""ClipNormalizer - concatenation-friendly MP4 normalization using FFmpeg."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class ClipNormalizerError(RuntimeError):
    """An error that can be presented directly to the command-line user."""


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("0より大きい整数を指定してください")
    return number


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("0より大きい数値を指定してください")
    return number


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise ClipNormalizerError(
            f"{name} が見つかりません。FFmpegをインストールし、PATHに追加してください。"
        )
    return path


def run_process(command: Sequence[str], description: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError as exc:
        raise ClipNormalizerError(f"{description}を開始できません: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() or exc.stdout.strip() or "詳細情報なし"
        raise ClipNormalizerError(f"{description}に失敗しました。\n\n{details}") from exc


def probe_media(path: Path, ffprobe_path: str) -> Dict[str, Any]:
    command = [
        ffprobe_path,
        "-v", "error",
        "-show_entries",
        "format=filename,format_name,start_time,duration:"
        "stream=index,codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,"
        "r_frame_rate,time_base,start_time,duration,sample_rate,channels",
        "-of", "json",
        str(path),
    ]
    result = run_process(command, f"ffprobeによる解析 ({path})")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ClipNormalizerError(f"ffprobeの結果を解析できません: {exc}") from exc
    if not any(s.get("codec_type") == "video" for s in data.get("streams", [])):
        raise ClipNormalizerError(f"映像ストリームが見つかりません: {path}")
    return data


def first_stream(info: Dict[str, Any], stream_type: str) -> Optional[Dict[str, Any]]:
    return next(
        (stream for stream in info.get("streams", []) if stream.get("codec_type") == stream_type),
        None,
    )


def display_value(value: Any) -> str:
    return "-" if value in (None, "", "N/A") else str(value)


def print_probe(title: str, info: Dict[str, Any]) -> None:
    video = first_stream(info, "video") or {}
    audio = first_stream(info, "audio")
    fmt = info.get("format", {})
    print(f"\n=== {title} ===")
    print(f"ファイル       : {display_value(fmt.get('filename'))}")
    print(f"コンテナ       : {display_value(fmt.get('format_name'))}")
    print(f"映像           : {display_value(video.get('codec_name'))}, "
          f"{display_value(video.get('width'))}x{display_value(video.get('height'))}, "
          f"{display_value(video.get('pix_fmt'))}")
    print(f"FPS (avg / r)  : {display_value(video.get('avg_frame_rate'))} / "
          f"{display_value(video.get('r_frame_rate'))}")
    print(f"映像 time_base : {display_value(video.get('time_base'))}")
    print(f"映像 start/dur : {display_value(video.get('start_time'))} / "
          f"{display_value(video.get('duration'))} 秒")
    print(f"全体 start/dur : {display_value(fmt.get('start_time'))} / "
          f"{display_value(fmt.get('duration'))} 秒")
    if audio:
        print(f"音声           : {display_value(audio.get('codec_name'))}, "
              f"{display_value(audio.get('sample_rate'))} Hz, "
              f"{display_value(audio.get('channels'))} ch")
        print(f"音声 start/dur : {display_value(audio.get('start_time'))} / "
              f"{display_value(audio.get('duration'))} 秒")
    else:
        print("音声           : なし")


def build_ffmpeg_command(
    args: argparse.Namespace,
    has_audio: bool,
    ffmpeg_path: str,
) -> List[str]:
    # Force even scale dimensions because yuv420p requires even-sized chroma planes.
    video_filter = (
        f"scale={args.width}:{args.height}:force_original_aspect_ratio=decrease:"
        "force_divisible_by=2:flags=lanczos,"
        f"pad={args.width}:{args.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"fps=fps={args.fps},setpts=PTS-STARTPTS,format=yuv420p"
    )
    command = [ffmpeg_path, "-hide_banner", "-y", "-i", str(args.input)]
    if has_audio:
        command += [
            "-filter_complex",
            f"[0:v:0]{video_filter}[v];"
            f"[0:a:0]aresample={args.audio_sample_rate}:async=1:first_pts=0,"
            "asetpts=PTS-STARTPTS[a]",
            "-map", "[v]", "-map", "[a]",
        ]
    else:
        command += ["-vf", video_filter, "-map", "0:v:0", "-an"]
    command += [
        "-c:v", args.video_codec,
        "-preset", args.preset,
        "-crf", str(args.crf),
        "-pix_fmt", "yuv420p",
        "-r", str(args.fps),
        # -vsync is retained for compatibility with older Windows FFmpeg builds.
        # The fps filter above performs the actual CFR frame selection.
        "-vsync", "cfr",
    ]
    if has_audio:
        command += [
            "-c:a", args.audio_codec,
            "-ar", str(args.audio_sample_rate),
            "-shortest",
        ]
    command += [
        "-movflags", "+faststart",
        "-metadata:s:v:0", "language=und",
        str(args.output),
    ]
    return command


def normalize_video(command: Sequence[str]) -> None:
    print("\n正規化を実行しています...")
    run_process(command, "FFmpegによる変換")
    print("FFmpegによる変換が完了しました。")


def rate_as_fraction(value: Any) -> Optional[Fraction]:
    try:
        result = Fraction(str(value))
        return result if result.denominator and result > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


def expected_codec(encoder: str) -> Optional[str]:
    known = {
        "libx264": "h264", "h264": "h264", "h264_nvenc": "h264",
        "libx265": "hevc", "hevc": "hevc", "aac": "aac",
        "libfdk_aac": "aac", "libopus": "opus", "opus": "opus",
    }
    return known.get(encoder.lower())


def verify_output(
    info: Dict[str, Any], args: argparse.Namespace, input_had_audio: bool
) -> List[str]:
    video = first_stream(info, "video") or {}
    audio = first_stream(info, "audio")
    errors: List[str] = []
    if (video.get("width"), video.get("height")) != (args.width, args.height):
        errors.append("解像度が指定値と一致しません")
    if video.get("pix_fmt") != "yuv420p":
        errors.append("ピクセルフォーマットがyuv420pではありません")
    target_rate = Fraction(str(args.fps))
    avg_rate = rate_as_fraction(video.get("avg_frame_rate"))
    real_rate = rate_as_fraction(video.get("r_frame_rate"))
    if avg_rate != target_rate or real_rate != target_rate:
        errors.append(
            f"FPSが指定値と一致しません (avg={video.get('avg_frame_rate')}, "
            f"r={video.get('r_frame_rate')})"
        )
    wanted_video_codec = expected_codec(args.video_codec)
    if wanted_video_codec and video.get("codec_name") != wanted_video_codec:
        errors.append(f"映像コーデックが{wanted_video_codec}ではありません")
    if input_had_audio and audio is None:
        errors.append("入力にあった音声が出力にありません")
    try:
        video_start = float(video.get("start_time", 0))
        if abs(video_start) > 0.000001:
            errors.append(f"映像の開始時刻が0ではありません ({video_start:.6f}秒)")
    except (TypeError, ValueError):
        errors.append("映像の開始時刻を確認できません")
    if audio:
        wanted_audio_codec = expected_codec(args.audio_codec)
        if wanted_audio_codec and audio.get("codec_name") != wanted_audio_codec:
            errors.append(f"音声コーデックが{wanted_audio_codec}ではありません")
        if str(audio.get("sample_rate")) != str(args.audio_sample_rate):
            errors.append("音声サンプルレートが指定値と一致しません")
    return errors


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ClipNormalizer",
        description="MP4素材を動画連結に適したCFR・ゼロ開始PTSへ正規化します。",
    )
    parser.add_argument("input", type=Path, help="入力動画ファイル")
    parser.add_argument("output", type=Path, help="出力MP4ファイル")
    parser.add_argument("--fps", type=positive_float, default=30, help="出力FPS (既定: 30)")
    parser.add_argument("--width", type=positive_int, default=1920, help="出力幅 (既定: 1920)")
    parser.add_argument("--height", type=positive_int, default=1080, help="出力高 (既定: 1080)")
    parser.add_argument("--video-codec", default="libx264", help="映像エンコーダ (既定: libx264)")
    parser.add_argument("--audio-codec", default="aac", help="音声エンコーダ (既定: aac)")
    parser.add_argument("--audio-sample-rate", type=positive_int, default=48000,
                        help="音声サンプルレート (既定: 48000)")
    parser.add_argument("--crf", type=int, choices=range(0, 52), default=18,
                        metavar="0-51", help="映像品質CRF (既定: 18)")
    parser.add_argument("--preset", default="medium", help="エンコードpreset (既定: medium)")
    return parser.parse_args(argv)


def validate_paths(args: argparse.Namespace) -> None:
    if not args.input.is_file():
        raise ClipNormalizerError(f"入力ファイルが存在しません: {args.input}")
    if args.input.resolve() == args.output.resolve():
        raise ClipNormalizerError("入力ファイルと出力ファイルに同じパスは指定できません。")
    if not args.output.parent.is_dir():
        raise ClipNormalizerError(f"出力先フォルダが存在しません: {args.output.parent}")
    if args.output.suffix.lower() != ".mp4":
        raise ClipNormalizerError("出力ファイルの拡張子は .mp4 にしてください。")
    if args.width % 2 or args.height % 2:
        raise ClipNormalizerError("yuv420p出力の幅と高さには偶数を指定してください。")


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        validate_paths(args)
        ffmpeg_path = executable("ffmpeg")
        ffprobe_path = executable("ffprobe")

        before = probe_media(args.input, ffprobe_path)
        print_probe("正規化前", before)
        input_had_audio = first_stream(before, "audio") is not None

        command = build_ffmpeg_command(args, input_had_audio, ffmpeg_path)
        normalize_video(command)

        after = probe_media(args.output, ffprobe_path)
        print_probe("正規化後", after)
        errors = verify_output(after, args, input_had_audio)
        if errors:
            print("\n検証結果: NG", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 2
        print("\n検証結果: OK（指定形式への正規化を確認しました）")
        return 0
    except ClipNormalizerError as exc:
        print(f"\nエラー: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n処理を中断しました。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
