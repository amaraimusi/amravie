#!/usr/bin/env python3
"""ClipNormalizer Batch - normalize all MP4 files in a directory."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from clip_normalizer import (
    ClipNormalizerError,
    build_ffmpeg_command,
    executable,
    first_stream,
    normalize_video,
    positive_float,
    positive_int,
    print_probe,
    probe_media,
    verify_output,
)


def resolve_output_directory(
    input_dir: Path, output_dir: Optional[Path]
) -> Tuple[Path, bool]:
    """Return the explicit or automatically derived output directory."""
    if output_dir is not None:
        resolved = output_dir.resolve()
        automatic = False
    else:
        resolved = input_dir.parent / f"{input_dir.name}_normalized"
        resolved = resolved.resolve()
        automatic = True

    if resolved == input_dir.resolve():
        raise ClipNormalizerError("出力ディレクトリを入力ディレクトリと同じ場所にはできません。")
    return resolved, automatic


def is_relative_to(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def discover_videos(input_dir: Path, output_dir: Path, recursive: bool) -> List[Path]:
    """Find MP4 inputs while excluding an output tree located under the input."""
    iterator = input_dir.rglob("*") if recursive else input_dir.iterdir()
    videos: List[Path] = []
    for path in iterator:
        if not path.is_file() or path.suffix.lower() != ".mp4":
            continue
        resolved = path.resolve()
        if is_relative_to(resolved, output_dir):
            continue
        videos.append(path)
    return sorted(videos, key=lambda item: str(item).casefold())


def output_path_for(source: Path, input_dir: Path, output_dir: Path) -> Path:
    """Preserve relative subdirectories, avoiding recursive-name collisions."""
    relative = source.relative_to(input_dir)
    return (output_dir / relative).with_suffix(".mp4")


def print_batch_header(
    input_dir: Path, output_dir: Path, automatic: bool, file_count: int
) -> None:
    print("ClipNormalizer Batch")
    print(f"\n入力:\n{input_dir}")
    print(f"\n出力:\n{output_dir}")
    if automatic:
        print("（出力先が省略されたため自動設定しました）")
    print(f"\n対象動画: {file_count}ファイル")


def replace_with_retry(source: Path, destination: Path) -> None:
    """Finalize an output despite brief Windows scanner/indexer file locks."""
    last_error: Optional[OSError] = None
    for attempt in range(10):
        try:
            os.replace(str(source), str(destination))
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.1 * (attempt + 1))
    raise ClipNormalizerError(f"出力ファイル名を確定できません: {last_error}")


def remove_temporary_with_retry(path: Path) -> None:
    for attempt in range(5):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(0.1 * (attempt + 1))


def normalize_one(
    source: Path,
    destination: Path,
    args: argparse.Namespace,
    ffmpeg_path: str,
    ffprobe_path: str,
) -> None:
    before = probe_media(source, ffprobe_path)
    print_probe("正規化前", before)
    has_audio = first_stream(before, "audio") is not None

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.stem}.normalizing.mp4")
    file_args = argparse.Namespace(**vars(args))
    file_args.input = source
    file_args.output = temporary

    try:
        command = build_ffmpeg_command(file_args, has_audio, ffmpeg_path)
        normalize_video(command)
        after = probe_media(temporary, ffprobe_path)
        print_probe("正規化後", after)
        errors = verify_output(after, file_args, has_audio)
        if errors:
            details = "\n".join(f"  - {error}" for error in errors)
            raise ClipNormalizerError(f"出力検証に失敗しました。\n{details}")
        replace_with_retry(temporary, destination)
    finally:
        if temporary.exists():
            remove_temporary_with_retry(temporary)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ClipNormalizer Batch",
        description="ディレクトリ内のMP4素材を一括して連結向け形式へ正規化します。",
    )
    parser.add_argument("input_dir", type=Path, help="入力ディレクトリ")
    parser.add_argument("output_dir", type=Path, nargs="?", help="出力ディレクトリ（省略可）")
    parser.add_argument("--recursive", action="store_true", help="サブディレクトリも再帰的に処理")
    parser.add_argument("--overwrite", action="store_true", help="既存の出力ファイルを上書き")
    parser.add_argument("--fps", type=positive_float, default=30, help="出力FPS (既定: 30)")
    parser.add_argument("--width", type=positive_int, default=1920, help="出力幅 (既定: 1920)")
    parser.add_argument("--height", type=positive_int, default=1080, help="出力高 (既定: 1080)")
    parser.add_argument("--video-codec", default="libx264", help="映像エンコーダ (既定: libx264)")
    parser.add_argument("--audio-codec", default="aac", help="音声エンコーダ (既定: aac)")
    parser.add_argument(
        "--audio-sample-rate", type=positive_int, default=48000,
        help="音声サンプルレート (既定: 48000)",
    )
    parser.add_argument(
        "--crf", type=int, choices=range(0, 52), default=18,
        metavar="0-51", help="映像品質CRF (既定: 18)",
    )
    parser.add_argument("--preset", default="medium", help="エンコードpreset (既定: medium)")
    return parser.parse_args(argv)


def validate_arguments(args: argparse.Namespace) -> None:
    if not args.input_dir.is_dir():
        raise ClipNormalizerError(f"入力ディレクトリが存在しません: {args.input_dir}")
    if args.width % 2 or args.height % 2:
        raise ClipNormalizerError("yuv420p出力の幅と高さには偶数を指定してください。")


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        validate_arguments(args)
        input_dir = args.input_dir.resolve()
        output_dir, automatic = resolve_output_directory(input_dir, args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg_path = executable("ffmpeg")
        ffprobe_path = executable("ffprobe")
        videos = discover_videos(input_dir, output_dir, args.recursive)
        print_batch_header(input_dir, output_dir, automatic, len(videos))

        succeeded = 0
        skipped = 0
        failed: List[Tuple[Path, str]] = []
        for index, source in enumerate(videos, start=1):
            destination = output_path_for(source, input_dir, output_dir)
            print(f"\n{'=' * 72}")
            print(f"[{index}/{len(videos)}] {source}")
            print(f"出力: {destination}")
            if destination.exists() and not args.overwrite:
                print("既存の出力ファイルがあるためスキップしました。")
                skipped += 1
                continue
            try:
                normalize_one(source, destination, args, ffmpeg_path, ffprobe_path)
                print("検証結果: OK")
                succeeded += 1
            except (ClipNormalizerError, OSError) as exc:
                print(f"エラー: {exc}", file=sys.stderr)
                failed.append((source, str(exc)))

        print("\n=== 一括処理結果 ===")
        print(f"成功: {succeeded} / スキップ: {skipped} / 失敗: {len(failed)}")
        if failed:
            print("\n失敗したファイル:", file=sys.stderr)
            for source, message in failed:
                first_line = message.splitlines()[0]
                print(f"  - {source}: {first_line}", file=sys.stderr)
            return 2
        return 0
    except ClipNormalizerError as exc:
        print(f"\nエラー: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"\nファイル操作エラー: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n処理を中断しました。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
