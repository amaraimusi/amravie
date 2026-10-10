"""MP4 動画のハードカットを検出し、シーンごとの時刻を出力する。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


@dataclass(frozen=True)
class Scene:
    number: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    start_time: str
    end_time: str


def format_time(seconds: float) -> str:
    """秒を HH:MM:SS.mmm 形式にする。"""
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def frame_signature(frame: np.ndarray, width: int = 64, height: int = 36) -> np.ndarray:
    """画面全体から均等に色を採取した、小さな比較用画像を返す。"""
    small = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    # 明るさの変化だけに偏らないよう Lab 色空間で比較する。
    return cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)


def difference(previous: np.ndarray, current: np.ndarray) -> float:
    """2画面の平均色差を 0.0～1.0 で返す。"""
    return float(np.mean(np.abs(current - previous)) / 255.0)


def detect_cuts(
    video_path: Path,
    sample_interval: float = 0.2,
    threshold: float = 0.12,
    min_scene_length: float = 3.0,
) -> tuple[list[float], float, list[tuple[float, float]]]:
    """シーン切替時刻、動画長、検出候補の (時刻, 色差) を返す。"""
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"動画を開けません: {video_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or frame_count <= 0:
        capture.release()
        raise ValueError("動画のフレームレートまたはフレーム数を取得できません")

    duration = frame_count / fps
    sample_frames = max(1, round(sample_interval * fps))
    cuts: list[float] = []
    candidates: list[tuple[float, float]] = []
    previous_signature: np.ndarray | None = None
    last_cut = 0.0
    frame_number = 0

    try:
        while frame_number < frame_count:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ok, frame = capture.read()
            if not ok:
                break

            current_signature = frame_signature(frame)
            current_time = frame_number / fps
            if previous_signature is not None:
                score = difference(previous_signature, current_signature)
                if score >= threshold:
                    candidates.append((current_time, score))
                    if current_time - last_cut >= min_scene_length:
                        cuts.append(current_time)
                        last_cut = current_time

            previous_signature = current_signature
            frame_number += sample_frames
    finally:
        capture.release()

    # 動画末尾に短すぎるシーンを作らない。
    if cuts and duration - cuts[-1] < min_scene_length:
        cuts.pop()
    return cuts, duration, candidates


def make_scenes(cuts: Iterable[float], duration: float) -> list[Scene]:
    boundaries = [0.0, *cuts, duration]
    scenes = []
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        scenes.append(
            Scene(
                number=index,
                start_seconds=round(start, 3),
                end_seconds=round(end, 3),
                duration_seconds=round(end - start, 3),
                start_time=format_time(start),
                end_time=format_time(end),
            )
        )
    return scenes


def write_csv(path: Path, scenes: list[Scene]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=asdict(scenes[0]).keys())
        writer.writeheader()
        writer.writerows(asdict(scene) for scene in scenes)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MP4 の画面切替を検出してシーン時刻を出力します")
    parser.add_argument("input", type=Path, help="入力MP4ファイル")
    parser.add_argument("-o", "--output", type=Path, help="出力先（省略時は同名の scenes.csv）")
    parser.add_argument("--format", choices=("csv", "json"), default="csv", help="出力形式")
    parser.add_argument("--interval", type=float, default=0.2, help="比較間隔（秒、既定: 0.2）")
    parser.add_argument("--threshold", type=float, default=0.12, help="色差の検出閾値（既定: 0.12）")
    parser.add_argument("--min-scene", type=float, default=3.0, help="最短シーン秒数（既定: 3.0）")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        print(f"入力動画が見つかりません: {args.input}", file=sys.stderr)
        return 1
    if args.interval <= 0 or not 0 < args.threshold <= 1 or args.min_scene < 0:
        print("interval と threshold は正数、min-scene は0以上にしてください", file=sys.stderr)
        return 1

    suffix = ".json" if args.format == "json" else ".csv"
    output = args.output or args.input.with_name(f"{args.input.stem}_scenes{suffix}")
    try:
        cuts, duration, candidates = detect_cuts(
            args.input, args.interval, args.threshold, args.min_scene
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1

    scenes = make_scenes(cuts, duration)
    if args.format == "json":
        output.write_text(
            json.dumps([asdict(scene) for scene in scenes], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        write_csv(output, scenes)

    print(f"{len(scenes)} シーンを検出しました: {output}")
    for scene in scenes:
        print(f"{scene.number:3d}  {scene.start_time} - {scene.end_time}  ({scene.duration_seconds:.1f}秒)")
    if not candidates:
        print("ヒント: 切替を検出できない場合は --threshold 0.08 など閾値を下げてください")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
