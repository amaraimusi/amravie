import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw
from PngToumeiTool import main, remove_background, tolerance_value


class BackgroundTests(unittest.TestCase):
    def test_enclosed_color_and_edges(self):
        im = Image.new('RGB', (9, 9), 'white')
        ImageDraw.Draw(im).rectangle((2, 2, 6, 6), outline='black')
        out = remove_background(im)
        self.assertEqual(out.getpixel((0, 0))[3], 0)
        self.assertEqual(out.getpixel((4, 4))[3], 255)
        self.assertEqual(out.getpixel((2, 2)), (0, 0, 0, 255))
        self.assertEqual(im.mode, 'RGB')

    def test_tolerance(self):
        im = Image.new('RGB', (5, 5), (230, 230, 230))
        for xy in [(0, 0), (4, 0), (0, 4), (4, 4)]:
            im.putpixel(xy, (255, 255, 255))
        self.assertEqual(remove_background(im, 0).getpixel((1, 0))[3], 255)
        self.assertEqual(remove_background(im, .1).getpixel((1, 0))[3], 0)
        self.assertEqual(remove_background(im, 1).getbbox(), None)

    def test_different_corners(self):
        im = Image.new('RGB', (8, 8), 'white')
        ImageDraw.Draw(im).rectangle((4, 0, 7, 7), fill=(220, 225, 230))
        self.assertIsNone(remove_background(im, .01).getbbox())

    def test_transparency(self):
        im = Image.new('RGBA', (5, 5), (255, 255, 255, 255))
        im.putpixel((0, 0), (12, 34, 56, 0))
        im.putpixel((2, 2), (0, 0, 0, 99))
        out = remove_background(im)
        self.assertEqual(out.getpixel((0, 0)), (12, 34, 56, 0))
        self.assertEqual(out.getpixel((2, 2)), (0, 0, 0, 99))
        self.assertEqual(out.getpixel((1, 1))[3], 0)
        for xy in [(0, 0), (4, 0), (0, 4), (4, 4)]:
            im.putpixel(xy, (0, 0, 0, 0))
        self.assertEqual(remove_background(im).getpixel((1, 1))[3], 255)

    def test_small_palette(self):
        for size in [(1, 1), (1, 5), (5, 1)]:
            self.assertIsNone(remove_background(Image.new('P', size)).getbbox())

    def test_cli_batch_and_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / '日本語.PNG'
            Image.new('RGB', (3, 3), 'white').save(image)
            original = image.read_bytes()
            (root / 'bad.png').write_bytes(b'bad')
            (root / 'sub').mkdir()
            Image.new('RGB', (1, 1)).save(root / 'sub' / 'nested.png')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(root)]), 1)
                self.assertEqual(main([str(image), '-o', str(root)]), 1)
                self.assertEqual(main([str(image), '-o', str(root / 'out')]), 0)
            self.assertEqual(image.read_bytes(), original)
            self.assertTrue((root / '日本語_transparent.png').exists())
            self.assertTrue((root / 'out' / image.name).exists())
            self.assertFalse((root / 'sub' / 'nested_transparent.png').exists())
            with Image.open(root / '日本語_transparent.png') as out:
                self.assertEqual(out.mode, 'RGBA')

    def test_invalid_tolerance(self):
        for value in [-.1, 1.1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                remove_background(Image.new('RGB', (1, 1)), value)


if __name__ == '__main__':
    unittest.main()
