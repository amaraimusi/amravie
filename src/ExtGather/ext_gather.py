#!/usr/bin/env python3
"""ExtGather: recursively collect files using only the Python 3.9 standard library."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from datetime import datetime

MANIFEST = ".extgather.json"
LOCK = ".extgather.lock"


def path_key(path):
    return os.path.normcase(str(path.resolve()))


def inside(path, directory):
    return path == directory or directory in path.parents


def linked(path):
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def atomic_text(path, text):
    fd, name = tempfile.mkstemp(prefix=".extgather-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(name, str(path))
    finally:
        if os.path.exists(name):
            os.unlink(name)


def save_manifest(output, entries):
    atomic_text(output / MANIFEST, json.dumps(
        {"version": 1, "files": entries}, ensure_ascii=False, indent=2) + "\n")


def load_manifest(output):
    path = output / MANIFEST
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("files"), dict):
        raise ValueError("収集記録の形式が不正です。")
    entries = data["files"]
    names = {"readme.md", MANIFEST, LOCK}
    for key, entry in entries.items():
        if not isinstance(entry, dict):
            raise ValueError("収集記録の項目が不正です。")
        name = entry["name"]
        if (not isinstance(key, str) or not isinstance(entry["source"], str)
                or not isinstance(name, str) or not name
                or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
                or name in (".", "..") or name.endswith((".", " "))
                or name.casefold() in names):
            raise ValueError("収集記録に不正な出力名があります。")
        names.add(name.casefold())
    return entries


def choose_name(source, used):
    if source.name.casefold() not in used:
        return source.name
    parent = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", source.parent.name)[:40]
    digest = hashlib.sha256(path_key(source).encode("utf-8")).hexdigest()[:16]
    base = "{}__{}__{}".format(source.stem[:100], parent, digest)
    name = base + source.suffix
    number = 2
    while name.casefold() in used:
        name = "{}__{}{}".format(base, number, source.suffix)
        number += 1
    return name


def copy_atomic(source, target):
    fd, name = tempfile.mkstemp(prefix=".extgather-", dir=str(target.parent))
    os.close(fd)
    try:
        shutil.copy2(str(source), name)
        os.replace(name, str(target))
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_readme(output, entries, source, extension, counts):
    def cell(value):
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(
            "|", "&#124;").replace("\n", " ").replace("\r", " ")
    lines = ["# ExtGather 収集ファイル一覧", "",
             "最終実行: " + datetime.now().astimezone().isoformat(timespec="seconds"),
             "", "今回の探索先: " + str(source), "", "今回の拡張子: " + extension,
             "", "新規 {copied} / 更新 {updated} / スキップ {skipped} / エラー {errors}".format(**counts),
             "", "コピー元の更新日時を保持し、コピー元が新しい場合のみ更新します。",
             "過去に収集したファイルも一覧に保持します。元ファイルが削除されても収集先は削除しません。",
             "", "| 出力ファイル | コピー元（絶対パス） | 出力の最終更新日時 |",
             "| --- | --- | --- |"]
    for entry in sorted(entries.values(), key=lambda item: item["name"].casefold()):
        target = output / entry["name"]
        stamp = (datetime.fromtimestamp(target.stat().st_mtime).astimezone().isoformat(
            timespec="seconds") if target.is_file() else "未コピー／出力がありません")
        lines.append("| {} | {} | {} |".format(cell(entry["name"]), cell(entry["source"]), stamp))
    atomic_text(output / "README.md", "\n".join(lines) + "\n")


def gather(extension, source, output, dry_run=False):
    source, output = Path(source).resolve(), Path(output).resolve()
    extension = "." + extension.lstrip(".").casefold()
    if not re.fullmatch(r"\.[^<>:\"/\\|?*\s.]+", extension):
        raise ValueError("拡張子は srt または .srt のように指定してください。")
    if not source.is_dir():
        raise ValueError("探索対象のフォルダが存在しません: " + str(source))
    if inside(source, output):
        raise ValueError("探索先と出力先は別にしてください。探索先を含む親フォルダも出力先にできません。")
    counts = dict(copied=0, updated=0, skipped=0, errors=0)
    locked = False
    try:
        if not dry_run:
            output.mkdir(parents=True, exist_ok=True)
            try:
                with (output / LOCK).open("x", encoding="utf-8") as stream:
                    stream.write(str(os.getpid()))
                locked = True
            except FileExistsError:
                raise ValueError("収集中のロックがあります。実行中でなければ .extgather.lock を削除してください。")
        entries = load_manifest(output)
        used = {"readme.md", MANIFEST, LOCK}
        used.update(entry["name"].casefold() for entry in entries.values())
        if output.exists():
            used.update(path.name.casefold() for path in output.iterdir())

        def report_error(error):
            counts["errors"] += 1
            print("エラー: " + str(error), file=sys.stderr)

        for root, dirs, files in os.walk(str(source), followlinks=False, onerror=report_error):
            allowed = []
            for name in sorted(dirs, key=str.casefold):
                path = Path(root) / name
                try:
                    if not inside(path.resolve(), output) and not linked(path):
                        allowed.append(name)
                except OSError as error:
                    report_error(error)
            dirs[:] = allowed
            for name in sorted(files, key=str.casefold):
                path = Path(root) / name
                if path.suffix.casefold() != extension:
                    continue
                try:
                    if linked(path) or not path.is_file():
                        continue
                    key = path_key(path)
                    if key not in entries:
                        entries[key] = {"source": str(path.resolve()), "name": choose_name(path, used)}
                        used.add(entries[key]["name"].casefold())
                        # Record ownership before copying, so an interrupted run can resume.
                        if not dry_run:
                            save_manifest(output, entries)
                    target = output / entries[key]["name"]
                    exists = target.exists()
                    if target.is_symlink() or (exists and (linked(target) or not target.is_file())):
                        raise ValueError("出力先が通常のファイルではありません: " + str(target))
                    if exists and path.stat().st_mtime_ns <= target.stat().st_mtime_ns:
                        counts["skipped"] += 1
                        continue
                    if not dry_run:
                        copy_atomic(path, target)
                    counts["updated" if exists else "copied"] += 1
                    print("{}: {} -> {}".format("更新" if exists else "コピー", path, target.name))
                except (OSError, ValueError) as error:
                    report_error(error)
        if not dry_run:
            save_manifest(output, entries)
            write_readme(output, entries, source, extension, counts)
        print(("[確認のみ] " if dry_run else "") +
              "新規 {copied} / 更新 {updated} / スキップ {skipped} / エラー {errors}".format(**counts))
        return counts
    finally:
        if locked:
            (output / LOCK).unlink()


def main(argv=None):
    # CMD may use a legacy encoding that cannot represent every filename.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description="ExtGather — 拡張子別ファイル収集ツール")
    parser.add_argument("extension", help="拡張子（srt または .srt、大文字小文字は区別しません）")
    parser.add_argument("source", help="探索対象ディレクトリ（下層も探索）")
    parser.add_argument("output", help="出力ディレクトリ（探索対象外）")
    parser.add_argument("--dry-run", action="store_true", help="コピー予定を確認（ファイルを作成・変更しません）")
    args = parser.parse_args(argv)
    try:
        counts = gather(args.extension, args.source, args.output, args.dry_run)
        return 1 if counts["errors"] else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("エラー: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
