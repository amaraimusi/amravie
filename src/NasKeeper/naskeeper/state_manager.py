import contextlib
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path


def atomic_json(path, data):
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(temp), str(path))
    finally:
        try:
            temp.unlink()
        except OSError:
            pass


def read_json(path):
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


class JobLock:
    """OSのバイト範囲ロック。終了・強制終了で解放される。"""
    def __init__(self, path):
        self.path = path
        self.file = None

    def __enter__(self):
        self.file = self.path.open("a+b")
        try:
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.file.seek(0, os.SEEK_END)
            if self.file.tell() == 0:
                self.file.write(b"0")
                self.file.flush()
        except OSError:
            self.file.close()
            self.file = None
            raise RuntimeError("同じ保存先のジョブが起動中、またはロックを取得できません")
        return self

    def __exit__(self, *args):
        if self.file:
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            self.file.close()


class State:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "state.sqlite"
        try:
            self.db = sqlite3.connect(str(path), check_same_thread=False)
            if self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("破損したDB")
        except sqlite3.DatabaseError:
            if hasattr(self, "db"):
                self.db.close()
            path.rename(path.with_name("state.corrupt." + uuid.uuid4().hex + ".sqlite"))
            self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS files (relative TEXT PRIMARY KEY, destination TEXT, size INTEGER, mtime INTEGER, identity TEXT, status TEXT, retries INTEGER, error TEXT, transferred INTEGER, verified INTEGER, completed TEXT)")
        self.db.commit()

    def update(self, rel, fp, status, retries=0, error="", transferred=0, verified=0):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (rel, rel, fp.get("size", 0), fp.get("mtime", 0), json.dumps(fp), status,
                 retries, error, transferred, verified,
                 time.strftime("%Y-%m-%dT%H:%M:%S%z") if status == "completed" else None))
            self.db.commit()

    def close(self):
        self.db.close()
