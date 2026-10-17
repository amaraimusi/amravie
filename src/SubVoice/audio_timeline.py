"""Disk backed mixing; subtitle end times never determine speech speed."""
import logging
from pathlib import Path
import numpy as np
import soundfile as sf


class AudioTimeline:
    def __init__(self, work, rate=44100):
        self.work, self.rate, self.clips = Path(work), rate, []

    def add(self, subtitle, rate, audio):
        audio = np.asarray(audio, dtype=np.float32)
        if (
            rate <= 0
            or audio.ndim != 1
            or not len(audio)
            or not np.isfinite(audio).all()
        ):
            raise ValueError("不正な音声データ")
        if rate != self.rate:
            from scipy.signal import resample_poly
            from math import gcd

            g = gcd(rate, self.rate)
            audio = resample_poly(audio, self.rate // g, rate // g).astype(np.float32)
        start = round(subtitle.start * self.rate)
        for old, pos, count, _ in self.clips:
            overlap = min(pos + count, start + len(audio)) - max(pos, start)
            if overlap > 0:
                logging.warning(
                    "字幕 #%s と字幕 #%s の音声が %.3f 秒重複",
                    old.index,
                    subtitle.index,
                    overlap / self.rate,
                )
        path = self.work / ("%06d.wav" % len(self.clips))
        sf.write(str(path), audio, self.rate, subtype="FLOAT")
        self.clips.append((subtitle, start, len(audio), path))

    def write(self, path):
        size = max((start + count for _, start, count, _ in self.clips), default=1)
        mix = np.memmap(
            str(self.work / "timeline.f32"), mode="w+", dtype="float32", shape=(size,)
        )
        mix[:] = 0
        try:
            for _, start, count, clip in self.clips:
                audio, _ = sf.read(str(clip), dtype="float32")
                mix[start : start + count] += audio
            peak = max(
                float(np.max(np.abs(mix[i : i + 65536]))) for i in range(0, size, 65536)
            )
            gain = 1 / max(1, peak)
            if peak > 1:
                logging.warning("クリッピング防止: 全体ゲイン %.4f", gain)
            with sf.SoundFile(
                str(path),
                mode="w",
                samplerate=self.rate,
                channels=1,
                subtype="PCM_16",
                format="WAV",
            ) as out:
                for i in range(0, size, 65536):
                    out.write(mix[i : i + 65536] * gain)
        finally:
            mix.flush()
            del mix
