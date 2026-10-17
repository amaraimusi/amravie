import re
import html
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Subtitle:
    index: int
    start: float
    end: float
    text: str


def seconds(text):
    m = re.fullmatch(r"(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})", text)
    if not m:
        raise ValueError("不正な時刻: " + text)
    h, m, s, ms = map(int, m.groups())
    return h * 3600 + m * 60 + s + ms / 1000


def clean_text(text, dictionary=None):
    text = " ".join(html.unescape(re.sub(r"<[^>]*>|\{\\[^}]*\}", "", text)).split())
    if dictionary:
        pattern = "|".join(
            re.escape(k) for k in sorted(dictionary, key=len, reverse=True)
        )
        text = re.sub(pattern, lambda m: dictionary[m.group()], text)
    return text


def parse_srt(path, encoding="utf-8-sig", dictionary=None):
    raw = (
        Path(path)
        .read_text(encoding=encoding)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    result = []
    for block in re.split(r"\n[ \t]*\n", raw.strip()):
        if not block.strip():
            continue
        lines = block.strip().split("\n")
        try:
            index = int(lines[0])
            m = re.fullmatch(r"(\S+)\s+-->\s+(\S+)(?:\s+.*)?", lines[1])
            if not m:
                raise ValueError("不正な時刻行")
            start, end = map(seconds, m.groups())
            if end < start:
                raise ValueError("終了が開始より前")
            result.append(
                Subtitle(
                    index, start, end, clean_text("\n".join(lines[2:]), dictionary)
                )
            )
        except (ValueError, IndexError) as exc:
            raise ValueError("SRT解析エラー: " + block[:100]) from exc
    if not result:
        raise ValueError("字幕がありません")
    return sorted(result, key=lambda s: s.start)
