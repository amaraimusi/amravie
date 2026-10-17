"""標準ライブラリだけで実行する回帰テスト。"""
import contextlib
from datetime import datetime
import io
import os
from pathlib import Path
import tempfile
import unittest

import file_time_rename as tool


class RenameTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).parent / "work"
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=str(work))
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def create(self, name="MOV_0123.mp4"):
        path = self.folder / name
        path.write_bytes(b"sample content\x00\xff")
        timestamp = datetime(2026, 10, 15, 9, 30, 25).timestamp()
        os.utime(str(path), (timestamp, timestamp))
        return path

    def run_tool(self, **options):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return tool.run(self.folder, **options)

    def test_name_content_mtime_and_repeat(self):
        source = self.create()
        before = source.stat().st_mtime_ns
        content = source.read_bytes()
        self.assertEqual(self.run_tool(), 0)
        target = self.folder / "20261015_093025_MOV_0123.mp4"
        self.assertFalse(source.exists())
        self.assertEqual(target.read_bytes(), content)
        self.assertEqual(target.stat().st_mtime_ns, before)
        self.assertEqual(self.run_tool(), 0)
        self.assertEqual(list(self.folder.iterdir()), [target])

    def test_dry_run(self):
        source = self.create()
        self.assertEqual(self.run_tool(dry_run=True), 0)
        self.assertEqual(list(self.folder.iterdir()), [source])

    def test_collision_continues_without_overwrite(self):
        source = self.create()
        target = self.folder / "20261015_093025_MOV_0123.mp4"
        target.write_bytes(b"keep")
        self.create("other.txt")
        self.assertEqual(self.run_tool(), 1)
        self.assertTrue(source.exists())
        self.assertEqual(target.read_bytes(), b"keep")
        self.assertTrue((self.folder / "20261015_093025_other.txt").exists())

    def test_recursive_is_optional(self):
        child = self.folder / "sub"
        child.mkdir()
        source = self.create()
        source.rename(child / source.name)
        self.assertEqual(self.run_tool(), 0)
        self.assertTrue((child / source.name).exists())
        self.assertEqual(self.run_tool(recursive=True), 0)
        self.assertTrue((child / "20261015_093025_MOV_0123.mp4").exists())

    def test_japanese_extensionless_and_old_prefix(self):
        for name in ("日本語 空白.txt", "拡張子なし", "26_0913_MOV.mp4", ".hidden"):
            self.create(name)
        self.assertEqual(self.run_tool(), 0)
        for name in ("日本語 空白.txt", "拡張子なし", "26_0913_MOV.mp4", ".hidden"):
            self.assertTrue((self.folder / ("20261015_093025_" + name)).exists())

    def test_prefix_validation(self):
        self.assertTrue(tool.has_timestamp("20261015_093025_a.mp4"))
        self.assertFalse(tool.has_timestamp("20260230_093025_a.mp4"))
        self.assertFalse(tool.has_timestamp("20261015_250000_a.mp4"))

    def test_invalid_directory(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                tool.main([str(self.folder / "missing")])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
