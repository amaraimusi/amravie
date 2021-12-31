import cv2
import glob
from pydub import AudioSegment #音声操作用　mp3関連の処理
import ffmpeg

class SplitVideoSound:
    
    # コンストラクタ
    def __init__(self, configs):
        self.configs = configs

    # 実行
    def run(self):
        input_mp4_fp = self.configs['input_mp4_fp']
        output_mp4_fp = self.configs['output_mp4_fp']
        output_mp3_fp = self.configs['output_mp3_fp']
        
        # mp4を音声なしmp4とmp3に分割する。
        self.splitVideoAndSound(input_mp4_fp, output_mp4_fp, output_mp3_fp)

        
    # mp4を音声なしmp4とmp3に分割する。(時間もそろえる）
    # @param string input_fp 入力動画ファイルパス
    # @param string output_mp4_fp 出力動画ファイルパス（音声なしmp4)
    # @param string output_mp3_fp 出力音声ファイルパス（mp3)
    # 
    def splitVideoAndSound(self, input_fp, output_mp4_fp, output_mp3_fp):
        
        sound = AudioSegment.from_file(input_fp, "mp4")
        sound_sec = sound.duration_seconds # 再生時間
        print(f'音声ファイルの長さ={str(sound_sec)}')
        
        movie = cv2.VideoCapture(input_fp)
        width = movie.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = movie.get(cv2.CAP_PROP_FRAME_HEIGHT)
        video_frame_count = movie.get(cv2.CAP_PROP_FRAME_COUNT) # フレーム数を取得する
        video_fps = movie.get(cv2.CAP_PROP_FPS) 
        print(f'入力動画ファイルのFPS={str(video_fps)}')
        #video_time = (video_fps * video_frame_count) / 1000
        print(f'入力動画ファイルのフレーム数={str(video_frame_count)}')
        
        output_video_fps = video_frame_count / sound_sec
        print(f'出力動画ファイルのfps={str(output_video_fps)}')
        
        # 出力動画ファイルの用意(mp4)
        fourcc = cv2.VideoWriter_fourcc('m','p','4','v')
        output = cv2.VideoWriter(output_mp4_fp, int(fourcc), output_video_fps, (int(width), int(height)))
        print(f'{output_mp4_fp}の出力開始')
        
        while True:
            ret, frame = movie.read()
            output.write(frame)
            if not ret:
                break
        
        # 映像オブジェクトの解放
        movie.release()
        print(f'{output_mp4_fp}の出力完了')
    
        # 音声ファイルの出力
        sound.export(output_mp3_fp, format="mp3")
        print(f'{output_mp3_fp}の出力完了')
        
