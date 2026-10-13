import errno
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from .scanner import scan
from .state_manager import State, JobLock
from .verification import fingerprint, safe_path
from .transfer import Transfer
from .error_handler import ConnectionGate, OfflineError, transient
from .logger import Progress


def validate(source, destination, state_dir):
    if not source.is_dir():
        raise ValueError("保存元ディレクトリが存在しません: " + str(source))
    # resolveにより既存のジャンクション・別表記の包含も検出する。
    for a, b in ((source, destination), (destination, source)):
        try:
            b.relative_to(a)
            raise ValueError("保存元と保存先の同一／包含関係は使用できません")
        except ValueError as exc:
            if str(exc).startswith("保存元"):
                raise
    for a, b in ((destination, state_dir), (source, state_dir)):
        try:
            b.relative_to(a)
            raise ValueError("状態保存先は保存元・保存先の外にあるPCローカルフォルダーを指定してください")
        except ValueError as exc:
            if str(exc).startswith("状態"):
                raise
    if os.name == "nt" and str(state_dir).startswith("\\"):
        raise ValueError("SQLiteの状態保存先にはUNCパスを指定できません")


def run(source, destination, options, state_dir, logger, stop):
    validate(source, destination, state_dir)
    started = time.monotonic()
    failures = []
    failure_lock = threading.Lock()
    def failed(rel, error):
        with failure_lock:
            failures.append((rel, str(error)))
        logger.error("FAILED %s: %s", rel, error)
    files, directories = scan(source, failed)
    logger.info("START source=%s destination=%s files=%d", source, destination, len(files))
    if options.dry_run:
        for rel in directories:
            print("DIRECTORY " + rel)
        for rel in files:
            dst = safe_path(destination, rel)
            print(("CHECK " if dst.exists() else "COPY ") + rel)
        print("対象 %d ファイル（dry-run: 書き込みなし）" % len(files))
        return 1 if failures else 0
    for attempt in range(options.reconnect_attempts + 1):
        try:
            destination.mkdir(parents=True, exist_ok=True)
            break
        except OSError as exc:
            if not transient(exc) or attempt == options.reconnect_attempts:
                raise
            logger.warning("起動時の保存先再接続 %d/%d: %s", attempt + 1, options.reconnect_attempts, exc)
            if stop.wait(options.reconnect_wait):
                return 130
    meta = safe_path(destination, ".naskeeper")
    meta.mkdir(exist_ok=True)
    for name in ("temp", "receipts", "versions"):
        safe_path(destination, ".naskeeper/" + name).mkdir(exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    with JobLock(state_dir / "job.lock"), JobLock(meta / "job.lock"):
        state = State(state_dir)
        total_bytes = 0
        for rel in files:
            try:
                total_bytes += fingerprint(source / rel)["size"]
            except OSError:
                pass
        progress = Progress(len(files), total_bytes, options.quiet)
        transfer = Transfer(source, destination, state, options, stop, progress, logger)
        gate = ConnectionGate(destination, stop, options.reconnect_wait, options.reconnect_attempts, logger)
        def worker(rel):
            fp = {}
            for attempt in range(options.retry + 1):
                try:
                    gate.check()
                    fp = fingerprint(source / rel)
                    transfer.recover(rel)
                    result = transfer.process(rel)
                    if attempt:
                        state.update(rel, fp, "completed", retries=attempt,
                                     transferred=fp["size"], verified=fp["size"])
                    return result
                except InterruptedError:
                    state.update(rel, fp, "interrupted", retries=attempt, error="中断")
                    return "interrupted"
                except Exception as exc:
                    logger.warning("処理失敗 %s attempt=%d: %s", rel, attempt, exc)
                    if isinstance(exc, OfflineError):
                        state.update(rel, fp, "deferred", retries=attempt, error=str(exc))
                        failed(rel, exc)
                        return "failed"
                    try:
                        gate.check()
                    except (OfflineError, InterruptedError) as offline:
                        state.update(rel, fp, "deferred", retries=attempt, error=str(offline))
                        failed(rel, offline)
                        return "failed"
                    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
                        stop.set()
                    if transient(exc) and attempt < options.retry and not stop.is_set():
                        state.update(rel, fp, "retrying", retries=attempt + 1, error=str(exc))
                        logger.info("RETRY %s %d/%d", rel, attempt + 1, options.retry)
                        if not stop.wait(options.retry_wait):
                            continue
                    state.update(rel, fp, "failed", retries=attempt, error=str(exc))
                    failed(rel, exc)
                    progress.update(rel, 0, fp.get("size", 0), finished=True, failed=True)
                    return "failed"
        try:
            for rel in directories:
                if stop.is_set():
                    break
                try:
                    gate.check()
                    safe_path(destination, rel).mkdir(parents=True, exist_ok=True)
                except Exception as exc:
                    failed(rel, exc)
            # 全ファイルを一度にsubmitしない。切断／中断時は未着手のまま保留する。
            with ThreadPoolExecutor(max_workers=options.workers) as pool:
                iterator = iter(files)
                active = {}
                while True:
                    while len(active) < options.workers and not stop.is_set():
                        rel = next(iterator, None)
                        if rel is None:
                            break
                        active[pool.submit(worker, rel)] = rel
                    if not active:
                        break
                    done, _ = wait(active, timeout=.5, return_when=FIRST_COMPLETED)
                    for future in done:
                        rel = active.pop(future)
                        result = future.result()
                        copied += result == "copied"
                        skipped += result == "skipped"
                        if result in ("copied", "skipped"):
                            progress.update(rel, 0, 0, finished=True)
        finally:
            state.close()
        elapsed = time.monotonic() - started
        remaining = len(files) - copied - skipped - sum(1 for r, e in failures if r in files)
        status = "INTERRUPTED / DEFERRED" if stop.is_set() else "COMPLETED WITH ERRORS" if failures else "COMPLETED"
        summary = ("\nNasKeeper - Backup Summary\nSource: %s\nDestination: %s\nTotal files: %d\nCopied: %d\nSkipped: %d\nFailed: %d\nDeferred: %d\nTransferred: %.2f GiB\nElapsed: %.1fs\nAvg speed: %.2f MiB/s\nStatus: %s" %
                   (source, destination, len(files), copied, skipped, len(failures), max(0, remaining), progress.bytes / 1073741824, elapsed, progress.bytes / max(elapsed, .001) / 1048576, status))
        print(summary)
        logger.info("END %s", summary)
        for rel, error in failures:
            print("  %s: %s" % (rel, error))
        return 130 if stop.is_set() and not failures else 1 if failures else 130 if stop.is_set() else 0
