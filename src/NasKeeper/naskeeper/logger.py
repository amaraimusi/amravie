import logging
import time
import threading


def make_logger(path):
    logger = logging.getLogger("naskeeper")
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    handler = logging.FileHandler(str(path), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(console)
    return logger


class Progress:
    def __init__(self, total, total_bytes, quiet=False):
        self.total, self.total_bytes, self.quiet = total, total_bytes, quiet
        self.done = self.errors = self.bytes = self.credited = 0
        self.start = time.monotonic()
        self.last = self.start
        self.last_bytes = 0
        self.lock = threading.Lock()

    def credit(self, amount):
        with self.lock:
            self.credited += amount

    def update(self, name, offset, size, sent=0, finished=False, failed=False):
        with self.lock:
            self.bytes += sent
            self.done += int(finished)
            self.errors += int(failed)
            now = time.monotonic()
            if self.quiet or now - self.last < 1:
                return
            elapsed = now - self.start
            rate = (self.bytes - self.last_bytes) / (now - self.last)
            average = self.bytes / max(elapsed, .001)
            eta = max(0, self.total_bytes - self.bytes - self.credited) / average if average else 0
            print("[%d/%d] %s %.1f%% | %.1f MiB/s | 経過 %.0fs | 残り目安 %.0fs | エラー %d" %
                  (self.done, self.total, name, 100 if finished else 100 * offset / max(size, 1), rate / 1048576, elapsed, eta, self.errors), flush=True)
            self.last, self.last_bytes = now, self.bytes
