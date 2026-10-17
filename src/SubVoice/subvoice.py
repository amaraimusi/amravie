import json
import os
import logging
import shutil
import tempfile
from pathlib import Path
from copy import copy
from config import arguments
from srt_parser import parse_srt
from model_manager import ModelManager
from credit_manager import credit_text


def reserve_outputs(srt, folder, overwrite=False):
    folder = Path(folder or srt.parent)
    folder.mkdir(parents=True, exist_ok=True)
    for number in range(100000):
        name = srt.stem + "_subvoice" + ("" if number == 0 else "_%03d" % number)
        paths = [folder / (name + s) for s in (".wav", "_credit.txt", ".log")]
        if overwrite:
            return paths
        if any(p.exists() for p in paths):
            continue
        created = []
        try:
            for path in paths:
                with path.open("x"):
                    pass
                created.append(path)
            return paths
        except FileExistsError:
            for path in created:
                path.unlink()
    raise RuntimeError("出力名を確保できません")


def render(subtitles, engine, options, timeline):
    failed = 0
    for i, sub in enumerate(subtitles):
        if not sub.text:
            continue
        logging.info("[%s/%s] 字幕 #%s 生成中...", i + 1, len(subtitles), sub.index)
        try:
            rate, audio = engine.synthesize(sub.text, options)
            if options.overlap_mode == "avoid" and i + 1 < len(subtitles):
                available = subtitles[i + 1].start - sub.start
                if available > 0 and len(audio) / rate > available:
                    adjusted = copy(options)
                    adjusted.speed *= min(
                        options.max_speedup, len(audio) / rate / available
                    )
                    try:
                        rate, audio = engine.synthesize(sub.text, adjusted)
                    except Exception:
                        logging.exception("加速再生成に失敗: 元の自然速度音声を使用します")
            timeline.add(sub, rate, audio)
        except Exception:
            failed += 1
            logging.exception("字幕 #%s 読み上げ失敗: スキップ", sub.index)
    return failed


def main(argv=None):
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s", force=True
    )
    work = None
    outputs = None
    handler = None
    staging = None
    try:
        a = arguments(argv)
        if a.list_styles:
            model = ModelManager(a.model, a.profiles)
            print(json.dumps(model.styles(), ensure_ascii=False, indent=2))
            return 0
        outputs = reserve_outputs(a.srt, a.output_dir, a.overwrite)
        wav, credit, log = outputs
        handler = logging.FileHandler(log, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(handler)
        dictionary = (
            json.loads(a.dictionary.read_text(encoding="utf-8-sig"))
            if a.dictionary
            else {}
        )
        if not isinstance(dictionary, dict) or any(
            not k or not isinstance(v, str) for k, v in dictionary.items()
        ):
            raise ValueError("辞書は空でない単語:読み文字列のJSONオブジェクトです")
        subtitles = parse_srt(a.srt, a.encoding, dictionary)
        logging.info(
            "SRT解析: %s件 / 開始 %.3f秒 / 最終開始 %.3f秒",
            len(subtitles),
            subtitles[0].start,
            subtitles[-1].start,
        )
        if a.analyze_only:
            logging.info("解析のみ完了。音声は生成していません")
            return 0
        model = ModelManager(a.model, a.profiles)
        if a.style not in model.styles():
            raise ValueError("スタイルがありません: " + a.style)
        from tts_engine import StyleBertEngine
        from audio_timeline import AudioTimeline

        engine = StyleBertEngine(
            model, a.device, a.bert_model, str(a.work_dir / "bert-cache")
        )
        a.work_dir.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="run-", dir=str(a.work_dir)))
        timeline = AudioTimeline(work)
        failed = render(subtitles, engine, a, timeline)
        if not timeline.clips:
            raise RuntimeError("生成できた音声がありません")
        temporary = work / "final.wav"
        timeline.write(temporary)
        credit.write_text(credit_text(model.metadata), encoding="utf-8")
        with tempfile.NamedTemporaryFile(
            prefix=".subvoice-", suffix=".wav", dir=str(wav.parent), delete=False
        ) as stream:
            staging = Path(stream.name)
        shutil.copyfile(str(temporary), str(staging))
        os.replace(str(staging), str(wav))
        staging = None
        logging.info("完了: %s / 成功 %s件 / 失敗 %s件", wav, len(timeline.clips), failed)
        return 2 if failed else 0
    except Exception:
        logging.exception("処理を続行できません")
        return 1
    finally:
        if staging and staging.exists():
            staging.unlink()
        if work and not a.keep_work:
            try:
                resolved = work.resolve()
                if resolved.parent != a.work_dir.resolve() or not resolved.name.startswith("run-"):
                    raise ValueError("作業ディレクトリの範囲が不正です")
                shutil.rmtree(str(resolved))
            except (OSError, ValueError):
                logging.exception("一時ファイルを削除できません。workを確認してください")
        if outputs and outputs[0].exists() and outputs[0].stat().st_size == 0:
            outputs[0].unlink()
            if outputs[1].exists() and outputs[1].stat().st_size == 0:
                outputs[1].unlink()
        if handler:
            logging.getLogger().removeHandler(handler)
            handler.close()


if __name__ == "__main__":
    raise SystemExit(main())
