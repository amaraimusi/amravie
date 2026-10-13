import contextlib
import errno
import io
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from naskeeper.cli import parser, main
from naskeeper.backup_manager import run, validate
from naskeeper.state_manager import State, JobLock, atomic_json
from naskeeper.transfer import Transfer
from naskeeper.verification import fingerprint, digest
from naskeeper.logger import Progress
from naskeeper.error_handler import ConnectionGate, OfflineError


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parents[1] / "work"))
        self.root = Path(self.tmp.name)
        self.src, self.dst, self.local = [self.root / n for n in ("source", "destination", "local")]
        self.src.mkdir()
        self.options = parser().parse_args([str(self.src), str(self.dst), "--quiet", "--retry-wait", "0", "--reconnect-wait", "0", "--reconnect-attempts", "0"])
        self.logger = logging.getLogger("test")
        self.logger.addHandler(logging.NullHandler())
        self.stop = threading.Event()

    def tearDown(self):
        self.tmp.cleanup()

    def backup(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return run(self.src, self.dst, self.options, self.local, self.logger, self.stop)

    def put(self, rel, content=b"hello"):
        path = self.src / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def transfer(self):
        self.dst.mkdir(exist_ok=True)
        for folder in ("temp", "receipts", "versions"):
            (self.dst / ".naskeeper" / folder).mkdir(parents=True, exist_ok=True)
        state = State(self.local)
        return Transfer(self.src, self.dst, state, self.options, self.stop, Progress(1, 0, True), self.logger), state

    def test_basic_parallel_unicode_empty_and_differential(self):
        for rel in ("日本語 空白.mp4", "sub/a.jpg", "other/a.jpg", "sound.wav"):
            self.put(rel)
        (self.src / "empty").mkdir()
        (self.src / ".naskeeper").mkdir()
        self.put(".naskeeper/ignore")
        self.options.workers = 4
        self.assertEqual(self.backup(), 0)
        self.assertTrue((self.dst / "empty").is_dir())
        self.assertFalse((self.dst / ".naskeeper/ignore").exists())
        before = (self.dst / "sub/a.jpg").stat().st_mtime_ns
        self.assertEqual(self.backup(), 0)
        self.assertEqual(before, (self.dst / "sub/a.jpg").stat().st_mtime_ns)
        self.put("sub/a.jpg", b"updated")
        self.assertEqual(self.backup(), 0)
        self.assertEqual((self.dst / "sub/a.jpg").read_bytes(), b"updated")
        self.assertTrue(list((self.dst / ".naskeeper/versions").glob("*.bak")))
        (self.src / "sound.wav").unlink()
        self.assertEqual(self.backup(), 0)
        self.assertTrue((self.dst / "sound.wav").exists())

    def test_unknown_file_retained_other_file_continues(self):
        self.put("a", b"new")
        self.put("b")
        self.dst.mkdir()
        (self.dst / "a").write_bytes(b"old")
        self.assertEqual(self.backup(), 1)
        self.assertEqual((self.dst / "a").read_bytes(), b"old")
        self.assertEqual((self.dst / "b").read_bytes(), b"hello")

    def test_existing_identical_adopted(self):
        src = self.put("a")
        self.dst.mkdir()
        import shutil
        shutil.copy2(str(src), str(self.dst / "a"))
        self.assertEqual(self.backup(), 0)
        self.put("a", b"changed")
        self.assertEqual(self.backup(), 0)

    def test_zero_byte_file(self):
        self.put("empty.bin", b"")
        self.assertEqual(self.backup(), 0)
        self.assertEqual((self.dst / "empty.bin").stat().st_size, 0)
        self.assertEqual(self.backup(), 0)

    def test_partial_resume_corruption(self):
        src = self.put("a", b"a" * 1048576 + b"b" * 1048576 + b"c" * 100)
        transfer, state = self.transfer()
        try:
            dst, part, manifest, receipt = transfer.paths("a")
            part.write_bytes(b"a" * 1048576 + b"X" * 300)
            atomic_json(manifest, {"relative": "a", "source_root": str(self.src), "fingerprint": fingerprint(src)})
            self.assertEqual(transfer.process("a"), "copied")
            self.assertEqual(dst.read_bytes(), src.read_bytes())
            self.assertEqual(transfer.progress.bytes, src.stat().st_size - 1048576)
        finally:
            state.close()

    def test_changed_source_invalidates_partial(self):
        src = self.put("a", b"a" * 5000)
        transfer, state = self.transfer()
        try:
            dst, part, manifest, _ = transfer.paths("a")
            part.write_bytes(b"a" * 3000)
            atomic_json(manifest, {"relative": "a", "source_root": str(self.src), "fingerprint": fingerprint(src)})
            src.write_bytes(b"b" * 5000)
            transfer.process("a")
            self.assertEqual(dst.read_bytes(), b"b" * 5000)
            self.assertEqual(transfer.progress.bytes, 5000)
        finally:
            state.close()

    def test_graceful_interrupt_then_resume(self):
        src = self.put("a", b"A" * (3 * 1048576))
        transfer, state = self.transfer()
        original = transfer.progress.update
        def interrupt(*args, **kwargs):
            original(*args, **kwargs)
            self.stop.set()
        try:
            with patch.object(transfer.progress, "update", side_effect=interrupt):
                with self.assertRaises(InterruptedError):
                    transfer.process("a")
            self.assertFalse((self.dst / "a").exists())
            self.stop.clear()
            transfer.process("a")
            self.assertEqual(digest(src), digest(self.dst / "a"))
            self.assertEqual(transfer.progress.bytes, src.stat().st_size)
        finally:
            state.close()

    def test_source_changed_during_transfer_old_backup_survives(self):
        src = self.put("a", b"old")
        self.backup()
        src.write_bytes(b"A" * (2 * 1048576))
        transfer, state = self.transfer()
        original = transfer.progress.update
        def mutate(*args, **kwargs):
            original(*args, **kwargs)
            src.write_bytes(b"new source")
        try:
            with patch.object(transfer.progress, "update", side_effect=mutate):
                with self.assertRaises(OSError):
                    transfer.process("a")
            self.assertEqual((self.dst / "a").read_bytes(), b"old")
        finally:
            state.close()

    def test_local_database_lost_or_corrupted(self):
        self.put("a")
        self.assertEqual(self.backup(), 0)
        (self.local / "state.sqlite").unlink()
        self.assertEqual(self.backup(), 0)
        (self.local / "state.sqlite").write_bytes(b"corrupt")
        self.assertEqual(self.backup(), 0)
        self.assertTrue(list(self.local.glob("state.corrupt.*")))

    def test_finalize_failure_recovers(self):
        self.put("a")
        import naskeeper.transfer as module
        original = module.os.replace
        def fail(src, dst):
            if str(src).endswith(".part"):
                raise OSError(errno.EIO, "rename failure")
            return original(src, dst)
        self.options.retry = 0
        with patch.object(module.os, "replace", side_effect=fail):
            self.assertEqual(self.backup(), 1)
        self.assertFalse((self.dst / "a").exists())
        self.assertEqual(self.backup(), 0)
        self.assertEqual((self.dst / "a").read_bytes(), b"hello")

    def test_pending_receipt_recovery_after_replace(self):
        self.put("a")
        transfer, state = self.transfer()
        import naskeeper.transfer as module
        original = module.atomic_json
        def fail(path, data):
            if path.parent.name == "receipts" and not path.name.endswith("pending.json"):
                raise OSError(errno.EIO, "receipt failure")
            return original(path, data)
        try:
            with patch.object(module, "atomic_json", side_effect=fail):
                with self.assertRaises(OSError):
                    transfer.process("a")
            transfer.recover("a")
            self.assertEqual(transfer.process("a"), "skipped")
        finally:
            state.close()

    def test_file_errors_continue(self):
        for problem in (PermissionError(errno.EACCES, "locked"), FileNotFoundError(errno.ENOENT, "deleted"), OSError(errno.EIO, "write failed")):
            with self.subTest(problem=problem):
                self.put("a")
                self.put("b")
                original = Transfer.process
                def fail(obj, rel):
                    if rel == "a":
                        raise problem
                    return original(obj, rel)
                self.options.retry = 1
                with patch.object(Transfer, "process", autospec=True, side_effect=fail) as mocked:
                    self.assertEqual(self.backup(), 1)
                    attempts = sum(1 for call in mocked.call_args_list if call.args[1] == "a")
                    self.assertEqual(attempts, 2 if problem.errno == errno.EIO else 1)
                self.assertTrue((self.dst / "b").exists())

    def test_disk_full_stops_without_loop(self):
        self.put("a")
        self.put("b")
        with patch.object(Transfer, "process", side_effect=OSError(errno.ENOSPC, "disk full")) as mock:
            self.assertEqual(self.backup(), 1)
            self.assertEqual(mock.call_count, 1)
        self.assertFalse((self.dst / "b").exists())

    def test_offline_reconnect_is_bounded(self):
        self.dst.mkdir()
        gate = ConnectionGate(self.dst, self.stop, 0, 2, self.logger)
        with patch.object(Path, "stat", side_effect=OSError(errno.ENETUNREACH, "offline")) as mock:
            with self.assertRaises(OfflineError):
                gate.check()
            self.assertEqual(mock.call_count, 3)
        self.assertTrue(self.stop.is_set())

    def test_connection_recovers(self):
        self.dst.mkdir()
        (self.dst / ".naskeeper").mkdir()
        gate = ConnectionGate(self.dst, self.stop, 0, 2, self.logger)
        original = Path.stat
        calls = [0]
        def flaky(path, *args, **kwargs):
            calls[0] += 1
            if calls[0] == 1:
                raise OSError(errno.ENETUNREACH, "offline")
            return original(path, *args, **kwargs)
        with patch.object(Path, "stat", flaky):
            gate.check()
        self.assertFalse(self.stop.is_set())

    def test_double_job_lock(self):
        path = self.root / "lock"
        with JobLock(path):
            with self.assertRaises(RuntimeError):
                with JobLock(path):
                    pass
        with JobLock(path):
            pass

    def test_path_overlap(self):
        for destination in (self.src, self.src / "child", self.root):
            with self.assertRaises(ValueError):
                validate(self.src, destination, self.local)

    def test_dry_run_has_no_writes(self):
        self.put("a")
        self.options.dry_run = True
        self.assertEqual(self.backup(), 0)
        self.assertFalse(self.dst.exists())
        self.assertFalse(self.local.exists())

    def test_destination_permission_denied_other_files_continue(self):
        self.put("bad/a")
        self.put("good")
        original = Path.mkdir
        def denied(path, *args, **kwargs):
            if path == self.dst / "bad":
                raise PermissionError(errno.EACCES, "denied")
            return original(path, *args, **kwargs)
        with patch.object(Path, "mkdir", denied):
            self.assertEqual(self.backup(), 1)
        self.assertTrue((self.dst / "good").exists())

    def test_full_metadata_lost_rebuild(self):
        self.put("a")
        self.assertEqual(self.backup(), 0)
        import shutil
        shutil.rmtree(str(self.local))
        shutil.rmtree(str(self.dst / ".naskeeper"))
        self.assertEqual(self.backup(), 0)
        self.put("a", b"changed")
        self.assertEqual(self.backup(), 0)

    def test_ctrl_c_signal_handler_in_subprocess(self):
        self.put("a", b"A" * (3 * 1048576))
        tool_root = Path(__file__).resolve().parents[1]
        script = """import signal, sys, time
sys.path.insert(0, sys.argv[1])
from naskeeper.logger import Progress
from naskeeper.cli import main
original = Progress.update
def interrupt(self, *args, **kwargs):
    original(self, *args, **kwargs)
    signal.raise_signal(signal.SIGINT)
    time.sleep(.6)
Progress.update = interrupt
raise SystemExit(main(sys.argv[2:]))
"""
        result = subprocess.run([sys.executable, "-c", script, str(tool_root), str(self.src), str(self.dst), "--state-dir", str(self.local), "--_child", "--quiet"], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 130, result.stderr)
        self.assertFalse((self.dst / "a").exists())
        self.assertEqual(self.backup(), 0)
        self.assertEqual(digest(self.src / "a"), digest(self.dst / "a"))

    def test_watchdog_stops_blocked_process(self):
        self.put("a")
        tool = Path(__file__).resolve().parents[1] / "naskeeper.py"
        result = subprocess.run([sys.executable, str(tool), str(self.src), str(self.dst), "--state-dir", str(self.local), "--max-runtime", "0.001"], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 124)

    def test_symlink_cycle_and_destination_link(self):
        self.put("a")
        try:
            (self.src / "cycle").symlink_to(self.src, target_is_directory=True)
        except OSError:
            self.skipTest("Windowsシンボリックリンク権限なし（ジャンクションは別テスト）")
        self.assertEqual(self.backup(), 1)
        self.assertTrue((self.dst / "a").exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction")
    def test_junction_cycle(self):
        self.put("a")
        junction = self.src / "cycle"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(self.src)], capture_output=True)
        if result.returncode:
            self.skipTest("ジャンクション作成不可")
        try:
            self.assertEqual(self.backup(), 1)
            self.assertTrue((self.dst / "a").exists())
            self.assertFalse((self.dst / "cycle").exists())
        finally:
            junction.rmdir()

    def test_write_failure_mid_transfer_resumes(self):
        src = self.put("a", b"A" * (3 * 1048576))
        transfer, state = self.transfer()
        original = transfer.progress.update
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError(errno.EIO, "書き込み中の通信障害")
        try:
            with patch.object(transfer.progress, "update", side_effect=fail):
                with self.assertRaises(OSError):
                    transfer.process("a")
            self.assertFalse((self.dst / "a").exists())
            self.assertEqual(transfer.paths("a")[1].stat().st_size, 1048576)
            transfer.process("a")
            self.assertEqual(digest(src), digest(self.dst / "a"))
        finally:
            state.close()

    @unittest.skipUnless(os.name == "nt", "Windows sharing lock")
    def test_real_windows_source_file_lock(self):
        import ctypes
        src = self.put("a")
        self.put("b")
        kernel = ctypes.windll.kernel32
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong,
                                      ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
        handle = kernel.CreateFileW(str(src), 0x80000000, 0, None, 3, 0, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        self.options.retry = 1
        try:
            self.assertEqual(self.backup(), 1)
            self.assertFalse((self.dst / "a").exists())
            self.assertTrue((self.dst / "b").exists())
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
        self.assertEqual(self.backup(), 0)


if __name__ == "__main__":
    unittest.main()
