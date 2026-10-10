#!/usr/bin/env python3
"""InstaThumbPad / サムネ余白メーカー。背景のみを伸縮して原寸で合成する。"""
import argparse
import math
from pathlib import Path
import sys


def margin_percent(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("余白率は数値（例: 20）で指定してください。")
    if not math.isfinite(number) or number < 0 or number > 1000:
        raise argparse.ArgumentTypeError("余白率は0～1000の有限な数値で指定してください。")
    return number


def create_image(background, thumbnail, output, margin):
    from PIL import Image, ImageOps

    background, thumbnail, output = map(Path, (background, thumbnail, output))
    for source in (background, thumbnail):
        if output.resolve() == source.resolve() or (output.exists() and output.samefile(source)):
            raise ValueError("入力画像を出力先には指定できません。")
    formats = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
    fmt = formats.get(output.suffix.lower())
    if fmt is None:
        raise ValueError("出力の拡張子は .png / .jpg / .jpeg / .webp にしてください。")
    with Image.open(background) as source:
        bg = ImageOps.exif_transpose(source).convert("RGBA")
    with Image.open(thumbnail) as source:
        thumb = ImageOps.exif_transpose(source).convert("RGBA")
    width = math.ceil(thumb.width * (1 + margin / 100))
    height = max(1, round(bg.height * width / bg.width))
    if height < thumb.height:
        needed = max(0, (thumb.height * bg.width / bg.height / thumb.width - 1) * 100)
        raise ValueError(f"背景の高さが不足します（{height} < {thumb.height}px）。"
                         f"縦長の背景を使うか、余白率を約{math.ceil(needed)}％以上にしてください。")
    if width * height > 80_000_000:
        raise ValueError("出力が8000万画素を超えます。余白率を小さくしてください。")
    canvas = bg.resize((width, height), getattr(Image, "Resampling", Image).LANCZOS)
    canvas.alpha_composite(thumb, ((width - thumb.width) // 2, (height - thumb.height) // 2))
    options = {}
    if fmt == "JPEG":
        flat = Image.new("RGB", canvas.size, "white")
        flat.paste(canvas, mask=canvas.getchannel("A"))
        canvas = flat
        options = {"quality": 95, "subsampling": 0}
    elif fmt == "WEBP":
        options = {"lossless": True}
    # Exclusive creation prevents accidental replacement, including concurrent runs.
    with output.open("xb") as stream:
        try:
            canvas.save(stream, format=fmt, **options)
        except Exception:
            stream.close()
            output.unlink()
            raise
    return width, height


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="InstaThumbPad / サムネ余白メーカー：サムネを原寸で背景の中央に配置します。",
        usage='%(prog)s 背景画像 元サムネ画像 [出力画像] 余白率')
    parser.add_argument("background", help="背景画像のパス")
    parser.add_argument("thumbnail", help="元サムネイル画像のパス")
    parser.add_argument("output", nargs="?", help="出力画像（省略時: 元画像名_instapad.png）")
    parser.add_argument("margin", type=margin_percent, help="左右合計の余白率。20 = 元画像幅の20％追加")
    args = parser.parse_args(argv)
    source = Path(args.thumbnail)
    output = Path(args.output) if args.output else source.with_name(source.stem + "_instapad.png")
    try:
        width, height = create_image(args.background, source, output, args.margin)
    except ImportError:
        parser.exit(1, "Pillowが必要です。python -m pip install Pillow を実行してください。\n")
    except (OSError, ValueError, ImageError) as exc:
        parser.exit(1, f"エラー: {exc}\n")
    print(f"作成しました: {output.resolve()}\n画像サイズ: {width} × {height}px / 余白率: {args.margin:g}％")
    return 0


# Pillow's decompression-bomb error is handled without requiring Pillow for --help.
try:
    from PIL.Image import DecompressionBombError as ImageError
except ImportError:
    ImageError = RuntimeError


if __name__ == "__main__":
    sys.exit(main())
