import tempfile
import unittest
from unittest import mock
from decimal import Decimal
from pathlib import Path

import clip_joiner as cj


class ClipJoinerTests(unittest.TestCase):
    def test_natural_sort(self):
        paths = [Path("scene10.mp4"), Path("scene2.MP4"), Path("scene1.mp4")]
        self.assertEqual([p.name for p in cj.sort_files(paths, "name", False)],
                         ["scene1.mp4", "scene2.MP4", "scene10.mp4"])

    def test_timestamp_rounding_and_long_duration(self):
        self.assertEqual(cj.format_timestamp(Decimal("5538.2746")), "01:32:18.275")

    def test_positions_are_decimal_and_continuous(self):
        items = [(Path("a.mp4"), {"_duration_decimal": Decimal("10.500")}),
                 (Path("b.mp4"), {"_duration_decimal": Decimal("7.250")})]
        clips = cj.calculate_clip_positions(items)
        self.assertEqual(clips[1].start, Decimal("10.500"))
        self.assertEqual(clips[1].end, Decimal("17.750"))

    def test_case_insensitive_mp4_discovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "a.MP4").touch()
            (root / "memo.txt").touch()
            self.assertEqual([p.name for p in cj.find_mp4_files(root)], ["a.MP4"])

    def test_replace_retries_a_temporary_windows_lock(self):
        locked = PermissionError(13, "locked")
        locked.winerror = 32
        with mock.patch.object(cj.os, "replace", side_effect=[locked, None]) as replace, \
             mock.patch.object(cj.time, "sleep") as sleep:
            cj._replace_with_retry(Path("temporary.mp4"), Path("final.mp4"))
        self.assertEqual(replace.call_count, 2)
        sleep.assert_called_once_with(0.25)


if __name__ == "__main__":
    unittest.main()
