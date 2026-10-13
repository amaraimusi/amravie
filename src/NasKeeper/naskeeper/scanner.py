import os
from pathlib import Path
from .verification import is_link


def scan(root, on_error, exclusions=()):
    files, directories = [], []
    excluded = {os.path.normcase(str(p.resolve())) for p in exclusions}
    def visit(folder):
        try:
            with os.scandir(str(folder)) as entries:
                items = sorted(entries, key=lambda e: e.name.casefold())
            for entry in items:
                path = Path(entry.path)
                rel = path.relative_to(root).as_posix()
                try:
                    if entry.name.casefold() == ".naskeeper" or os.path.normcase(str(path.resolve())) in excluded:
                        continue
                    if is_link(path):
                        on_error(rel, "リンク／ジャンクションは探索対象外")
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        directories.append(rel)
                        visit(path)
                    elif entry.is_file(follow_symlinks=False):
                        files.append(rel)
                except OSError as exc:
                    on_error(rel, str(exc))
        except OSError as exc:
            on_error(str(folder.relative_to(root)), str(exc))
    visit(root)
    return files, directories
