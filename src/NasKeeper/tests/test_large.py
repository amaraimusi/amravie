"""NASKEEPER_LARGE_TEST=1 のときだけ2GiBの実プロセステストを実施。"""
import contextlib
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from naskeeper.verification import digest


@unittest.skipUnless(os.environ.get("NASKEEPER_LARGE_TEST") == "1", "2GiBテストは明示指定時のみ")
class LargeFileTest(unittest.TestCase):
    def test_forced_termination_and_resume_2gib(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=str(root / "work")) as tmp:
            folder = Path(tmp)
            source, destination, state = [folder / n for n in ("source", "destination", "state")]
            source.mkdir()
            file = source / "large.mp4"
            length = 2 * 1024 ** 3
            with file.open("wb") as f:
                if os.name == "nt":
                    import msvcrt
                    returned = ctypes.c_ulong()
                    ok = ctypes.windll.kernel32.DeviceIoControl(ctypes.c_void_p(msvcrt.get_osfhandle(f.fileno())), 0x900C4, None, 0, None, 0, ctypes.byref(returned), None)
                    self.assertTrue(ok, "スパースファイル設定失敗")
                f.truncate(length)
                f.seek(0)
                f.write(b"HEAD" * 1024)
                f.seek(length - 4096)
                f.write(b"TAIL" * 1024)
            command = [sys.executable, str(root / "naskeeper.py"), str(source), str(destination), "--state-dir", str(state), "--quiet", "--max-runtime", "0"]
            with (folder / "first-output.txt").open("wb") as output:
                child = subprocess.Popen(command, stdout=output, stderr=output)
                deadline = time.monotonic() + 30
                offset = 0
                while time.monotonic() < deadline:
                    parts = list((destination / ".naskeeper/temp").glob("*.part"))
                    if parts:
                        offset = parts[0].stat().st_size
                        if offset >= 64 * 1048576:
                            break
                    if child.poll() is not None:
                        break
                    time.sleep(.02)
                child.kill()
                child.wait(timeout=10)
            self.assertGreaterEqual(offset, 64 * 1048576)
            self.assertFalse((destination / "large.mp4").exists())
            part = next((destination / ".naskeeper/temp").glob("*.part"))
            # OSバッファに残った末尾も、次回は実ファイル全体を検証する。
            offset = part.stat().st_size
            started = time.monotonic()
            peak_working_set = 0
            with (folder / "resume-output.txt").open("wb") as output:
                child = subprocess.Popen(command, stdout=output, stderr=output)
                class Counters(ctypes.Structure):
                    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
                deadline = started + 180
                while child.poll() is None:
                    if time.monotonic() > deadline:
                        child.kill()
                        self.fail("大容量テストの180秒上限")
                    if os.name == "nt":
                        counter = Counters()
                        counter.cb = ctypes.sizeof(counter)
                        if ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(int(child._handle)), ctypes.byref(counter), counter.cb):
                            peak_working_set = max(peak_working_set, counter.PeakWorkingSetSize)
                    time.sleep(.05)
                self.assertEqual(child.returncode, 0, (folder / "resume-output.txt").read_text(encoding="utf-8", errors="replace"))
            elapsed = time.monotonic() - started
            self.assertEqual(digest(file), digest(destination / "large.mp4"))
            self.assertLess(peak_working_set, 256 * 1048576)
            db = __import__("sqlite3").connect(str(state / "state.sqlite"))
            self.assertEqual(db.execute("SELECT status,verified FROM files").fetchone(), ("completed", length))
            db.close()
            report = {"size_bytes": length, "verified_resume_bytes": offset,
                      "resumed_elapsed_seconds": round(elapsed, 3),
                      "peak_working_set_mib": round(peak_working_set / 1048576, 2),
                      "resumed_transfer_mib_per_second": round((length - offset) / elapsed / 1048576, 2),
                      "sha256_equal": True, "python": sys.version}
            (root / "work/large-test-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
