"""Run: python -m unittest discover -s src/FramePick -v"""
import csv
from decimal import Decimal
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import frame_pick


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
class ExtractionTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).parent / "work"
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=str(work))
        self.root = Path(self.temp.name)
        self.video = self.root / "日本語 sample.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=160x90:rate=2:duration=3", "-c:v", "mpeg4",
                        str(self.video)], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def rows(self, output):
        with (output / "frames.txt").open(encoding="utf-8-sig") as stream:
            for _ in range(5):
                next(stream)
            return list(csv.DictReader(stream, delimiter="\t"))

    def test_real_timestamps_range_png_and_resize(self):
        output = self.root / "images"
        args = frame_pick.parser().parse_args([str(self.video), str(output),
                  "--start", "0.3", "--interval", "0.7", "--end", "2.1",
                  "--format", "png", "--max-width", "80"])
        self.assertEqual(frame_pick.extract(args), 3)
        rows = self.rows(output)
        self.assertEqual([Decimal(r["actual_ms"]) for r in rows],
                         [Decimal(500), Decimal(1000), Decimal(2000)])
        import struct
        image = (output / rows[0]["image"]).read_bytes()
        self.assertEqual(struct.unpack(">II", image[16:24]), (80, 45))

    def test_default_directory_and_count(self):
        args = frame_pick.parser().parse_args([str(self.video), "--count", "1"])
        self.assertEqual(frame_pick.extract(args), 1)
        output = self.video.with_name(self.video.stem + "_frames")
        rows = self.rows(output)
        self.assertEqual(Decimal(rows[0]["actual_ms"]), 0)
        self.assertEqual(rows[0]["source_video"], str(self.video.resolve()))
        before = (output / "frame_000001.jpg").read_bytes()
        with self.assertRaises(ValueError):
            frame_pick.extract(args)
        self.assertEqual(before, (output / "frame_000001.jpg").read_bytes())

    def test_no_frames_is_error(self):
        output = self.root / "empty"
        args = frame_pick.parser().parse_args([str(self.video), str(output), "--start", "10"])
        with self.assertRaises(ValueError):
            frame_pick.extract(args)
        self.assertIn("失敗", (output / "frames.txt").read_text(encoding="utf-8-sig"))

    def test_invalid_interval_does_not_create_output(self):
        output = self.root / "invalid"
        args = frame_pick.parser().parse_args([str(self.video), str(output), "--interval", "0"])
        with self.assertRaises(ValueError):
            frame_pick.extract(args)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
