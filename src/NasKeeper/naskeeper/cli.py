import argparse
import hashlib
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from . import __version__
from .backup_manager import run, validate
from .logger import make_logger


def size(value):
    text = value.upper().strip()
    factors = {"KIB": 1024, "MIB": 1048576, "GIB": 1073741824, "KB": 1000, "MB": 1000000, "GB": 1000000000}
    try:
        for suffix, factor in factors.items():
            if text.endswith(suffix):
                result = int(float(text[:-len(suffix)]) * factor)
                break
        else:
            result = int(text)
        if not 4096 <= result <= 64 * 1048576:
            raise ValueError()
        return result
    except ValueError:
        raise argparse.ArgumentTypeError("4096～64MiBを指定してください（例: 1MiB）")


def nonnegative(value):
    try:
        number = float(value)
        if number < 0 or not number < float("inf"):
            raise ValueError()
        return number
    except ValueError:
        raise argparse.ArgumentTypeError("0以上の有限数を指定してください")


def count(value):
    try:
        n = int(value)
        if n < 0:
            raise ValueError()
        return n
    except ValueError:
        raise argparse.ArgumentTypeError("0以上の整数を指定してください")


def parser():
    p = argparse.ArgumentParser(description="NasKeeper： NASバックアップ管理ツール")
    p.add_argument("source", help="保存元ディレクトリ")
    p.add_argument("destination", help="保存先ディレクトリ（UNC可）")
    p.add_argument("--workers", type=int, choices=range(1, 5), default=1)
    p.add_argument("--buffer-size", type=size, default=1048576)
    p.add_argument("--retry", type=count, default=3)
    p.add_argument("--retry-wait", type=nonnegative, default=5)
    p.add_argument("--reconnect-wait", type=nonnegative, default=30)
    p.add_argument("--reconnect-attempts", type=count, default=20)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--resume", dest="resume", action="store_true", default=True)
    group.add_argument("--no-resume", dest="resume", action="store_false")
    p.add_argument("--verify", choices=("size", "hash"), default="hash")
    p.add_argument("--mtime-tolerance", type=nonnegative, default=0)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--keep-versions", dest="keep_versions", action="store_true", default=True)
    group.add_argument("--no-keep-versions", dest="keep_versions", action="store_false")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--max-runtime", type=nonnegative, default=43200, help="実行全体の上限秒。既定12時間、0は無制限")
    p.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--log", type=Path)
    p.add_argument("--state-dir", type=Path)
    p.add_argument("--version", action="version", version="NasKeeper " + __version__)
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    options = parser().parse_args(argv)
    if options.max_runtime and not options._child:
        arguments = list(argv) if argv is not None else sys.argv[1:]
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "naskeeper.py")] + arguments + ["--_child"]
        child = subprocess.Popen(command)
        try:
            return child.wait(timeout=options.max_runtime)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            print("実行時間の上限に達したため停止しました。部分ファイルから次回再開できます。", file=sys.stderr)
            return 124
        except KeyboardInterrupt:
            # Ctrl+Cは同じコンソールの子にも配送される。応答しない場合は強制停止。
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            return 130
    source, destination = Path(options.source).resolve(), Path(options.destination).resolve()
    key = hashlib.sha256(os.path.normcase(str(destination)).encode("utf-8")).hexdigest()[:24]
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "NasKeeper"
    state_dir = options.state_dir.resolve() if options.state_dir else base / key
    stop = threading.Event()
    old_signal = signal.getsignal(signal.SIGINT)
    def interrupt(signum, frame):
        stop.set()
    signal.signal(signal.SIGINT, interrupt)
    try:
        validate(source, destination, state_dir)
        if options.dry_run:
            logger = logging.getLogger("naskeeper.dryrun")
            logger.addHandler(logging.NullHandler())
        else:
            log = options.log or state_dir / "logs" / (time.strftime("%Y%m%d-%H%M%S") + "-%d.log" % os.getpid())
            log = log.resolve()
            for protected in (source, destination):
                try:
                    log.relative_to(protected)
                except ValueError:
                    continue
                raise ValueError("ログは保存元・保存先の外のローカルフォルダーに指定してください")
            log.parent.mkdir(parents=True, exist_ok=True)
            logger = make_logger(log)
            print("ログ: " + str(log))
        return run(source, destination, options, state_dir, logger, stop)
    except (OSError, ValueError, RuntimeError) as exc:
        print("エラー: " + str(exc), file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGINT, old_signal)
