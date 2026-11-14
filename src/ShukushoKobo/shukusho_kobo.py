"""縮小工房: ディレクトリ内の画像を安全に一括縮小する。Python 3.9。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import sys
import tempfile
import time

from PIL import Image, ImageOps


EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff', '.gif'}
FORMATS = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP'}
LANCZOS = getattr(Image, 'Resampling', Image).LANCZOS


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('1以上を指定してください')
    return number


def convert(source, target, size, quality):
    """一時ファイルで完成させてから、上書きせず出力する。"""
    temporary = None
    try:
        if target.exists():
            return 'SKIP', source.name, '出力先に同名ファイルがあります'
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original)
            # パレット透過も維持。アニメーションは先頭フレームのみ扱う。
            has_alpha = 'A' in image.getbands() or 'transparency' in image.info
            image = image.convert('RGBA' if has_alpha else 'RGB')
            # 片方が未指定なら元の寸法を上限にし、指定した辺だけで縮小率を決める。
            bounds = (size[0] or image.width, size[1] or image.height)
            image.thumbnail(bounds, LANCZOS, reducing_gap=3.0)
            output_format = FORMATS[target.suffix.lower()]
            if output_format == 'JPEG' and image.mode == 'RGBA':
                background = Image.new('RGB', image.size, 'white')
                background.paste(image, mask=image.getchannel('A'))
                image = background
            options = {}
            if output_format == 'JPEG':
                options = {'quality': quality, 'optimize': True, 'progressive': True}
            elif output_format == 'WEBP':
                options = {'quality': quality, 'method': 4}
            # GPS等の元メタデータは出力しない。色プロファイルは保持する。
            icc = original.info.get('icc_profile')
            if icc:
                options['icc_profile'] = icc
            descriptor, temporary = tempfile.mkstemp(prefix='.shukusho-', suffix='.tmp', dir=target.parent)
            os.close(descriptor)
            image.save(temporary, format=output_format, **options)
            dimensions = image.size
        # ハードリンクの作成は既存ファイルを置換しない。非対応環境では排他作成する。
        try:
            os.link(temporary, target)
        except FileExistsError:
            return 'SKIP', source.name, '出力先に同名ファイルがあります'
        except OSError:
            import shutil
            try:
                destination = target.open('xb')
            except FileExistsError:
                return 'SKIP', source.name, '出力先に同名ファイルがあります'
            try:
                with destination, open(temporary, 'rb') as stream:
                    shutil.copyfileobj(stream, destination)
            except Exception:
                target.unlink()
                raise
        return 'OK', source.name, '{} ({}×{})'.format(target.name, *dimensions)
    except Exception as error:
        return 'ERROR', source.name, str(error)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    # Windowsのリダイレクト先がCP932でも、特殊なファイル名で停止しない。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(errors='backslashreplace')
    parser = argparse.ArgumentParser(description='縮小工房 - フォルダ内の画像を縦横比を維持して一括縮小')
    parser.add_argument('input', type=Path, help='対象フォルダ（直下のみ）')
    parser.add_argument('output', type=Path, nargs='?', help='出力フォルダ（省略: 入力名_resized）')
    parser.add_argument('--width', type=positive, help='最大幅 px（高さのみ指定時は自動計算。両方省略時: 400）')
    parser.add_argument('--height', type=positive, help='最大高さ px（幅のみ指定時は自動計算。両方省略時: 400）')
    parser.add_argument('--format', choices=['keep', 'png', 'jpeg', 'webp'], default='keep', help='出力形式（既定: keep）')
    parser.add_argument('--quality', type=positive, default=85, help='JPEG/WebP品質 1-100（既定: 85）')
    parser.add_argument('--workers', type=positive, default=min(4, os.cpu_count() or 1), help='同時処理数（既定: 最大4）')
    args = parser.parse_args(argv)
    if args.width is None and args.height is None:
        args.width = args.height = 400
    if args.quality > 100:
        parser.error('--quality は1〜100で指定してください')
    source = args.input.resolve()
    if not source.is_dir():
        parser.error('対象フォルダが存在しません: {}'.format(source))
    output = args.output.resolve() if args.output else source.with_name(source.name + '_resized')
    if output == source:
        parser.error('入力と出力には異なるフォルダを指定してください')
    try:
        files = sorted((p for p in source.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS), key=lambda p: p.name.lower())
        output.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        parser.error(str(error))
    jobs = []
    reserved = set()
    collisions = []
    for path in files:
        suffix = path.suffix.lower() if args.format == 'keep' else '.' + args.format
        if suffix == '.jpeg':
            suffix = '.jpg' if args.format != 'keep' else suffix
        if suffix not in FORMATS:
            suffix = '.png'
        target = output / (path.stem + suffix)
        key = target.name.casefold()
        if key in reserved:
            collisions.append(('ERROR', path.name, '形式変換後のファイル名が重複: ' + target.name))
        else:
            reserved.add(key)
            jobs.append((path, target))
    print('対象: {}枚 / 出力先: {}'.format(len(files), output))
    started = time.monotonic()
    counts = {'OK': 0, 'SKIP': 0, 'ERROR': 0}
    def process(job):
        return convert(job[0], job[1], (args.width, args.height), args.quality)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for status, name, detail in executor.map(process, jobs):
            counts[status] += 1
            print('[{}] {} → {}'.format(status, name, detail))
    for status, name, detail in collisions:
        counts[status] += 1
        print('[{}] {} → {}'.format(status, name, detail))
    print('完了: 成功 {OK} / スキップ {SKIP} / 失敗 {ERROR} / '.format(**counts) + '{:.1f}秒'.format(time.monotonic() - started))
    return 1 if counts['ERROR'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
