import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def arguments(argv=None):
    p = argparse.ArgumentParser(description="SubVoice 字幕読み上げツール: 開始時刻固定・自然な朗読")
    p.add_argument("srt", type=Path, nargs="?")
    p.add_argument(
        "--config",
        type=Path,
        default=(ROOT / "subvoice_config.json")
        if (ROOT / "subvoice_config.json").is_file()
        else None,
    )
    p.add_argument("--model")
    p.add_argument("--profiles", type=Path, default=ROOT / "model_profiles.json")
    p.add_argument("--output-dir", type=Path)
    p.add_argument("--work-dir", type=Path, default=ROOT / "work")
    p.add_argument("--dictionary", type=Path)
    p.add_argument("--encoding", default="utf-8-sig")
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--bert-model", help="日本語BERTのローカルパスまたはHF ID")
    p.add_argument("--style", default="Neutral")
    p.add_argument("--speaker-id", type=int, default=0)
    for name, value in [
        ("speed", 1.0),
        ("style-weight", 1.0),
        ("pitch", 1.0),
        ("intonation", 1.0),
        ("sdp-ratio", 0.2),
        ("noise", 0.6),
        ("noise-w", 0.8),
        ("max-speedup", 1.15),
    ]:
        p.add_argument("--" + name, type=float, default=value)
    p.add_argument("--overlap-mode", choices=["allow", "warn", "avoid"], default="warn")
    for name in ["overwrite", "keep-work", "list-styles", "analyze-only"]:
        p.add_argument("--" + name, action="store_true")
    preliminary, _ = p.parse_known_args(argv)
    if preliminary.config:
        data = json.loads(preliminary.config.read_text(encoding="utf-8-sig"))
        actions = {a.dest: a for a in p._actions}
        for key, value in data.items():
            if key not in actions or key in ("help", "config", "srt"):
                p.error("未知または使用できない設定: " + key)
            action = actions[key]
            if action.type:
                value = action.type(value)
            elif isinstance(action, argparse._StoreTrueAction) and not isinstance(
                value, bool
            ):
                p.error(key + " は真偽値が必要")
            if action.choices and value not in action.choices:
                p.error("不正な設定: " + key)
            p.set_defaults(**{key: value})
    a = p.parse_args(argv)
    if not a.list_styles and a.srt is None:
        p.error("SRTファイルを指定してください")
    for key in [
        "speed",
        "pitch",
        "intonation",
        "style_weight",
        "sdp_ratio",
        "noise",
        "noise_w",
        "max_speedup",
    ]:
        value = getattr(a, key)
        if not math.isfinite(value) or value < 0:
            p.error(key + " は有限の非負値が必要")
    if (
        min(a.speed, a.pitch, a.intonation) <= 0
        or not 1 <= a.max_speedup <= 1.25
        or not 0 <= a.sdp_ratio <= 1
    ):
        p.error("speed/pitch/intonation > 0、max-speedup 1～1.25、sdp-ratio 0～1 が必要")
    return a
