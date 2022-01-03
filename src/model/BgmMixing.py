import os
import cv2
import glob
from pydub import AudioSegment #音声操作用　mp3関連の処理
import ffmpeg

# 複数のbgmを連結してmp4にミキシングします
# since 2022-1-2
# version 1.0.0
# auther amaraimusi
class BgmMixing:
    
    # コンストラクタ
    def __init__(self, configs):
        self.configs = configs
    
    def run(self):
        configs = self.configs
        input_mp4_fp = configs['input_mp4_fp'];
        output_mp4_fp = configs['output_mp4_fp'];
        
        print('入力mp4ファイルパス→' +  input_mp4_fp)
        print('出力mp4ファイルパス→' +  output_mp4_fp)
        
        bgmFps = self.__getBgmFps(configs) # BGMファイルパスリストを取得する
        
        # position = configs['position']
        # volume = configs['volume']
        # print('position=' + position)
        # print('volume=' + volume)
        # position = int(position);
        # volume = int(volume);
        #
        # ext = self.__stringRightRev(input_mp4_fp, '.')
        # ext = ext.lower()
        # if ext != 'mp4':
        #     print('mp4ファイルでありません。処理を中断します。')
        #     exit()
        #
        # ext = self.__stringRightRev(input_mp3_fp, '.')
        # ext = ext.lower()
        # if ext != 'mp3':
        #     print('合成オーディオファイルはmp3ファイルでありません。処理を中断します。')
        #     exit()
        #
        # #■■■□□□■■■□□□一時出力ファイルが必要なので保留
        # # tmp_fn = 'tmp' + u +  ' .mp3'
        # #
        #
        # left_path = self.__stringLeftRev(input_mp4_fp, '.') # 拡張子から左側のパス
        #
        # #■■■□□□■■■□□□一時出力ファイルが必要なので保留
        # # output_mp4_fp = left_path + '_' + u + '.mp4'
        # # print('出力ファイルパスmp4→' +  output_mp4_fp)
        # #
        # #
        # #
        # # 動画の再生時間を取得する（秒）
        # mov_duration = self.__getDurationForMp4Ffmeg(input_mp4_fp)
        # print(f'入力mp4ファイルの再生時間→{mov_duration}')
        #
        # print('動画の元音声を読込')
        # audio1 = AudioSegment.from_file(input_mp4_fp, "mp4")
        # audio1_duration =audio1.duration_seconds ; # audio1の再生時間を取得
        # print(f'元音声の再生時間→{audio1_duration}')
        #
        # # 映像の再生時間と元音声の再生時間が2秒以上乖離しているなら元音声に無音を追加して、調整をする。
        # if mov_duration > audio1_duration + 2:
        #     print('入力mp4の映像の再生時間と音声が著しく乖離しています。なので無音を追加して調整します。')
        #     print('動画の再生時間→' + str(mov_duration))
        #     print('音声の再生時間→' + str(audio1_duration))
        #     add_ms = (mov_duration - audio1_duration) * 1000;
        #     print(audio1_duration)
        #     add_silent = AudioSegment.silent(duration=add_ms) #１秒
        #     audio1 = audio1 + add_silent;
        #     print(f'元音声の再生時間を調整→{str(audio1.duration_seconds)}'  )
        #
        #
        # print('入力mp3ファイルを読み込みます')
        # audio2 = AudioSegment.from_file(input_mp3_fp, "mp3")
        #
        # print('入力mp3の音量調整')
        # audio2 = audio2 + volume #音量を変更
        # print(f'入力mp3の再生時間→{str(audio2.duration_seconds)}'  )
        #
        #
        # print('元音声と入力mp3のミキシングして、ミックスした音声を仮mp3として出力します。')
        # tmp_mp3_fp = left_path + '_tmp.mp3'
        # self.__removeExifFile(tmp_mp3_fp) # 既存ファイルを除去
        # audio3 = audio1.overlay(audio2, position=position)
        # audio3.export(tmp_mp3_fp,  format="mp3")
        #
        #
        # print('映像のみの動画である仮mp4を生成する。')
        # tmp_mp4_fp = left_path + '_tmp.mp4' 
        # self.__removeExifFile(tmp_mp4_fp) # 既存ファイルを除去
        # self.videoOnly(input_mp4_fp, tmp_mp4_fp)
        #
        #
        # self.__removeExifFile(output_mp4_fp) # 既存ファイルを除去
        #
        # # 映像を読みこむ
        # print('映像と音声の再結合処理中...')
        # stream_video = ffmpeg.input(tmp_mp4_fp)
        # stream_audio = ffmpeg.input(tmp_mp3_fp)
        # stream = ffmpeg.output(stream_video, stream_audio, output_mp4_fp, vcodec="copy", acodec="copy")
        # print('最終出力中...')
        # ffmpeg.run(stream)
        # print(f'最終出力→{output_mp4_fp}')
        #
        # # 既存ファイルを除去
        # self.__removeExifFile(tmp_mp4_fp) 
        # self.__removeExifFile(tmp_mp3_fp) 
        
        
        
    # BGMファイルパスリストを取得する
    def __getBgmFps(self, configs) :
        
        return

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

        