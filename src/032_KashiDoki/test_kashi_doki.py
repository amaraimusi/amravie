import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import json
import wave
from pathlib import Path

from kashi_doki import AlignmentError, clean_lyrics, make_cues, timestamp, write_srt, parser, run


class KashiDokiTests(unittest.TestCase):
    def test_annotations_and_mixed_languages(self):
        self.assertEqual(clean_lyrics('[Intro]\n猫 [注記] マフラー\n[複数\n行]\nC’est chic!'),
                         ['猫  マフラー', 'C’est chic!'])
        self.assertEqual(clean_lyrics('あ[外[内]外]い'), ['あい'])
        for text in ('[注記]', '歌[注記', '歌]'):
            with self.assertRaises(ValueError):
                clean_lyrics(text)

    def test_audio_times_not_equal_spacing(self):
        lines = ['猫', 'フランス']
        segments = [dict(text=t, start=s, end=e, words=[dict(start=s, end=e)])
                    for t, s, e in [('猫', 7.12, 8.35), ('フランス', 30.0, 33.1)]]
        cues = make_cues(lines, segments, 60)
        self.assertEqual(cues[0], (7120, 8350, '猫'))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / '猫.srt'
            write_srt(target, cues)
            self.assertIn('00:00:30,000 --> 00:00:33,100', target.read_text(encoding='utf-8-sig'))
            with self.assertRaises(FileExistsError):
                write_srt(target, cues)

    def test_reject_failed_alignment(self):
        good = dict(text='猫', start=1, end=2, words=[dict(start=1, end=2)])
        for segments in ([], [dict(good, text='犬')], [dict(good, end=float('nan'))],
                         [dict(good, words=[])], [dict(good, words=[dict(start=1, end=1)])],
                         [good, dict(good, start=1.5)]):
            with self.assertRaises(AlignmentError):
                make_cues(['猫'] * len(segments) if segments else ['猫'], segments, 60)

    def test_srt_rounding(self):
        self.assertEqual(timestamp(round(3599.9999 * 1000)), '01:00:00,000')

    def test_japanese_instant_subtoken_keeps_detected_line(self):
        segments = [dict(text='ミャ', start=1, end=2,
                         words=[dict(start=1, end=2), dict(start=2, end=2)])]
        self.assertEqual(make_cues(['ミャ'], segments, 5), [(1000, 2000, 'ミャ')])

    def test_pipeline_and_failure_report(self):
        # Model-independent integration check; never substitutes for real audio QA.
        import numpy  # Initialize before replacing subprocess.run.
        segment = dict(text='猫', start=1, end=2, words=[dict(start=1, end=2)])
        model = SimpleNamespace(align=lambda *a, **kw: SimpleNamespace(to_dict=lambda: {'segments': [segment]}))
        modules = {'torch': SimpleNamespace(set_num_threads=lambda n: None),
                   'stable_whisper': SimpleNamespace(load_model=lambda *a, **kw: model)}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '曲.mp3').write_bytes(b'test')
            (root / '歌詞.txt').write_text('[Intro]\n猫', encoding='utf-8')
            args = parser().parse_args([str(root / '曲.mp3'), str(root / '歌詞.txt')])
            def convert(command, **kwargs):
                with wave.open(command[-1], 'wb') as stream:
                    stream.setnchannels(1)
                    stream.setsampwidth(2)
                    stream.setframerate(16000)
                    stream.writeframes(b'\0\0' * 48000)
                return SimpleNamespace(returncode=0)
            with patch.dict('sys.modules', modules), patch('kashi_doki.shutil.which', return_value='ffmpeg'), \
                    patch('kashi_doki.subprocess.run', side_effect=convert):
                run(args)
                self.assertTrue((root / 'kasiDoki/曲.srt').is_file())
                segment['end'] = 0
                with self.assertRaises(AlignmentError):
                    run(args)
            reports = [json.loads(p.read_text(encoding='utf-8'))
                       for p in (root / 'kasiDoki/data').glob('*/report.json')]
            self.assertEqual(sorted(r['status'] for r in reports), ['failed', 'success'])
            self.assertEqual(len(list((root / 'kasiDoki').glob('*.srt'))), 1)


if __name__ == '__main__':
    unittest.main()
