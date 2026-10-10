import sys
import os
from pydub import AudioSegment
import ffmpeg

# コマンドの例→ cd C:\Users\user\git\amravie\src && python 20_no_sound.py E:\backup_kenji\mov\n134\s20b2.mp4 E:\backup_kenji\mov\n134\s20b8.mp4

def create_silent_mp3(duration_ms, output_path):
    """
    指定した長さ（ミリ秒）の無音MP3ファイルを作成します。
    """
    silent_audio = AudioSegment.silent(duration=duration_ms)
    silent_audio.export(output_path, format="mp3")
    print(f"無音MP3を作成しました: {output_path}")

def add_silent_audio_to_video(input_video_path, output_video_path):
    """
    入力動画ファイルから既存の音声を除去し、無音のMP3ファイルをセットして新しい動画ファイルを作成します。
    """
    # 入力動画の情報を取得
    probe = ffmpeg.probe(input_video_path)
    video_duration = float(probe['format']['duration']) * 1000  # 秒をミリ秒に変換

    # 無音のMP3ファイルを一時作成
    silent_mp3_path = "silent_temp.mp3"
    create_silent_mp3(video_duration, silent_mp3_path)

    try:
        # 既存の音声を除去
        ffmpeg.input(input_video_path).output('temp_video.mp4', an=None, vcodec='copy').run(overwrite_output=True)

        # 無音のMP3を動画に追加
        ffmpeg.concat(
            ffmpeg.input('temp_video.mp4'),
            ffmpeg.input(silent_mp3_path),
            v=1, a=1
        ).output(output_video_path).run(overwrite_output=True)

        print(f"無音MP3をセットした動画ファイルを作成しました: {output_video_path}")
    finally:
        # 一時ファイルを削除
        if os.path.exists(silent_mp3_path):
            os.remove(silent_mp3_path)
        if os.path.exists('temp_video.mp4'):
            os.remove('temp_video.mp4')

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("使い方: python 20_no_sound.py 入力動画ファイルパス 出力動画ファイルパス")
        sys.exit(1)

    input_video_path = sys.argv[1]
    output_video_path = sys.argv[2]

    if not os.path.exists(input_video_path):
        print(f"入力動画ファイルが見つかりません: {input_video_path}")
        sys.exit(1)

    add_silent_audio_to_video(input_video_path, output_video_path)
