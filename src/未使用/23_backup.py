# 23_backup.py
# -*- coding: utf-8 -*-

import os
import sys
import shutil
from typing import Tuple


def print_usage() -> None:
    print("使い方:")
    print("  python 23_backup.py <コピー元ディレクトリ> <コピー先ディレクトリ> <モード>")
    print("    第3引数: 0 = 上書きコピー, 1 = ミラーリング")


def validate_args(args: list) -> Tuple[str, str, int]:
    if len(args) != 4:
        print("引数の数が正しくありません。")
        print_usage()
        sys.exit(1)

    src_dir = os.path.abspath(args[1])
    dst_dir = os.path.abspath(args[2])

    try:
        mode = int(args[3])
    except ValueError:
        print("第3引数（モード）は 0 か 1 を指定してください。")
        sys.exit(1)

    if mode not in (0, 1):
        print("第3引数（モード）は 0 か 1 を指定してください。")
        sys.exit(1)

    if not os.path.isdir(src_dir):
        print(f"コピー元ディレクトリが存在しません: {src_dir}")
        sys.exit(1)

    if src_dir == dst_dir:
        print("コピー元とコピー先が同じです。処理を中止します。")
        sys.exit(1)

    return src_dir, dst_dir, mode


def is_same_file(src: str, dst: str) -> bool:
    try:
        src_stat = os.stat(src)
        dst_stat = os.stat(dst)
    except FileNotFoundError:
        return False

    src_mtime = int(src_stat.st_mtime)
    dst_mtime = int(dst_stat.st_mtime)

    if src_mtime != dst_mtime:
        return False

    if src_stat.st_size != dst_stat.st_size:
        return False

    return True


def copy_all(src_dir: str, dst_dir: str) -> None:
    total_files = 0
    copied_files = 0
    skipped_files = 0

    for root, dirs, files in os.walk(src_dir):
        rel_path = os.path.relpath(root, src_dir)
        target_root = dst_dir if rel_path == "." else os.path.join(dst_dir, rel_path)

        os.makedirs(target_root, exist_ok=True)

        for fname in files:
            src_path = os.path.join(root, fname)
            dst_path = os.path.join(target_root, fname)
            total_files += 1

            if os.path.islink(src_path):
                skipped_files += 1
                continue

            if os.path.exists(dst_path) and is_same_file(src_path, dst_path):
                skipped_files += 1
                continue

            try:
                shutil.copy2(src_path, dst_path)
                copied_files += 1
                print(f"[COPY] {src_path}  ->  {dst_path}")
            except Exception as e:
                print(f"[ERROR][COPY] {src_path} -> {dst_path} : {e}")

    print("---- コピー結果 ----")
    print(f"  対象ファイル数: {total_files}")
    print(f"  コピー実行:     {copied_files}")
    print(f"  スキップ:       {skipped_files}")


def mirror_delete(src_dir: str, dst_dir: str) -> None:
    deleted_files = 0
    deleted_dirs = 0

    for root, dirs, files in os.walk(dst_dir, topdown=False):
        rel_path = os.path.relpath(root, dst_dir)
        src_root = src_dir if rel_path == "." else os.path.join(src_dir, rel_path)

        for fname in files:
            dst_path = os.path.join(root, fname)
            src_path = os.path.join(src_root, fname)
            if not os.path.exists(src_path):
                try:
                    os.remove(dst_path)
                    deleted_files += 1
                    print(f"[DELETE FILE] {dst_path}")
                except Exception as e:
                    print(f"[ERROR][DELETE FILE] {dst_path} : {e}")

        for dname in dirs:
            dst_subdir = os.path.join(root, dname)
            src_subdir = os.path.join(src_root, dname)
            if not os.path.exists(src_subdir):
                try:
                    shutil.rmtree(dst_subdir)
                    deleted_dirs += 1
                    print(f"[DELETE DIR]  {dst_subdir}")
                except Exception as e:
                    print(f"[ERROR][DELETE DIR] {dst_subdir} : {e}")

    print("---- ミラーリング削除結果 ----")
    print(f"  削除ファイル数:   {deleted_files}")
    print(f"  削除ディレクトリ数: {deleted_dirs}")


def main() -> None:
    src_dir, dst_dir, mode = validate_args(sys.argv)

    print(f"コピー元: {src_dir}")
    print(f"コピー先: {dst_dir}")
    print(f"モード: {mode}")

    copy_all(src_dir, dst_dir)

    if mode == 1:
        print("不要ファイルを削除中...")
        mirror_delete(src_dir, dst_dir)

    print("バックアップ処理が完了しました。")


if __name__ == "__main__":
    main()
