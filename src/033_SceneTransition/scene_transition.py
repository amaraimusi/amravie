"""033 SceneTransition — render a CSV timeline to MP4 on Windows."""

import argparse
import csv
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

COLUMNS = ["image_path", "duration_ms", "transition", "transition_ms"]
EFFECTS = {
    "cut": "cut", "none": "cut", "カット": "cut", "なし": "cut",
    "crossfade": "crossfade", "dissolve": "crossfade",
    "crossdissolve": "crossfade", "クロスディゾルブ": "crossfade",
    "fadeblack": "fadeblack", "フェードブラック": "fadeblack",
    "wipe": "wipe", "ワイプ": "wipe", "slide": "slide", "スライド": "slide",
    "zoom": "zoom", "ズーム": "zoom", "blur": "blur", "ブラー": "blur",
}
CODECS = {"h264": "libx264", "h265": "libx265"}
WORK = Path(__file__).resolve().parent / "work"


@dataclass
class Scene:
    path: Path
    line: int
    effect: str
    transition_end: int
    display_end: int


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("正の整数を指定してください")
    return number


def ratio(value):
    try:
        width, height = map(int, value.split(":"))
        if width <= 0 or height <= 0:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("画面比率は 16:9 のように指定してください") from None
    common = math.gcd(width, height)
    width, height = width // common, height // common
    scale = min(1920 // width, 1920 // height, 1080 // min(width, height))
    scale -= scale % 2
    if scale < 2:
        raise argparse.ArgumentTypeError("画面比率の整数比が大きすぎます")
    return width * scale, height * scale


def parse_args():
    parser = argparse.ArgumentParser(description="指示CSVからシーンイラストを結合してMP4を生成します")
    parser.add_argument("csv", type=Path, help="指示CSV")
    parser.add_argument("output", nargs="?", type=Path, help="MP4保存先")
    parser.add_argument("audio", nargs="?", type=Path, help="MP3音源")
    parser.add_argument("-o", "--output", dest="output_option", type=Path, help="MP4保存先")
    parser.add_argument("-a", "--audio", dest="audio_option", type=Path, help="MP3音源")
    parser.add_argument("--aspect-ratio", type=ratio, default="16:9", help="画面比率（既定 16:9）")
    parser.add_argument("--fps", type=positive_int, default=30, help="整数フレームレート（既定 30）")
    parser.add_argument("--codec", choices=CODECS, default="h264", help="映像コーデック（既定 h264）")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg実行ファイル名またはパス")
    parser.add_argument("--overwrite", action="store_true", help="既存MP4を上書きする")
    args = parser.parse_args()
    if (args.output and args.output_option) or (args.audio and args.audio_option):
        parser.error("保存先または音源が重複指定されています")
    return args


def read_timeline(csv_path, fps):
    scenes = []
    elapsed = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source, strict=True)
        try:
            header = next(reader, [])
            if sorted(header) != sorted(COLUMNS):
                raise ValueError("CSVのヘッダーには " + ", ".join(COLUMNS) + " が必要です")
            for row in reader:
                if not row:
                    continue
                line = reader.line_num
                if len(row) != len(COLUMNS):
                    raise ValueError(f"CSV {line}行目: 4列が必要です")
                fields = dict(zip(header, (field.strip() for field in row)))
                image = csv_path.parent / fields["image_path"]
                if not fields["image_path"] or not image.is_file():
                    raise ValueError(f"CSV {line}行目: 画像が見つかりません: {image}")
                try:
                    duration = int(fields["duration_ms"])
                    transition = int(fields["transition_ms"])
                    if duration <= 0 or transition < 0:
                        raise ValueError
                except ValueError:
                    raise ValueError(
                        f"CSV {line}行目: duration_msは正の整数、transition_msは0以上の整数が必要です"
                    ) from None
                name = fields["transition"].lower()
                effect = EFFECTS.get(name)
                if not name:
                    effect = "crossfade" if transition else "cut"
                if effect is None:
                    raise ValueError(f"CSV {line}行目: 未対応のトランジション: {name}")
                if not scenes and (effect != "cut" or transition):
                    raise ValueError(f"CSV {line}行目: 最初のシーンは cut,0 を指定してください")
                if (effect == "cut") != (transition == 0):
                    raise ValueError(f"CSV {line}行目: cutは0、その他の効果は正のtransition_msが必要です")
                # Round timeline boundaries, so rounding never accumulates per scene.
                transition_end = ((elapsed + transition) * fps + 500) // 1000
                elapsed += transition + duration
                display_end = (elapsed * fps + 500) // 1000
                scenes.append(Scene(image, line, effect, transition_end, display_end))
        except csv.Error as error:
            raise ValueError(f"CSV {reader.line_num}行目: {error}") from error
        except UnicodeError as error:
            raise ValueError("指示CSVをUTF-8で保存してください") from error
    if not scenes:
        raise ValueError("CSVにシーンがありません")
    if not scenes[-1].display_end:
        raise ValueError("指定のフレームレートでは映像が0フレームになります")
    return scenes, elapsed


def load_image(scene, size, image_module, image_ops):
    try:
        with image_module.open(scene.path) as source:
            image = image_ops.exif_transpose(source).convert("RGBA")
            scale = min(size[0] / image.width, size[1] / image.height)
            fitted = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
            if fitted != image.size:
                resampling = getattr(image_module, "Resampling", image_module)
                image = image.resize(fitted, resampling.LANCZOS)
    except (OSError, ValueError, image_module.DecompressionBombError) as error:
        raise ValueError(f"CSV {scene.line}行目: 画像を開けません: {scene.path} ({error})") from error
    canvas = image_module.new("RGB", size)
    offset = tuple((target - actual) // 2 for target, actual in zip(size, image.size))
    canvas.paste(image, offset, image)
    return canvas


def transition_frame(before, after, effect, progress, image_module, image_filter):
    width, height = before.size
    if effect == "fadeblack":
        black = image_module.new("RGB", before.size)
        if progress < 0.5:
            return image_module.blend(before, black, 2 * progress)
        return image_module.blend(black, after, 2 * progress - 1)
    if effect in ("wipe", "slide"):
        shift = round(width * progress)
        boundary = width - shift
        if effect == "wipe":
            frame = before.copy()
            frame.paste(after.crop((boundary, 0, width, height)), (boundary, 0))
        else:
            frame = image_module.new("RGB", before.size)
            frame.paste(before, (-shift, 0))
            frame.paste(after, (boundary, 0))
        return frame
    if effect == "zoom":
        scale = 1 + progress * 0.5
        x = (width - width / scale) / 2
        y = (height - height / scale) / 2
        before = before.resize(before.size, box=(x, y, width - x, height - y))
    frame = image_module.blend(before, after, progress)
    if effect == "blur":
        return frame.filter(image_filter.GaussianBlur(width * 0.015 * math.sin(math.pi * progress)))
    return frame


def render(command, scenes, size, log):
    try:
        from PIL import Image, ImageFilter, ImageOps
    except ImportError as error:
        raise ValueError("Pillowが必要です。python -m pip install Pillow を実行してください") from error

    with log.open("w+b") as errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors)
        try:
            previous = None
            frame_index = 0
            with process.stdin as pipe:
                for scene in scenes:
                    current = load_image(scene, size, Image, ImageOps)
                    count = scene.transition_end - frame_index
                    for offset in range(count):
                        frame = transition_frame(previous, current, scene.effect,
                                                 (offset + 0.5) / count, Image, ImageFilter)
                        pipe.write(frame.tobytes())
                    count = scene.display_end - scene.transition_end
                    if count:
                        pixels = current.tobytes()
                        for _ in range(count):
                            pipe.write(pixels)
                    frame_index = scene.display_end
                    previous = current
            status = process.wait()
        except BrokenPipeError:
            status = process.wait()
            if not status:
                raise
        except BaseException:
            process.kill()
            process.wait()
            raise
        if status:
            errors.seek(0)
            raise ValueError("映像のエンコードに失敗しました。\n" + errors.read().decode("utf-8", "replace"))


def run(args):
    csv_path = args.csv.resolve()
    output_name = args.output_option or args.output or csv_path.with_suffix(".mp4")
    output = (csv_path.parent / output_name).resolve()
    audio_name = args.audio_option or args.audio
    audio = (csv_path.parent / audio_name).resolve() if audio_name else None
    if not shutil.which(args.ffmpeg):
        raise ValueError("FFmpegが見つかりません。PATHまたは --ffmpeg を確認してください")
    if output.suffix.lower() != ".mp4":
        raise ValueError("保存先の拡張子は .mp4 を指定してください")
    if audio and (audio.suffix.lower() != ".mp3" or not audio.is_file()):
        raise ValueError(f"MP3ファイルが見つからないか、拡張子が異なります: {audio}")
    scenes, milliseconds = read_timeline(csv_path, args.fps)
    if any(output == value.resolve() or (output.exists() and output.samefile(value))
           for value in [csv_path, *(scene.path for scene in scenes), *([audio] if audio else [])]):
        raise ValueError("入力ファイルと同じ場所には保存できません")
    if output.exists() and not args.overwrite:
        raise ValueError(f"保存先が既に存在します。上書きする場合は --overwrite を指定してください: {output}")
    print(f"{len(scenes)} シーン | 理論尺 {milliseconds} ms | "
          f"{scenes[-1].display_end} フレーム / {args.fps} fps", flush=True)

    WORK.mkdir(exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = args.aspect_ratio
    ffmpeg = [args.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin"]
    with TemporaryDirectory(prefix="scene-", dir=WORK) as temporary, \
            TemporaryDirectory(prefix=".scene-", dir=output.parent) as staging:
        final = Path(staging) / "output.mp4"
        video = Path(temporary) / "video.mp4" if audio else final
        command = ffmpeg + [
            "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
            "-framerate", str(args.fps), "-i", "pipe:0", "-an", "-c:v", CODECS[args.codec],
            "-preset", "veryfast", "-pix_fmt", "yuv420p",
        ]
        if args.codec == "h265":
            command += ["-tag:v", "hvc1"]
        render(command + ["-movflags", "+faststart", str(video)],
               scenes, (width, height), Path(temporary) / "ffmpeg.log")
        if audio:
            print("音声を組み込んでいます。", flush=True)
            result = subprocess.run(ffmpeg + [
                "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final),
            ], stderr=subprocess.PIPE)
            if result.returncode:
                raise ValueError("音声の組み込みに失敗しました。\n" + result.stderr.decode("utf-8", "replace"))
        if args.overwrite:
            final.replace(output)
        else:
            final.rename(output)  # On Windows this fails if another run created the target.
    print(f"出力: {output}")


def main():
    try:
        run(parse_args())
    except (OSError, ValueError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("中断しました。", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
