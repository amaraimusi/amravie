"""032 歌詞動機: supplied lyrics -> audio-grounded line subtitles (Python 3.9)."""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import wave


class AlignmentError(ValueError):
    pass


def clean_lyrics(text):
    # Preserve newlines even inside multiline/nested annotations.
    depth = 0
    chars = []
    for char in text:
        if char == '[':
            depth += 1
        elif char == ']':
            if not depth:
                raise ValueError('歌詞に対応する [ がない ] があります。')
            depth -= 1
        elif not depth or char in '\r\n':
            chars.append(char)
    if depth:
        raise ValueError('歌詞の [ が閉じられていません。')
    lines = [line.strip() for line in ''.join(chars).splitlines() if line.strip()]
    if not lines:
        raise ValueError('注記と空行を除くと歌詞がありません。')
    return lines


def timestamp(milliseconds):
    seconds, ms = divmod(milliseconds, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f'{hours:02}:{minute:02}:{sec:02},{ms:03}'


def key(text):
    return ''.join(text.split())


def make_cues(lines, segments, duration):
    if len(lines) != len(segments):
        raise AlignmentError(f'行数が一致しません（歌詞 {len(lines)} / 解析 {len(segments)}）。')
    cues, problems = [], []
    previous = 0
    for number, (line, segment) in enumerate(zip(lines, segments), 1):
        words = segment.get('words') or []
        if key(segment.get('text', '')) != key(line):
            problems.append(f'{number}行目: 解析後の歌詞が一致しません。')
        try:
            start, end = float(segment['start']), float(segment['end'])
            valid = math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration + 0.05
            if not valid or not words:
                raise ValueError()
            start_ms, end_ms = round(start * 1000), min(round(end * 1000), round(duration * 1000))
            if start_ms < previous or end_ms <= start_ms:
                raise ValueError()
            previous = end_ms
            # Japanese subword tokens (small kana, punctuation, etc.) can have
            # zero duration legitimately. Reject invalid times and fully untimed
            # lines, but retain the audio-derived bounds of a timed line.
            if any(not math.isfinite(float(w['start'])) or
                   not math.isfinite(float(w['end'])) or w['end'] < w['start'] for w in words):
                problems.append(f'{number}行目: 単語の時刻が不正です。')
            if not any(w['end'] > w['start'] for w in words):
                problems.append(f'{number}行目: 歌詞の位置を特定できません。')
            cues.append((start_ms, end_ms, line))
        except (ValueError, KeyError, TypeError):
            problems.append(f'{number}行目: 時刻が不正、重複、または歌声を検出できません。')
    if problems:
        raise AlignmentError('\n'.join(problems))
    return cues


def write_srt(path, cues):
    content = '\n\n'.join(f'{i}\n{timestamp(start)} --> {timestamp(end)}\n{text}'
                            for i, (start, end, text) in enumerate(cues, 1)) + '\n'
    # Exclusive creation prevents accidental overwrites, including concurrent runs.
    with path.open('x', encoding='utf-8-sig', newline='\n') as stream:
        stream.write(content)


def parser():
    p = argparse.ArgumentParser(description='032 歌詞動機 / KashiDoki: MP3と歌詞を強制アライメントしてSRTにします。')
    p.add_argument('audio', type=Path, help='MP3ファイル')
    p.add_argument('lyrics', type=Path, help='歌詞テキスト（1行につき字幕1件）')
    p.add_argument('--encoding', default='utf-8-sig', help='歌詞の文字コード（例: cp932）')
    p.add_argument('--model', default='small', choices=['tiny', 'base', 'small', 'medium', 'large-v3'])
    p.add_argument('--language', default='ja', help='主な言語。日本語: ja、フランス語: fr')
    p.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    p.add_argument('--threads', type=int, default=4, help='CPUスレッド数（既定4）')
    p.add_argument('--ffmpeg', default='ffmpeg', help='ffmpeg.exe のパス')
    p.add_argument('--vocals', type=Path, help='任意: 同じ開始位置・長さの歌声分離済み音源')
    return p


def run(args):
    audio, lyrics = args.audio.resolve(), args.lyrics.resolve()
    if not audio.is_file() or audio.suffix.lower() != '.mp3':
        raise ValueError('入力MP3が見つかりません。')
    if not lyrics.is_file():
        raise ValueError('歌詞ファイルが見つかりません。')
    if args.threads < 1:
        raise ValueError('--threads は1以上にしてください。')
    lines = clean_lyrics(lyrics.read_text(encoding=args.encoding))
    ffmpeg = shutil.which(args.ffmpeg)
    if not ffmpeg:
        raise ValueError('FFmpegが見つかりません。PATHまたは --ffmpeg を指定してください。')
    try:
        import torch
        import stable_whisper
    except ImportError as exc:
        raise ValueError('依存ライブラリが必要です。python -m pip install -r requirements.txt を実行してください。') from exc
    source = args.vocals.resolve() if args.vocals else audio
    if not source.is_file():
        raise ValueError('歌声分離済み音源が見つかりません。')
    output = audio.parent / 'kasiDoki'
    data = output / 'data' / (audio.stem + '_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    data.mkdir(parents=True)
    wav = data / 'audio_16k.wav'
    (data / 'lyrics_clean.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    report = dict(audio=str(audio), lyrics=str(lyrics), source=str(source), model=args.model,
                  language=args.language, method='stable-ts Whisper attention / DTW forced alignment',
                  status='running')
    try:
        print('音源を16kHzモノラルに変換しています…', flush=True)
        converted = subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-i', str(source),
                                    '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)],
                                   capture_output=True)
        if converted.returncode:
            raise ValueError('音源変換に失敗: ' + converted.stderr.decode('utf-8', errors='replace'))
        with wave.open(str(wav), 'rb') as stream:
            duration = stream.getnframes() / stream.getframerate()
        torch.set_num_threads(args.threads)
        print(f'モデル {args.model} で歌声と歌詞を照合しています（初回はモデル取得）…', flush=True)
        model = stable_whisper.load_model(args.model, device=args.device,
                                          download_root=str(Path(__file__).parent / 'work' / 'models'))
        # Array input bypasses any second FFmpeg lookup and pins sample rate explicitly.
        import numpy as np
        with wave.open(str(wav), 'rb') as stream:
            samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').astype(np.float32) / 32768
        result = model.align(samples, '\n'.join(lines), language=args.language,
                             original_split=True, regroup=False, remove_instant_words=False,
                             suppress_silence=True, verbose=False)
        if result is None:
            raise AlignmentError('音声と歌詞を照合できませんでした。')
        raw = result.to_dict()
        (data / 'alignment.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
        cues = make_cues(lines, raw['segments'], duration)
        review = []
        for number, segment in enumerate(raw['segments'], 1):
            words = segment['words']
            instant_ratio = sum(w['end'] <= w['start'] for w in words) / len(words)
            probabilities = [w['probability'] for w in words if w.get('probability') is not None]
            mean_probability = sum(probabilities) / len(probabilities) if probabilities else None
            if instant_ratio >= 0.5 or (mean_probability is not None and mean_probability < 0.25):
                review.append(dict(line=number, text=lines[number - 1],
                                   instant_token_ratio=instant_ratio, mean_probability=mean_probability))
        destination = output / (audio.stem + '.srt')
        if destination.exists():
            destination = output / (data.name + '.srt')
        write_srt(destination, cues)
        report.update(status='success', srt=str(destination), duration=duration, cues=len(cues), review=review)
        print(f'SRTを作成しました: {destination}')
        print('歌唱・伴奏・多言語の影響でずれる場合があります。音源と照合してください。')
        if review:
            print(f'要確認: {len(review)}行（report.json の review を参照）')
    except KeyboardInterrupt:
        report.update(status='interrupted', error='ユーザーが中断しました。')
        raise
    except Exception as exc:
        report.update(status='failed', error=str(exc))
        raise
    finally:
        (data / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'解析データ: {data}', flush=True)


def main():
    args = parser().parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        print('中断しました。', file=sys.stderr)
        return 130
    except Exception as exc:
        print(f'エラー: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
