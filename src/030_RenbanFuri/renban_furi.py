"""連番振り / RenbanFuri (Python 3.9+, standard library only)."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile


PREFIX = re.compile(r"^[0-9]{3,}_")


def make_plan(directory, start, step):
    directory = Path(directory).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("ディレクトリを指定してください。")
    if start < 0 or step <= 0:
        raise ValueError("開始番号は0以上、ステップは1以上にしてください。")
    files = sorted((p for p in directory.iterdir()
                    if not p.is_symlink() and p.is_file()), key=lambda p: p.name)
    plan = [(p, p.with_name("{:03d}_{}".format(
        start + i * step, PREFIX.sub("", p.name, count=1))))
        for i, p in enumerate(files)]
    # Compare case-insensitively even when tests run on a non-Windows host.
    names = [dst.name.casefold() for _, dst in plan]
    if len(names) != len(set(names)):
        raise ValueError("変更後のファイル名が重複しています。")
    sources = {src.name for src, _ in plan}
    occupied = {p.name.casefold(): p.name for p in directory.iterdir()}
    for _, dst in plan:
        existing = occupied.get(dst.name.casefold())
        if existing is not None and existing not in sources:
            raise ValueError("変更先が既に存在します: " + dst.name)
    return plan


def move_file(source, target):
    """Windows rename refuses to overwrite; also check broken symlinks."""
    if os.path.lexists(str(target)):
        raise FileExistsError("変更先が既に存在します: " + str(target))
    source.rename(target)


def apply_plan(plan):
    changes = [(src, dst) for src, dst in plan if src != dst]
    if not changes:
        return 0
    staging = Path(tempfile.mkdtemp(prefix=".renbanfuri-", dir=str(changes[0][0].parent)))
    rows = [(src, staging / str(i), dst) for i, (src, dst) in enumerate(changes)]
    journal = staging / "recovery.json"
    locations = [src for src, _, _ in rows]
    try:
        journal.write_text(json.dumps([
            {"original": str(src), "temporary": str(tmp), "destination": str(dst)}
            for src, tmp, dst in rows], ensure_ascii=False, indent=2), encoding="utf-8")
        for i, (src, tmp, _) in enumerate(rows):
            move_file(src, tmp)
            locations[i] = tmp
        for i, (_, tmp, dst) in enumerate(rows):
            move_file(tmp, dst)
            locations[i] = dst
    except (OSError, KeyboardInterrupt) as error:
        failures = []
        # First vacate final names, which may be another file's original name.
        for i, (src, tmp, dst) in enumerate(rows):
            if locations[i] == dst and locations[i] != src:
                try:
                    move_file(dst, tmp)
                    locations[i] = tmp
                except OSError as rollback_error:
                    failures.append(str(rollback_error))
        for i, (src, _, _) in enumerate(rows):
            if locations[i] != src:
                try:
                    move_file(locations[i], src)
                    locations[i] = src
                except OSError as rollback_error:
                    failures.append(str(rollback_error))
        if failures:
            raise RuntimeError("処理失敗。復旧が一部未完了です。対応表: {}\n{}".format(
                journal, "\n".join(failures))) from error
        if journal.exists():
            journal.unlink()
        staging.rmdir()
        raise RuntimeError("処理を中止し、元の名前に復旧しました: " + str(error)) from error
    # Cleanup failure must not trigger rollback after a successful rename.
    try:
        journal.unlink()
        staging.rmdir()
    except OSError as error:
        print("警告: 変更は完了しました。一時フォルダの削除に失敗: {} ({})".format(
            staging, error), file=sys.stderr)
    return len(changes)


def main(argv=None):
    parser = argparse.ArgumentParser(description="連番振り (030 RenbanFuri): ファイル名順に連番を付与・置換")
    parser.add_argument("directory", help="対象ディレクトリ（直下の通常ファイルのみ）")
    parser.add_argument("start", type=int, help="開始番号（0以上）")
    parser.add_argument("step", type=int, help="ステップ（1以上）")
    parser.add_argument("--dry-run", action="store_true", help="変更予定のみ表示")
    args = parser.parse_args(argv)
    try:
        plan = make_plan(args.directory, args.start, args.step)
        for src, dst in plan:
            print("{} -> {}{}".format(src.name, dst.name, "（変更なし）" if src == dst else ""))
        if args.dry_run:
            print("確認のみ: {} ファイル（変更していません）".format(len(plan)))
        else:
            print("完了: {} / {} ファイルを変更".format(apply_plan(plan), len(plan)))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print("エラー: " + str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("中止しました。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
