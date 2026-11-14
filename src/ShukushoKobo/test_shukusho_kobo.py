import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from shukusho_kobo import main


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / '画像'
        self.source.mkdir()

    def run_cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return main([str(self.source), *map(str, args)])

    def make(self, name='sample.png', size=(800, 400)):
        path = self.source / name
        Image.new('RGBA', size, (20, 40, 60, 100)).save(path)
        return path

    def test_default_transparency_ratio_original_and_skip(self):
        original = self.make()
        before = original.read_bytes()
        self.assertEqual(self.run_cli(), 0)
        output = self.source.with_name('画像_resized') / original.name
        with Image.open(output) as image:
            self.assertEqual(image.size, (400, 200))
            self.assertEqual(image.getpixel((0, 0))[3], 100)
        saved = output.read_bytes()
        self.assertEqual(self.run_cli('--width', 10), 0)
        self.assertEqual(output.read_bytes(), saved)
        self.assertEqual(original.read_bytes(), before)

    def test_errors_continue_and_no_upscale(self):
        self.make(size=(20, 10))
        (self.source / 'broken.png').write_bytes(b'broken')
        output = Path(self.temp.name) / 'out'
        self.assertEqual(self.run_cli(output, '--workers', 2), 1)
        with Image.open(output / 'sample.png') as image:
            self.assertEqual(image.size, (20, 10))

    def test_jpeg_white_background_and_name_collision(self):
        self.make()
        Image.new('RGB', (80, 40)).save(self.source / 'sample.jpg')
        output = Path(self.temp.name) / 'jpeg'
        self.assertEqual(self.run_cli(output, '--format', 'jpeg'), 1)
        with Image.open(output / 'sample.jpg') as image:
            self.assertEqual(image.format, 'JPEG')

    def test_webp_and_exif_orientation(self):
        image = Image.new('RGB', (80, 40))
        exif = image.getexif()
        exif[274] = 6
        image.save(self.source / 'rotated.jpg', exif=exif)
        output = Path(self.temp.name) / 'webp'
        self.assertEqual(self.run_cli(output, '--format', 'webp'), 0)
        with Image.open(output / 'rotated.webp') as result:
            self.assertEqual(result.size, (40, 80))

    def test_reject_invalid_arguments(self):
        for args in [(self.source,), ('--width', 0), ('--quality', 101)]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.run_cli(*args)

    def test_150_images(self):
        for number in range(150):
            self.make('image{:03}.png'.format(number), (32, 16))
        output = Path(self.temp.name) / 'batch'
        self.assertEqual(self.run_cli(output, '--width', 16, '--height', 16), 0)
        self.assertEqual(len(list(output.glob('*.png'))), 150)
        for path in output.glob('*.png'):
            with Image.open(path) as image:
                self.assertEqual(image.size, (16, 8))

    def test_single_dimension_and_bounding_box(self):
        self.make('portrait.png', (800, 1600))
        self.make('landscape.png', (1600, 800))
        self.make('small.png', (20, 10))
        cases = [
            (['--width', 600], (600, 1200), (600, 300)),
            (['--height', 600], (300, 600), (1200, 600)),
            (['--width', 600, '--height', 400], (200, 400), (600, 300)),
            ([], (200, 400), (400, 200)),
        ]
        for index, (args, portrait, landscape) in enumerate(cases):
            with self.subTest(args=args):
                output = Path(self.temp.name) / str(index)
                self.assertEqual(self.run_cli(output, *args), 0)
                for name, expected in [('portrait.png', portrait), ('landscape.png', landscape), ('small.png', (20, 10))]:
                    with Image.open(output / name) as image:
                        self.assertEqual(image.size, expected)


if __name__ == '__main__':
    unittest.main()
