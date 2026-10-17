#!/usr/bin/env python3
"""FileTimeRename — ファイルの更新日時を名前に付与（Python 3.9以上）。"""

import argparse
from datetime import datetime
import os
from pathlib import Path
import re
import stat
import sys


PREFIX = re.compile(r"^[0-9]{8}_[0-9]{6}_.+")


def has_timestamp(name):
    """有効な年月日・時分秒が先頭にあれば二重付与を防ぐ。"""
    if not PREFIX.match(name):
        return False
    try:
        datetime.strptime(name[:15], "%Y%m%d_%H%M%S")
        return True
    except ValueError:
        return False


def is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x400
    )


def rename_no_replace(source, target):
    """既存の出力を上書きしない。同一フォルダ内でのみ使用する。"""
    if os.path.lexists(str(target)):
        raise FileExistsError("変更先が既に存在します: {}".format(target))
    if os.name == "nt":
        # Windowsのrenameは既存の変更先があると失敗する。
        os.rename(str(source), str(target))
    else:
        # POSIXのrenameは上書きするため、排他的なリンク作成を利用する。
        os.link(str(source), str(target), follow_symlinks=False)
        try:
            source.unlink()
        except OSError:
            target.unlink()
            raise


def run(directory, recursive=False, dry_run=False):
    counts = {"renamed": 0, "skipped": 0, "errors": 0}

    def report_error(path, error):
        counts["errors"] += 1
        print("[エラー] {}: {}".format(path, error), file=sys.stderr)

    def visit(folder):
        try:
            # 名前を変更しながら列挙しないよう、先に一覧を確定する。
            entries = sorted(folder.iterdir(), key=lambda p: p.name)
        except OSError as error:
            report_error(folder, error)
            return
        for source in entries:
            try:
                info = source.lstat()
                if is_link(info):
                    counts["skipped"] += 1
                    print("[スキップ: リンク] {}".format(source))
                elif stat.S_ISDIR(info.st_mode):
                    if recursive:
                        visit(source)
                elif stat.S_ISREG(info.st_mode):
                    if has_timestamp(source.name):
                        counts["skipped"] += 1
                        print("[スキップ: 日時付き] {}".format(source))
                        continue
                    prefix = datetime.fromtimestamp(info.st_mtime).strftime(
                        "%Y%m%d_%H%M%S_"
                    )
                    target = source.with_name(prefix + source.name)
                    if os.path.lexists(str(target)):
                        raise FileExistsError("変更先が既に存在します: {}".format(target))
                    if not dry_run:
                        rename_no_replace(source, target)
                    counts["renamed"] += 1
                    print("[{}] {} → {}".format(
                        "予定" if dry_run else "変更", source, target.name
                    ))
            except (OSError, ValueError, OverflowError) as error:
                report_error(source, error)

    visit(directory)
    print("{}: {} 件 / スキップ: {} 件 / エラー: {} 件".format(
        "変更予定" if dry_run else "変更", counts["renamed"],
        counts["skipped"], counts["errors"]
    ))
    return 1 if counts["errors"] else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="FileTimeRename（ファイル日時付与ツール）: 更新日時をファイル名の先頭に付与します。",
        epilog="形式: YYYYMMDD_HHMMSS_元の名前。ローカル時刻を使用。バックアップは作成しません。"
    )
    parser.add_argument("directory", type=Path, help="対象ディレクトリパス")
    parser.add_argument("-r", "--recursive", action="store_true", help="サブフォルダ内も処理")
    parser.add_argument("--dry-run", action="store_true", help="名前を変更せず処理予定を表示")
    args = parser.parse_args(argv)
    if not args.directory.is_dir():
        parser.error("対象ディレクトリが存在しないか、フォルダではありません。")
    if is_link(args.directory.lstat()):
        parser.error("対象にはリンクではなく実体のフォルダを指定してください。")
    try:
        return run(args.directory.resolve(), args.recursive, args.dry_run)
    except KeyboardInterrupt:
        print("\n中断しました。変更済みの名前はそのまま残ります。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
