import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
import numpy as np
import soundfile as sf
from srt_parser import Subtitle, seconds, parse_srt, clean_text
from config import arguments
from model_manager import ModelManager
from audio_timeline import AudioTimeline
from subvoice import reserve_outputs, render, main
from credit_manager import credit_text


class FakeEngine:
    def __init__(self):
        self.speeds = []

    def synthesize(self, text, options):
        self.speeds.append(options.speed)
        if text == "失敗":
            raise RuntimeError("意図した生成失敗")
        return 1000, np.full(round(4000 / options.speed), 0.2, dtype=np.float32)


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "日本語フォルダ"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def srt(self):
        p = self.root / "字幕.srt"
        p.write_text(
            "1\n00:00:03,000 --> 00:00:03,500\n<b>今日は。</b>\n畑です。\n\n2\n00:00:05,000 --> 00:00:06,000\n次です。\n\n3\n00:00:12,000 --> 00:00:13,000\n最後。",
            encoding="utf-8-sig",
        )
        return p

    def test_parser(self):
        items = parse_srt(self.srt())
        self.assertEqual(items[0].start, 3)
        self.assertEqual(items[0].text, "今日は。 畑です。")
        self.assertAlmostEqual(seconds("01:02:03,456"), 3723.456)
        self.assertEqual(clean_text("{\\an8}<i>四角豆。</i>", {"四角豆": "シカクマメ"}), "シカクマメ。")

    def test_invalid(self):
        p = self.root / "bad.srt"
        p.write_text("1\nBAD\n本文", encoding="utf-8")
        with self.assertRaises(ValueError):
            parse_srt(p)

    def test_empty(self):
        p = self.root / "empty.srt"
        p.write_text("1\n00:00:00,000 --> 00:00:01,000\n", encoding="utf-8")
        self.assertEqual(parse_srt(p)[0].text, "")

    def test_timeline(self):
        subs = parse_srt(self.srt())
        engine = FakeEngine()
        timeline = AudioTimeline(self.root, 1000)
        with self.assertLogs(level="WARNING"):
            self.assertEqual(
                render(subs, engine, arguments([str(self.srt())]), timeline), 0
            )
        self.assertEqual(engine.speeds, [1, 1, 1])
        out = self.root / "mix.wav"
        timeline.write(out)
        audio, rate = sf.read(str(out))
        self.assertEqual(rate, 1000)
        self.assertEqual(len(audio), 16000)
        self.assertTrue(np.all(audio[:3000] == 0))
        self.assertTrue(np.all(audio[9000:12000] == 0))
        self.assertAlmostEqual(audio[3000], 0.2, places=4)
        self.assertAlmostEqual(audio[5000], 0.4, places=4)

    def test_failure_continues(self):
        subs = [Subtitle(1, 0, 1, "失敗"), Subtitle(2, 5, 6, "成功")]
        timeline = AudioTimeline(self.root, 1000)
        self.assertEqual(
            render(subs, FakeEngine(), arguments([str(self.srt())]), timeline), 1
        )
        self.assertEqual(timeline.clips[0][0].index, 2)

    def test_no_overwrite(self):
        srt = self.srt()
        first = reserve_outputs(srt, None)
        first[0].write_bytes(b"original")
        second = reserve_outputs(srt, None)
        self.assertEqual(first[0].parent, srt.parent)
        self.assertEqual(second[0].name, "字幕_subvoice_001.wav")
        self.assertEqual(first[0].read_bytes(), b"original")
        self.assertEqual(reserve_outputs(srt, None, True), first)

    def test_config(self):
        p = self.root / "settings.json"
        p.write_text(json.dumps({"speed": 0.9, "output_dir": str(self.root)}))
        a = arguments([str(self.srt()), "--config", str(p), "--speed", "1.1"])
        self.assertEqual(a.speed, 1.1)
        self.assertEqual(a.output_dir, self.root)

    def test_model_and_credit(self):
        (self.root / "voice.safetensors").touch()
        (self.root / "style_vectors.npy").touch()
        (self.root / "config.json").write_text('{"data":{"style2id":{"Neutral":0}}}')
        model = ModelManager(str(self.root), self.root / "none.json")
        self.assertEqual(model.styles(), {"Neutral": 0})
        self.assertIn("License: UNKNOWN", credit_text(model.metadata))

    def test_avoid_is_bounded(self):
        engine = FakeEngine()
        timeline = AudioTimeline(self.root, 1000)
        render(
            [Subtitle(1, 0, 0.1, "長文"), Subtitle(2, 1, 2, "次")],
            engine,
            arguments([str(self.srt()), "--overlap-mode", "avoid"]),
            timeline,
        )
        self.assertEqual(engine.speeds, [1, 1.15, 1])

    def test_cli_outputs(self):
        srt = self.srt()
        (self.root / "voice.safetensors").touch()
        (self.root / "style_vectors.npy").touch()
        (self.root / "config.json").write_text('{"data":{"style2id":{"Neutral":0}}}')
        with patch("tts_engine.StyleBertEngine", return_value=FakeEngine()):
            self.assertEqual(
                main(
                    [
                        str(srt),
                        "--model",
                        str(self.root),
                        "--work-dir",
                        str(self.root / "work"),
                    ]
                ),
                0,
            )
        self.assertTrue((self.root / "字幕_subvoice.wav").is_file())
        self.assertIn(
            "UNKNOWN",
            (self.root / "字幕_subvoice_credit.txt").read_text(encoding="utf-8"),
        )
        self.assertEqual(list((self.root / "work").iterdir()), [])

    def test_resample(self):
        timeline = AudioTimeline(self.root, 2000)
        timeline.add(Subtitle(1, 1, 2, "a"), 1000, np.ones(1000) * 0.1)
        self.assertEqual(timeline.clips[0][1:3], (2000, 2000))

    def test_real_srt(self):
        p = Path(r"E:\backup_kenji\mov\n175\n175.srt")
        if not p.exists():
            self.skipTest("指定実データなし")
        items = parse_srt(p)
        self.assertGreater(len(items), 1)
        self.assertEqual(items[0].start, 0.5)
        engine = FakeEngine()
        timeline = AudioTimeline(self.root, 1000)
        self.assertEqual(render(items, engine, arguments([str(p)]), timeline), 0)
        out = self.root / "n175_TEST_TONE_NOT_SPEECH.wav"
        timeline.write(out)
        self.assertTrue(out.exists())
        self.assertEqual(len(timeline.clips), sum(bool(s.text) for s in items))

    def test_clipping_prevention(self):
        timeline = AudioTimeline(self.root, 1000)
        for i in range(2):
            timeline.add(Subtitle(i, 0, 1, "音声"), 1000, np.ones(1000) * 0.8)
        out = self.root / "peak.wav"
        timeline.write(out)
        audio, _ = sf.read(str(out))
        self.assertGreater(audio.min(), 0.99)
        self.assertLessEqual(audio.max(), 1)

    def test_bad_config(self):
        p = self.root / "bad.json"
        p.write_text('{"speed":0}')
        with self.assertRaises(SystemExit):
            arguments([str(self.srt()), "--config", str(p)])
        p.write_text('{"overlap_mode":"invalid"}')
        with self.assertRaises(SystemExit):
            arguments([str(self.srt()), "--config", str(p)])

    def test_missing_model_cli(self):
        self.assertEqual(
            main([str(self.srt()), "--model", str(self.root / "missing")]), 1
        )
        self.assertFalse((self.root / "字幕_subvoice.wav").exists())
        self.assertTrue((self.root / "字幕_subvoice.log").exists())

    def test_analyze_without_model(self):
        self.assertEqual(main([str(self.srt()), "--analyze-only"]), 0)
        self.assertFalse((self.root / "字幕_subvoice.wav").exists())
        self.assertFalse((self.root / "字幕_subvoice_credit.txt").exists())

    def test_engine_parameter_mapping(self):
        from tts_engine import StyleBertEngine

        engine = StyleBertEngine.__new__(StyleBertEngine)
        engine.language = "JP"
        engine.model = Mock()
        engine.model.infer.return_value = (
            44100,
            np.array([-32768, 0, 16384], dtype=np.int16),
        )
        options = arguments([str(self.srt()), "--speed", "0.8", "--pitch", "1.1"])
        rate, audio = engine.synthesize("日本語", options)
        call = engine.model.infer.call_args.kwargs
        self.assertEqual(call["length"], 1.25)
        self.assertEqual(call["pitch_scale"], 1.1)
        self.assertFalse(call["line_split"])
        self.assertEqual(rate, 44100)
        np.testing.assert_allclose(audio, [-1, 0, 0.5])


    def test_cache_location(self):
        from tts_engine import configure_cache
        with patch.dict(os.environ, {}, clear=True):
            path = configure_cache(self.root / "cache")
            self.assertEqual(os.environ["HF_HUB_CACHE"], str((self.root / "cache").resolve()))
            self.assertTrue(Path(path).is_dir())
            os.environ["HF_HOME"] = "explicit-user-setting"
            configure_cache(path)
            self.assertEqual(os.environ["HF_HOME"], "explicit-user-setting")


if __name__ == "__main__":
    unittest.main()
