import sys
import os
import ffmpeg
from pydub import AudioSegment

# python 22_time_lapse_ex.py 入力動画ファイルパス 出力動画ファイルパス 倍率
# cd C:\Users\user\git\amravie\src && python 22_time_lapse_ex.py E:\backup_kenji\mov\n134\s20b2.mp4 E:\backup_kenji\mov\n134\s20b12.mp4 8

def create_time_lapse(input_video_path, time_lapse_video_path, speed_factor):
    """
    指定した倍率でタイムラプス動画を生成します。
    """
    try:
        (
            ffmpeg
            .input(input_video_path)
            .filter('setpts', f'{1 / speed_factor}*PTS')  # 動画の速度を変更
            .output(time_lapse_video_path, r=30)  # 出力フレームレートを指定
            .run(overwrite_output=True)
        )
        print(f"タイムラプス動画を生成しました: {time_lapse_video_path}")
    except ffmpeg.Error as e:
        print(f"FFmpegでエラーが発生しました（タイムラプス生成）: {e.stderr.decode('utf8')}")
        sys.exit(1)


def create_silent_mp3(duration_ms, silent_audio_path):
    """
    指定した長さ（ミリ秒）の無音MP3ファイルを作成します。
    """
    silent_audio = AudioSegment.silent(duration=duration_ms)
    silent_audio.export(silent_audio_path, format="mp3")
    print(f"無音MP3を作成しました: {silent_audio_path}")


def add_silent_audio_to_video(input_video_path, final_output_video_path):
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
        # 既存の音声を削除
        ffmpeg.input(input_video_path).output('temp_video.mp4', an=None, vcodec='copy').run(overwrite_output=True)

        # 無音のMP3を動画に追加
        ffmpeg.concat(
            ffmpeg.input('temp_video.mp4'),
            ffmpeg.input(silent_mp3_path),
            v=1, a=1
        ).output(final_output_video_path).run(overwrite_output=True)

        print(f"無音MP3をセットした動画ファイルを作成しました: {final_output_video_path}")
    finally:
        # 一時ファイルを削除
        if os.path.exists(silent_mp3_path):
            os.remove(silent_mp3_path)
        if os.path.exists('temp_video.mp4'):
            os.remove('temp_video.mp4')


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("使い方: python 22_time_lapse_ex.py 入力動画ファイルパス 出力動画ファイルパス 倍率")
        sys.exit(1)

    input_video_path = sys.argv[1]
    output_video_path = sys.argv[2]
    try:
        speed_factor = float(sys.argv[3])  # 倍率を取得
        if speed_factor <= 0:
            raise ValueError("倍率は正の数である必要があります。")
    except ValueError as e:
        print(f"倍率が無効です: {e}")
        sys.exit(1)

    # 一時ファイルパス
    time_lapse_video_path = "temp_time_lapse.mp4"

    try:
        # タイムラプス動画を生成
        create_time_lapse(input_video_path, time_lapse_video_path, speed_factor)

        # タイムラプス動画に無音MP3をセット
        add_silent_audio_to_video(time_lapse_video_path, output_video_path)
    finally:
        # 一時ファイルを削除
        if os.path.exists(time_lapse_video_path):
            os.remove(time_lapse_video_path)
