import tempfile
import unittest
from pathlib import Path
from PIL import Image
from card_sheet import create_sheet

class CardSheetTests(unittest.TestCase):
    def test_geometry_order_blanks_and_excess(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cards = []
            for i, color in enumerate(['red', 'green', 'blue', 'yellow']):
                p = root / ('card%d.png' % i)
                Image.new('RGB', (630, 900), color).save(p)
                cards.append(p)
            output, size, used, ignored, grid = create_sheet(cards + [root/'missing.png'])
            self.assertEqual((size, used, ignored, grid), ((1270, 1780), 4, 1, (2, 2)))
            with Image.open(output) as im:
                self.assertEqual([im.getpixel(p) for p in [(100,100),(700,100),(100,1000),(700,1000)]],
                                 [(255,0,0),(0,128,0),(0,0,255),(255,255,0)])
                self.assertAlmostEqual(im.info['dpi'][0], 254, places=1)
            blank = root/'three.jpg'
            create_sheet(cards[:3], blank, image_format='jpeg')
            with Image.open(blank) as im:
                self.assertEqual(im.format, 'JPEG')
                self.assertEqual(im.getpixel((700,1000)), (255,255,255))
            with self.assertRaises(FileExistsError):
                create_sheet(cards)
            with self.assertRaises(ValueError):
                create_sheet(cards, cards[0])
            with self.assertRaises(ValueError):
                create_sheet(cards, root/'small.png', sheet_size=(10,10))

if __name__ == '__main__':
    unittest.main()
