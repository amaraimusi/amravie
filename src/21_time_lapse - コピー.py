import sys
import os
import ffmpeg

def create_time_lapse(input_video_path, output_video_path, speed_factor):
    """
    指定した倍率でタイムラプス動画を生成します。

    Args:
        input_video_path (str): 入力動画ファイルのパス。
        output_video_path (str): 出力動画ファイルのパス。
        speed_factor (float): タイムラプスの速度倍率。
    """
    if not os.path.exists(input_video_path):
        print(f"入力動画ファイルが見つかりません: {input_video_path}")
        sys.exit(1)

    try:
        # FFmpegでタイムラプス動画を生成
        (
            ffmpeg
            .input(input_video_path)
            .filter('setpts', f'{1 / speed_factor}*PTS')  # 動画の速度を変更
            .output(output_video_path, r=30)  # 出力フレームレートを指定
            .run(overwrite_output=True)
        )
        print(f"タイムラプス動画を生成しました: {output_video_path}")
    except ffmpeg.Error as e:
        print(f"FFmpegでエラーが発生しました: {e.stderr.decode('utf8')}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("使い方: python 21_time_lapse.py 入力動画ファイルパス 出力動画ファイルパス 倍率")
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

    create_time_lapse(input_video_path, output_video_path, speed_factor)
