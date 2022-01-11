import cv2
import glob
from pydub import AudioSegment #音声操作用　mp3関連の処理
import ffmpeg

class JoinSilentVideAndSound:
    
    # コンストラクタ
    def __init__(self, configs):
        self.configs = configs

    # 実行
    def run(self):
        input_mp4_fp = self.configs['input_mp4_fp']
        input_mp3_fp = self.configs['input_mp3_fp']
        output_mp4_fp = self.configs['output_mp4_fp']
        
        # 映像を読みこむ
        stream_video = ffmpeg.input(input_mp4_fp)
        
        #オーディオを読み込む
        stream_audio = ffmpeg.input(input_mp3_fp)
        
        #合成
        stream = ffmpeg.output(stream_video, stream_audio, output_mp4_fp, vcodec="copy", acodec="copy")
        ffmpeg.run(stream)



        
