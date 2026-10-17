"""FramePick: Python 3.9 / FFmpeg video frame sampler."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import shutil
import subprocess
import sys


def seconds(value):
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0:
            raise ValueError()
        return number
    except (InvalidOperation, ValueError):
        raise argparse.ArgumentTypeError("0以上の有限の秒数を指定してください。")


def positive_int(value):
    try:
        number = int(value)
        if number > 0:
            return number
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("1以上の整数を指定してください。")


def parser():
    p = argparse.ArgumentParser(description="FramePick — 動画フレーム抽出ツール",
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("video", type=Path, help="入力MP4ファイル")
    p.add_argument("output", nargs="?", type=Path, help="出力フォルダ（省略: 動画名_frames）")
    p.add_argument("--interval", type=seconds, default=Decimal(5), help="抽出間隔（秒、0不可）")
    p.add_argument("--count", type=positive_int, help="最大枚数（省略: 終端まで）")
    p.add_argument("--start", type=seconds, default=Decimal(0), help="開始位置（秒）")
    p.add_argument("--end", type=seconds, help="終了位置（秒、この時刻を含まない）")
    p.add_argument("--format", choices=["jpg", "png"], default="jpg", help="画像形式")
    p.add_argument("--max-width", type=positive_int, help="最大幅px（拡大せず縦横比を維持）")
    p.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg実行ファイル名またはパス")
    return p


def extract(args):
    video = args.video.resolve()
    if not video.is_file():
        raise ValueError("動画ファイルが見つかりません: {}".format(video))
    if args.interval <= 0:
        raise ValueError("--interval は0より大きい秒数が必要です。")
    if args.end is not None and args.end <= args.start:
        raise ValueError("--end は --start より大きい秒数が必要です。")
    executable = shutil.which(args.ffmpeg)
    if not executable:
        raise ValueError("FFmpegが見つかりません。PATHまたは --ffmpeg を設定してください。")
    executable = str(Path(executable).resolve())
    output = (args.output or video.with_name(video.stem + "_frames")).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("出力先には新規または空のフォルダを指定してください: {}".format(output))
    output.mkdir(parents=True, exist_ok=True)
    # Normalize presentation timestamps to the first displayed video frame.
    filters = ["setpts=PTS-STARTPTS"]
    if args.end is not None:
        filters.append("trim=end={}".format(args.end))
    filters.append("select='gte(t,{}+selected_n*{})'".format(args.start, args.interval))
    if args.max_width:
        filters.append("scale='min(iw,{})':-1".format(args.max_width))
    filters.append("showinfo")
    command = [executable, "-hide_banner", "-nostdin", "-nostats", "-n", "-i", str(video),
               "-map", "0:v:0", "-an", "-vf", ",".join(filters), "-vsync", "0"]
    if args.count:
        command += ["-frames:v", str(args.count)]
    if args.format == "jpg":
        command += ["-q:v", "2"]
    command += ["-start_number", "1", "frame_%06d." + args.format]
    print("抽出中: {}".format(video), flush=True)
    log = output / "ffmpeg.log"
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=str(output), stdout=subprocess.DEVNULL,
                                stderr=stream)
    # showinfo can log an extra decoded frame; associate only files actually written.
    timestamps = []
    time_base = None
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        base = re.search(r"config in time_base:\s*(\d+)/(\d+)", line)
        if base:
            time_base = Decimal(base[1]) / Decimal(base[2])
        match = re.search(r"\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:([\d.eE+-]+)", line)
        if match:
            timestamps.append(Decimal(match[1]) * time_base if time_base else Decimal(match[2]))
    images = sorted(output.glob("frame_*." + args.format))
    valid = result.returncode == 0 and bool(images) and len(timestamps) >= len(images)
    with (output / "frames.txt").open("w", encoding="utf-8-sig", newline="") as stream:
        stream.write("FramePick / 動画フレーム抽出結果\n")
        stream.write("動画: {}\n状態: {}\n".format(video, "完了" if valid else "失敗（部分出力の可能性あり）"))
        stream.write("時刻原点: 最初の映像フレーム=0ms。実取得時刻は指定位置以降の最初のフレーム。\n")
        stream.write("間隔: {}秒 / 開始: {}秒 / 終了: {} / 最大枚数: {}\n".format(
            args.interval, args.start, args.end if args.end is not None else "動画終端",
            args.count if args.count else "制限なし"))
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["image", "source_video", "requested_ms", "actual_ms"])
        for index, image in enumerate(images):
            actual = format(timestamps[index] * 1000, ".3f") if index < len(timestamps) else "不明"
            writer.writerow([image.name, str(video), str((args.start + index * args.interval) * 1000), actual])
    if not valid:
        raise ValueError("抽出できませんでした。出力先の ffmpeg.log と frames.txt を確認してください。")
    print("完了: {}枚 / {}".format(len(images), output))
    return len(images)


def main():
    args = parser().parse_args()
    try:
        extract(args)
        return 0
    except (ValueError, OSError) as error:
        print("エラー: {}".format(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("中断しました。出力先に部分的な画像やログが残る場合があります。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
