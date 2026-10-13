import os
from .verification import fingerprint


def verified_prefix(source, partial, fp, buffer_size, stop):
    """境界だけでなく部分ファイル全体を照合し、最初の不一致から再送する。"""
    limit = min(partial.stat().st_size, fp["size"])
    offset = 0
    with source.open("rb") as src, partial.open("rb") as dst:
        while offset < limit:
            if stop.is_set():
                raise InterruptedError("中断されました")
            amount = min(buffer_size, limit - offset)
            if src.read(amount) != dst.read(amount):
                break
            offset += amount
    if fingerprint(source) != fp:
        raise OSError("コピー元が再開検証中に変更されました")
    return offset
