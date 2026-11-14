"""四隅につながる背景だけを透明化する Python 3.9 CLI。"""
import argparse
from collections import deque
import math
from pathlib import Path
import sys

try:
    from PIL import Image
except ImportError:
    raise SystemExit("Pillow が必要です。python -m pip install -r requirements.txt を実行してください。")


def remove_background(image, tolerance=0.10):
    """RGB最大成分差 / 255 で判定。各隅の固定色で4近傍探索する。"""
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 1:
        raise ValueError("許容値は0.0～1.0にしてください。")
    result = image.convert("RGBA")
    width, height = result.size
    original = result.tobytes()
    output = bytearray(original)
    limit = tolerance * 255
    corners = sorted(set((0, width - 1, (height - 1) * width, width * height - 1)))
    # 同色の隅は一度に探索し、異なる色の探索とは訪問状態を分ける。
    groups = {}
    for index in corners:
        offset = index * 4
        color = tuple(original[offset:offset + 3]) if original[offset + 3] else None
        groups.setdefault(color, []).append(index)
    for color, seeds in groups.items():
        visited = bytearray(width * height)
        queue = deque(seeds)
        for index in seeds:
            visited[index] = 1
        while queue:
            index = queue.popleft()
            offset = index * 4
            alpha = original[offset + 3]
            # 完全透明の隅は色候補にせず、透明領域だけを探索する。
            if alpha and (color is None or max(abs(original[offset + c] - color[c]) for c in range(3)) > limit):
                continue
            output[offset + 3] = 0
            x = index % width
            neighbors = []
            if x:
                neighbors.append(index - 1)
            if x + 1 < width:
                neighbors.append(index + 1)
            if index >= width:
                neighbors.append(index - width)
            if index + width < width * height:
                neighbors.append(index + width)
            for neighbor in neighbors:
                if not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)
    return Image.frombytes("RGBA", result.size, bytes(output))


def tolerance_value(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("許容値には0.0～1.0の数値を指定してください。")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise argparse.ArgumentTypeError("許容値は0.0～1.0にしてください。")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="PNG背景透明化ツール：四隅につながる背景を透明化します。")
    parser.add_argument("input", type=Path, help="PNGファイル、またはPNGを含むフォルダ（直下のみ）")
    parser.add_argument("--output", "-o", type=Path, help="出力フォルダ。指定時は元のファイル名で保存")
    parser.add_argument("--tolerance", type=tolerance_value, default=0.10, help="色の許容値0.0～1.0（既定: 0.10）")
    args = parser.parse_args(argv)
    source = args.input.resolve()
    try:
        if source.is_dir():
            files = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() == ".png" and not p.stem.lower().endswith("_transparent"))
            default_dir = source
        elif source.is_file() and source.suffix.lower() == ".png":
            files = [source]
            default_dir = source.parent
        else:
            raise ValueError("入力には存在するPNGファイルまたはフォルダを指定してください。")
        if not files:
            raise ValueError("処理対象のPNG画像がありません（*_transparent.png は一括処理から除外）。")
        output_dir = args.output.resolve() if args.output else default_dir
        targets = [output_dir / (p.name if args.output else p.stem + "_transparent.png") for p in files]
        # 上書き保存先が入力のどれかと一致する場合は、処理前に全体を拒否。
        if any(target.resolve() in files for target in targets):
            raise ValueError("出力先が元画像と同じです。別の出力フォルダを指定してください。")
        output_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        print("エラー: {}".format(exc), file=sys.stderr)
        return 1
    errors = 0
    for source_file, target in zip(files, targets):
        try:
            if target.exists() and source_file.samefile(target):
                raise ValueError("出力先が元画像と同一です。")
            with Image.open(source_file) as image:
                if image.format != "PNG":
                    raise ValueError("拡張子はPNGですが、内容がPNG形式ではありません。")
                if getattr(image, "n_frames", 1) > 1:
                    raise ValueError("アニメーションPNGには対応していません。")
                result = remove_background(image, args.tolerance)
            result.save(target, format="PNG")
            print("保存: {}".format(target))
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            errors += 1
            print("エラー: {}: {}".format(source_file.name, exc), file=sys.stderr)
    print("完了: 成功 {} 件 / 失敗 {} 件".format(len(files) - errors, errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
