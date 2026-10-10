"""Behavior tests; fixture files stay in the requested work directory."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ext_gather import gather, MANIFEST


class GatherTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).parent / "work"
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=str(work))
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "input"
        self.output = self.source / "collected"
        self.source.mkdir()

    def file(self, name, value="subtitle", stamp=1600000000):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        os.utime(str(path), (stamp, stamp))
        return path

    def run_gather(self, dry=False, ext="srt"):
        with contextlib.redirect_stdout(io.StringIO()):
            return gather(ext, self.source, self.output, dry)

    def test_recursive_duplicates_exclusion_and_stable_names(self):
        first = self.file("a/字幕.srt", "first")
        second = self.file("b/deep/字幕.SRT", "second")
        self.file("ignored.txt")
        self.output.mkdir()
        (self.output / "existing.srt").write_text("existing")
        self.assertEqual(self.run_gather()["copied"], 2)
        manifest = json.loads((self.output / MANIFEST).read_text(encoding="utf-8"))
        names = [entry["name"] for entry in manifest["files"].values()]
        self.assertEqual(len(set(name.casefold() for name in names)), 2)
        self.assertEqual(self.run_gather()["skipped"], 2)
        self.file("0/new/字幕.srt", "third")
        self.assertEqual(self.run_gather()["copied"], 1)
        after = json.loads((self.output / MANIFEST).read_text(encoding="utf-8"))
        for key, entry in manifest["files"].items():
            self.assertEqual(after["files"][key], entry)
        readme = (self.output / "README.md").read_text(encoding="utf-8")
        self.assertIn(str(first.resolve()), readme)
        self.assertIn(str(second.resolve()), readme)

    def test_newer_equal_older_and_missing_output(self):
        path = self.file("a.srt", "old")
        self.run_gather()
        target = self.output / "a.srt"
        self.assertEqual(path.stat().st_mtime_ns, target.stat().st_mtime_ns)
        self.assertEqual(self.run_gather()["skipped"], 1)
        path.write_text("new")
        os.utime(str(path), (1700000000, 1700000000))
        self.assertEqual(self.run_gather()["updated"], 1)
        self.assertEqual(target.read_text(), "new")
        target.write_text("edited output")
        os.utime(str(target), (1800000000, 1800000000))
        self.assertEqual(self.run_gather()["skipped"], 1)
        self.assertEqual(target.read_text(), "edited output")
        target.unlink()
        self.assertEqual(self.run_gather()["copied"], 1)

    def test_dry_run_and_invalid_paths(self):
        self.file("a.srt")
        self.assertEqual(self.run_gather(True, ".SRT")["copied"], 1)
        self.assertFalse(self.output.exists())
        with self.assertRaises(ValueError):
            gather("srt", self.source, self.source)
        with self.assertRaises(ValueError):
            gather("srt", self.source, self.source.parent)
        with self.assertRaises(ValueError):
            self.run_gather(ext="*.srt")

    def test_reserved_metadata_and_untracked_file(self):
        self.file("README.md", "source readme")
        self.output.mkdir()
        (self.output / "README.md").write_text("previous report")
        self.assertEqual(self.run_gather(ext="md")["copied"], 1)
        entries = json.loads((self.output / MANIFEST).read_text(encoding="utf-8"))["files"]
        entry = next(iter(entries.values()))
        self.assertNotEqual(entry["name"].casefold(), "readme.md")
        self.assertEqual((self.output / entry["name"]).read_text(), "source readme")

    def test_malformed_manifest_and_lock(self):
        self.file("a.srt")
        self.output.mkdir()
        (self.output / MANIFEST).write_text(json.dumps({"version": 1, "files": {
            "key": {"name": "../escape.srt", "source": "a"}}}))
        with self.assertRaises(ValueError):
            self.run_gather()
        self.assertFalse((self.output / ".extgather.lock").exists())
        (self.output / ".extgather.lock").write_text("another process")
        with self.assertRaises(ValueError):
            self.run_gather()
        self.assertTrue((self.output / ".extgather.lock").exists())

    def test_untracked_output_is_not_overwritten(self):
        self.file("a.srt", "source")
        self.output.mkdir()
        (self.output / "a.srt").write_text("keep me")
        self.assertEqual(self.run_gather()["copied"], 1)
        self.assertEqual((self.output / "a.srt").read_text(), "keep me")
        self.assertEqual(self.run_gather()["skipped"], 1)

    def test_copy_error_continues_and_retries_same_name(self):
        self.file("a.srt")
        self.file("b.srt")
        import ext_gather
        original = ext_gather.copy_atomic

        def fail_one(source, target):
            if source.name == "a.srt":
                raise PermissionError("test access denied")
            original(source, target)

        with patch("ext_gather.copy_atomic", side_effect=fail_one):
            with contextlib.redirect_stderr(io.StringIO()):
                counts = self.run_gather()
        self.assertEqual(counts["errors"], 1)
        self.assertEqual(counts["copied"], 1)
        self.assertTrue((self.output / "b.srt").exists())
        self.assertEqual(self.run_gather()["copied"], 1)
        self.assertTrue((self.output / "a.srt").exists())


if __name__ == "__main__":
    unittest.main()
