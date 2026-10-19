import gc
import io
from pathlib import Path
import unittest
import weakref
from unittest.mock import patch
from PIL import Image, ImageDraw
from engine import load_image
from photo_store import PhotoRecord, PhotoCache


class PhotoStoreTests(unittest.TestCase):
    def fixture(self, size=(2400, 1600)):
        image = Image.new('RGB', size, '#ca9b61')
        ImageDraw.Draw(image).rectangle((120, 300, 900, 1000), fill='#286f91')
        output = io.BytesIO()
        image.save(output, 'JPEG', quality=94)
        return output.getvalue()

    def test_original_is_byte_exact_proxy_is_bounded_and_cleanup_is_automatic(self):
        data = self.fixture()
        record = PhotoRecord(data)
        path = Path(record.directory.name)
        self.assertEqual(record.original.read_bytes(), data)
        self.assertEqual((record.width, record.height), (2400, 1600))
        with Image.open(record.proxy) as proxy:
            self.assertEqual(proxy.size, (1800, 1200))
        cache = PhotoCache()
        self.assertEqual(cache.get(record, full=True).tobytes(), load_image(data).tobytes())
        del record
        gc.collect()
        self.assertFalse(path.exists(), 'Cache must not retain original files after record removal')

    def test_cache_evicts_before_growth_and_keeps_selected_original_separate(self):
        cache = PhotoCache(budget=64 * 1024**2)
        records = [PhotoRecord(self.fixture()) for _ in range(5)]
        selected = cache.get(records[0], full=True)
        for record in records:
            cache.get(record)
            self.assertLessEqual(cache.used, cache.budget)
        self.assertIs(cache.get(records[0], full=True), selected)
        cache.discard(records[0])
        self.assertFalse(any(key[0] == records[0].directory.name for key in cache.entries))
        cache.clear()
        self.assertEqual(cache.used, 0)

    def test_oversize_original_is_processed_without_entering_cache(self):
        cache = PhotoCache(budget=1024**2)
        record = PhotoRecord(self.fixture())
        image = cache.get(record, full=True)
        self.assertEqual(image.size, (2400, 1600))
        self.assertEqual(cache.used, 0)

    def test_previous_original_is_released_before_next_decode(self):
        cache = PhotoCache(budget=32 * 1024**2)
        records = [PhotoRecord(self.fixture()) for _ in range(2)]
        image = cache.get(records[0], full=True)
        previous = weakref.ref(image)
        del image
        def decode(data):
            self.assertIsNone(previous(), 'Eviction must release RGB pixels before the next decode starts')
            return load_image(data)
        with patch('photo_store.load_image', side_effect=decode):
            cache.get(records[1], full=True)
