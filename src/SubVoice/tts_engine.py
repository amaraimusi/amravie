"""Style-Bert-VITS2 adapter; other engines implement synthesize(text, options)."""
import os
from pathlib import Path
from typing import Protocol
import numpy as np


def configure_cache(cache_dir=None):
    """Set defaults before Transformers/Hugging Face imports initialize caches."""
    cache = Path(cache_dir or Path(__file__).resolve().parent / "work" / "bert-cache").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache.parent / "huggingface"))
    os.environ.setdefault("HF_HUB_CACHE", str(cache))
    dictionary = cache.parent / "open_jtalk_dic_utf_8-1.11"
    if dictionary.is_dir():
        os.environ.setdefault("OPEN_JTALK_DICT_DIR", str(dictionary))
    return str(cache)


class Engine(Protocol):
    def synthesize(self, text, options):
        """Return sample rate and mono float audio in [-1,1]."""
        ...


class StyleBertEngine:
    def __init__(self, model, device="cpu", bert_model=None, cache_dir=None):
        cache_dir = configure_cache(cache_dir)
        from style_bert_vits2.constants import Languages
        from style_bert_vits2.nlp import bert_models
        from style_bert_vits2.tts_model import TTSModel

        self.language = Languages.JP
        source = bert_model or "ku-nlp/deberta-v2-large-japanese-char-wwm"
        bert_models.load_model(self.language, source, cache_dir=cache_dir)
        bert_models.load_tokenizer(self.language, source, cache_dir=cache_dir)
        self.model = TTSModel(model.weights, model.config, model.vectors, device)
        self.model.load()

    def synthesize(self, text, options):
        rate, audio = self.model.infer(
            text=text,
            language=self.language,
            speaker_id=options.speaker_id,
            style=options.style,
            style_weight=options.style_weight,
            length=1 / options.speed,
            sdp_ratio=options.sdp_ratio,
            noise=options.noise,
            noise_w=options.noise_w,
            pitch_scale=options.pitch,
            intonation_scale=options.intonation,
            line_split=False,
        )
        audio = np.asarray(audio)
        if np.issubdtype(audio.dtype, np.integer):
            audio = audio.astype(np.float32) / max(
                abs(np.iinfo(audio.dtype).min), np.iinfo(audio.dtype).max
            )
        return rate, audio.astype(np.float32)
