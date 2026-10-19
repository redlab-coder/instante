"""Local temporary originals and a bounded decoded-image cache.

Records own their temporary directories. Holding a record during export keeps
its files alive even when another tab removes it from the photo list.
"""
from collections import OrderedDict
import shutil
import tempfile
import threading
import weakref
from pathlib import Path

from PIL import Image
from engine import load_image, content_bounds, CONTENT_BOX


class PhotoRecord:
    def __init__(self, data):
        self.directory = tempfile.TemporaryDirectory(prefix='Instante-foto-')
        self._cleanup = weakref.finalize(self, self.directory.cleanup)
        self.original = Path(self.directory.name) / 'original'
        self.proxy = Path(self.directory.name) / 'editor.png'
        self.live = Path(self.directory.name) / 'editor.jpg'
        self.bytes = len(data)
        try:
            if shutil.disk_usage(self.directory.name).free < len(data) + 64 * 1024**2:
                raise ValueError('Pouco espaço temporário disponível no computador. Libere espaço e tente novamente.')
            # Save the exact uploaded bytes; output always reads these originals.
            self.original.write_bytes(data)
            image = load_image(data)
            self.width, self.height = image.size
            try:
                self.content_box = content_bounds(image)
                image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
                image.save(self.proxy, 'PNG', compress_level=1)
                image.save(self.live, 'JPEG', quality=95, subsampling=0)
            finally:
                image.close()
        except Exception:
            self._cleanup()
            raise


class PhotoCache:
    def __init__(self, budget=160 * 1024**2):
        self.budget = budget
        self.entries = OrderedDict()
        self.used = 0
        # Serializes full-size decoding/rendering, not the interactive browser.
        self.lock = threading.RLock()

    def get(self, record, full=False):
        key = (record.directory.name, full)
        with self.lock:
            if key in self.entries:
                self.entries.move_to_end(key)
                return self.entries[key][0]
            width, height = (record.width, record.height) if full else self.proxy_size(record)
            cost = width * height * 4  # Pillow RGB storage is approximately 4 B/pixel.
            # Evict before decoding so old originals don't overlap the new one.
            limit = self.budget * (0.8 if full else 0.2)
            pool_used = sum(size for (_, kind), (_, size) in self.entries.items() if kind == full)
            while pool_used + cost > limit:
                victim = next((key for key in self.entries if key[1] == full), None)
                if victim is None:
                    break
                previous_cost = self.entries[victim][1]
                del self.entries[victim]
                self.used -= previous_cost
                pool_used -= previous_cost
            if full:
                image = load_image(record.original.read_bytes())
            else:
                with Image.open(record.proxy) as source:
                    image = source.convert('RGB')
            image.info[CONTENT_BOX] = record.content_box
            if cost <= limit:
                self.entries[key] = (image, cost)
                self.used += cost
            return image

    @staticmethod
    def proxy_size(record):
        with Image.open(record.proxy) as image:
            return image.size

    def discard(self, record):
        with self.lock:
            for full in (False, True):
                cached = self.entries.pop((record.directory.name, full), None)
                if cached:
                    self.used -= cached[1]

    def clear(self):
        with self.lock:
            self.entries.clear()
            self.used = 0
