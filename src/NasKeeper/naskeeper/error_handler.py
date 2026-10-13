import errno
import threading
from .state_manager import read_json


class OfflineError(OSError):
    pass


class ConnectionGate:
    """共有ロック内で接続復旧を待ち、全workerの失敗連鎖を防ぐ。"""
    def __init__(self, destination, stop, wait, attempts, logger):
        self.destination, self.stop = destination, stop
        self.wait, self.attempts, self.logger = wait, attempts, logger
        self.lock = threading.Lock()
        self.exhausted = False

    def check(self):
        with self.lock:
            if self.exhausted:
                raise OfflineError("保存先への再接続回数を超えました")
            for attempt in range(self.attempts + 1):
                if self.stop.is_set():
                    raise InterruptedError("中断されました")
                try:
                    # exists()はアクセスエラーを隠すためstatを使う。
                    self.destination.stat()
                    (self.destination / ".naskeeper").stat()
                    return
                except OSError as exc:
                    if attempt == self.attempts:
                        self.exhausted = True
                        self.stop.set()
                        raise OfflineError("保存先に接続できません: " + str(exc))
                    self.logger.warning("保存先の復旧待機 %d/%d: %s", attempt + 1, self.attempts, exc)
                    if self.stop.wait(self.wait):
                        raise InterruptedError("中断されました")


def transient(exc):
    return isinstance(exc, OSError) and (exc.errno in
        (errno.EAGAIN, errno.EBUSY, errno.EIO, errno.ETIMEDOUT, errno.ECONNRESET,
         errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ECONNABORTED) or
        getattr(exc, "winerror", None) in (32, 33, 53, 64, 121, 1231, 1232))
