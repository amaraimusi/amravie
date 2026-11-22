import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import renban_furi as app


class RenbanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, content=None):
        (self.root / name).write_bytes((content or name).encode())

    def test_example_content_and_subdirectory(self):
        for name in ['20261117.mp4', '20261114.mp4', '20261116.mp4']:
            self.write(name)
        (self.root / 'sub').mkdir()
        (self.root / 'sub' / 'child').touch()
        self.assertEqual(app.apply_plan(app.make_plan(self.root, 400, 3)), 3)
        self.assertEqual((self.root / '403_20261116.mp4').read_bytes(), b'20261116.mp4')
        self.assertTrue((self.root / 'sub' / 'child').exists())
        self.assertEqual(len(list(self.root.iterdir())), 4)

    def test_replacement_crossing_and_four_digits(self):
        self.write('997_a.mp4', 'first')
        self.write('998_a.mp4', 'second')
        app.apply_plan(app.make_plan(self.root, 998, 2))
        self.assertEqual((self.root / '998_a.mp4').read_bytes(), b'first')
        self.assertEqual((self.root / '1000_a.mp4').read_bytes(), b'second')

    def test_dry_run_and_short_prefix(self):
        self.write('02_scene.png')
        self.assertEqual(app.main([str(self.root), '0', '1', '--dry-run']), 0)
        self.assertEqual([p.name for p in self.root.iterdir()], ['02_scene.png'])
        self.assertEqual(app.make_plan(self.root, 0, 1)[0][1].name, '000_02_scene.png')

    def test_collision_with_directory(self):
        self.write('scene.mp4')
        (self.root / '400_scene.mp4').mkdir()
        with self.assertRaises(ValueError):
            app.make_plan(self.root, 400, 3)
        self.assertTrue((self.root / 'scene.mp4').is_file())

    def test_invalid_and_empty(self):
        self.assertEqual(app.make_plan(self.root, 0, 1), [])
        for start, step in [(-1, 1), (0, 0), (0, -1)]:
            with self.assertRaises(ValueError):
                app.make_plan(self.root, start, step)
        with self.assertRaises(OSError):
            app.make_plan(self.root / 'missing', 0, 1)

    def test_failure_rolls_back_both_phases(self):
        self.write('001_a', 'A')
        self.write('002_a', 'B')
        original_move = app.move_file
        for fail_at in [2, 4]:
            calls = [0]

            def failing_move(src, dst):
                calls[0] += 1
                if calls[0] == fail_at:
                    raise PermissionError('simulated')
                original_move(src, dst)

            with patch.object(app, 'move_file', side_effect=failing_move):
                with self.assertRaisesRegex(RuntimeError, '復旧しました'):
                    app.apply_plan(app.make_plan(self.root, 2, 1))
            self.assertEqual((self.root / '001_a').read_bytes(), b'A')
            self.assertEqual((self.root / '002_a').read_bytes(), b'B')
            self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_failed_rollback_keeps_journal(self):
        self.write('a')
        original_move = app.move_file
        calls = [0]

        def failing_move(src, dst):
            calls[0] += 1
            if calls[0] >= 2:
                raise PermissionError('simulated')
            original_move(src, dst)

        with patch.object(app, 'move_file', side_effect=failing_move):
            with self.assertRaisesRegex(RuntimeError, '対応表'):
                app.apply_plan(app.make_plan(self.root, 1, 1))
        staging = next(self.root.glob('.renbanfuri-*'))
        self.assertTrue((staging / 'recovery.json').is_file())
        self.assertEqual((staging / '0').read_bytes(), b'a')

    def test_no_change(self):
        self.write('001_a')
        self.assertEqual(app.apply_plan(app.make_plan(self.root, 1, 1)), 0)


if __name__ == '__main__':
    unittest.main()
