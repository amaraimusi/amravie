#!/usr/bin/env python3
"""CardSheet / 印刷シート画像作成ツール (Python 3.9)."""
import argparse
import math
from pathlib import Path
import sys


def positive_mm(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("サイズは正の有限な数値で指定してください。")
    return number


def create_sheet(cards, output=None, card_size=(63, 88), sheet_size=(127, 178),
                 image_format="png"):
    from PIL import Image, ImageOps

    cards = [Path(p) for p in cards]
    if not cards:
        raise ValueError("カード画像を1枚以上指定してください。")
    if any(not math.isfinite(v) or v <= 0 for v in (*card_size, *sheet_size)):
        raise ValueError("サイズは正の有限な数値で指定してください。")
    cw, ch = card_size
    sw, sh = sheet_size
    cols, rows = math.floor(sw / cw), math.floor(sh / ch)
    if not cols or not rows:
        raise ValueError("指定した用紙にカードが1枚も入りません。")
    fmt = image_format.lower()
    if fmt not in ("png", "jpeg", "jpg"):
        raise ValueError("出力形式はpngまたはjpegにしてください。")
    output = Path(output) if output else cards[0].with_name(cards[0].stem + "_cardsheet." + fmt)
    if output.suffix.lower() not in ((".png",) if fmt == "png" else (".jpg", ".jpeg")):
        raise ValueError("出力ファイルの拡張子と出力形式を一致させてください。")
    for card in cards:
        if output.resolve() == card.resolve() or (output.exists() and card.exists() and output.samefile(card)):
            raise ValueError("入力画像を出力先に指定できません。")
    if output.exists():
        raise FileExistsError("出力先は既に存在します: " + str(output))
    with Image.open(cards[0]) as source:
        first = ImageOps.exif_transpose(source).convert("RGBA")
    scale = first.width / cw
    width, height = max(1, round(sw * scale)), max(1, round(sh * scale))
    card_w, card_h = first.width, max(1, round(ch * scale))
    if width * height > 80_000_000:
        raise ValueError("出力が8000万画素を超えます。入力画像を縮小してください。")
    # Center the complete grid; cap rounding at the sheet's pixel boundary.
    card_w, card_h = min(card_w, width // cols), min(card_h, height // rows)
    if not card_w or not card_h:
        raise ValueError("入力画像の解像度が不足しています。")
    x0, y0 = (width - cols * card_w) // 2, (height - rows * card_h) // 2
    canvas = Image.new("RGB", (width, height), "white")
    count = min(len(cards), cols * rows)
    for i, path in enumerate(cards[:count]):
        if i == 0:
            card = first
        else:
            with Image.open(path) as source:
                card = ImageOps.exif_transpose(source).convert("RGBA")
        card = card.resize((card_w, card_h), getattr(Image, "Resampling", Image).LANCZOS)
        canvas.paste(card, (x0 + i % cols * card_w, y0 + i // cols * card_h), card)
    options = {"dpi": (width / sw * 25.4, height / sh * 25.4)}
    if fmt != "png":
        options.update(quality=95, subsampling=0)
    with output.open("xb") as stream:
        try:
            canvas.save(stream, format="PNG" if fmt == "png" else "JPEG", **options)
        except Exception:
            stream.close()
            output.unlink()
            raise
    return output, canvas.size, count, len(cards) - count, (cols, rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="CardSheet / 印刷シート画像作成ツール")
    parser.add_argument("cards", nargs="+", help="カード画像のパス（指定順に配置）")
    parser.add_argument("--card-size", nargs=2, type=positive_mm, default=(63, 88),
                        metavar=("幅mm", "高さmm"), help="カード実寸（既定: 63 88）")
    parser.add_argument("--sheet-size", nargs=2, type=positive_mm, default=(127, 178),
                        metavar=("幅mm", "高さmm"), help="用紙実寸（既定: 127 178 / 2L判）")
    parser.add_argument("--format", choices=("png", "jpeg", "jpg"), default=None,
                        help="出力形式（既定: png。出力パス指定時は拡張子から判定）")
    parser.add_argument("-o", "--output", help="出力ファイルのパス（既存ファイルは上書きしません）")
    args = parser.parse_args(argv)
    fmt = args.format or (Path(args.output).suffix.lstrip(".").lower() if args.output else "png")
    try:
        output, size, used, ignored, grid = create_sheet(
            args.cards, args.output, args.card_size, args.sheet_size, fmt)
    except ImportError:
        parser.exit(1, "Pillowが必要です: python -m pip install -r requirements.txt\n")
    except (OSError, ValueError) as exc:
        parser.exit(1, "エラー: {}\n".format(exc))
    print("作成しました: {}".format(output.resolve()))
    print("画像: {} × {}px / 用紙: {} × {}mm / 配置: {}列 × {}行".format(
        *size, *args.sheet_size, *grid))
    print("使用: {}枚 / 無視: {}枚".format(used, ignored))
    return 0


if __name__ == "__main__":
    sys.exit(main())
