import hashlib
import os
from pathlib import Path


def fingerprint(path):
    st = path.stat()
    return {"size": st.st_size, "mtime": st.st_mtime_ns,
            "device": st.st_dev, "inode": st.st_ino}


def digest(path, buffer_size=1024 * 1024, stop=None):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            if stop is not None and stop.is_set():
                raise InterruptedError("中断されました")
            block = f.read(buffer_size)
            if not block:
                return h.hexdigest()
            h.update(block)


def is_link(path):
    # Windowsのジャンクションを含め、reparse pointは追跡しない。
    st = path.lstat()
    return path.is_symlink() or bool(getattr(st, "st_file_attributes", 0) & 0x400)


def safe_path(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("不正な相対パス")
    result = root / rel
    current = root
    for part in rel.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if is_link(current):
                raise OSError("保存先のリンク／ジャンクションは使用できません: " + str(current))
    return result
