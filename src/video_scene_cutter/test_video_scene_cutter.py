import unittest

from video_scene_cutter import (
    milliseconds_to_ffmpeg_time,
    timestamp_to_milliseconds,
)


class TimestampTest(unittest.TestCase):
    def test_example_start_timestamp(self):
        self.assertEqual(timestamp_to_milliseconds("00:03:41,338"), 221338)

    def test_example_end_timestamp(self):
        self.assertEqual(timestamp_to_milliseconds("00:03:47,300"), 227300)

    def test_dot_separator_is_accepted(self):
        self.assertEqual(timestamp_to_milliseconds("01:02:03.004"), 3723004)

    def test_invalid_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            timestamp_to_milliseconds("00:61:00,000")

    def test_ffmpeg_time_has_millisecond_precision(self):
        self.assertEqual(milliseconds_to_ffmpeg_time(5962), "5.962")


if __name__ == "__main__":
    unittest.main()
