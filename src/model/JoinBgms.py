import os
import cv2
import glob
from pydub import AudioSegment #音声操作用　mp3関連の処理
import ffmpeg


# 複数のbgmを連結して1つのbgmにする
# since 2022-1-3 | 2022-1-4
# version 1.0.0
# auther amaraimusi
class JoinBgms:
    
    # コンストラクタ
    def __init__(self, configs):
        self.configs = configs
    
    def run(self):
        configs = self.configs
        ouput_join_bgm_fp = configs['ouput_join_bgm_fp']
        join_bgm_sec = int(configs['join_bgm_sec'])
        join_intarval = int(configs['join_intarval'])
        
        print('連結BGM再生時間→' +  str(join_bgm_sec))
        print('連結BGM間隔時間→' +  str(join_intarval))
        
        bgmFps = self.__getBgmFps(configs) # BGMファイルパスリストを取得する
        
        audio0 = None
        silent = AudioSegment.silent(duration=join_intarval * 1000) # サイレント時間を作成
        
        # BGMをサイレントを間隔に入れつつ結合していく。
        for i, bgm_fp in enumerate(bgmFps):
            print('連結BGM→' + bgm_fp)
            audio1 = AudioSegment.from_file(bgm_fp, "mp3")
            if i==0:
                audio0 = audio1
            else:
                audio0 = audio0 + silent + audio1
                
            sec = audio0.duration_seconds
            print(sec)
            
            if join_bgm_sec < sec:
                break
        
        # 連結BGM再生時間をカットする。
        audio0 = audio0[0:join_bgm_sec * 1000]
        
        # BGMの末尾にフェードアウトを入れる
        audio0 = audio0.fade_out(5000)
        
        audio0.export(ouput_join_bgm_fp,  format="mp3")
        
        print('出力mp3ファイルパス→' +  ouput_join_bgm_fp)

        
    # BGMファイルパスリストを取得する
    def __getBgmFps(self, configs) :
        bgmFps = []
        for num in range(8):
            key = 'bgm_fp' + str(num)
            if configs.get(key) != '':
                bgmFps.append(configs[key])
        
        return bgmFps

    # 既存ファイルが存在するなら除去
    def __removeExifFile(self, fp):
        if os.path.exists(fp):
            os.remove(fp)

    # 動画の再生時間を取得する(秒）
    def __getDurationForMp4Ffmeg(self, input_mp4_fp):
        probe = ffmpeg.probe(input_mp4_fp)
        movInfo = probe['streams'][0];
        mov_duration = float(movInfo['duration']); # 動画再生時間
        return mov_duration
      
        
    # 文字列を右側から印文字を検索し、右側の文字を切り出す
    # @param string s 対象文字列
    # @param $mark 印文字
    # @return 印文字から右側の文字列
    def __stringRightRev(self, s, mark):
        a =s.rfind(mark)
        res = s[a+len(mark):]
        return res
    
    
    # 文字列を右側から印文字を検索し、左側の文字を切り出す
    # @param string s 対象文字列
    # @param $mark 印文字
    # @return 印文字から左側の文字列
    def __stringLeftRev(self, s, mark):
        a =s.rfind(mark)
        res = s[0:a]
        return res
    
       # mp4を音声なしmp4とmp3に分割する。(時間もそろえる）
    # @param string input_fp 入力動画ファイルパス
    # @param string output_mp4_fp 出力動画ファイルパス（音声なしmp4)
    # 
    def videoOnly(self, input_fp, output_mp4_fp):
        
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

        