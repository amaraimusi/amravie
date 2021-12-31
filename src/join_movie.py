


import cv2
import glob
from pydub import AudioSegment #音声操作用　mp3関連の処理
import ffmpeg

print('動画連結ツール ver 0.2.0')


# 動画の再生速度を変更する
# @param string input_fp 入力動画ファイルパス
# @param string output_fp 出力動画ファイルパス
# @param rete 変更後の再生速度倍率 　例:0.5→1/2のスローモーション, 2.0→2倍速再生
# 
def chageMovieSpeed(input_fp, output_fp, rate):
    # mp4を設定
    fourcc = cv2.VideoWriter_fourcc('m','p','4','v')
    
    movie = cv2.VideoCapture(input_fp)
    fps = int(movie.get(cv2.CAP_PROP_FPS))  
    print(f'変更前fps={str(fps)}')
    
    width = movie.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = movie.get(cv2.CAP_PROP_FRAME_HEIGHT)
    
    fps2 = fps * rate
    print(f'変更後fps={str(fps2)}')
    output = cv2.VideoWriter(output_fp, int(fourcc), fps2, (int(width), int(height)))
    
    while True:
        ret, frame = movie.read()        # フレームを取得
        output.write(frame)               # 動画を保存する
        # フレームが取得できない場合はループを抜ける
        if not ret:
            break
        
    # 撮影用オブジェクトとウィンドウの解放
    movie.release()

# 動画の再生速度を変更する
# @param string input_fp 入力動画ファイルパス
# @param string output_fp 出力動画ファイルパス
# @param rete 変更後の再生速度倍率 　例:0.5→1/2のスローモーション, 2.0→2倍速再生
# 
def chageMovieSpeed(input_fp, output_fp, rate):
    # mp4を設定
    fourcc = cv2.VideoWriter_fourcc('m','p','4','v')
    
    movie = cv2.VideoCapture(input_fp)
    fps = int(movie.get(cv2.CAP_PROP_FPS))  
    print(f'変更前fps={str(fps)}')
    
    width = movie.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = movie.get(cv2.CAP_PROP_FRAME_HEIGHT)
    
    fps2 = fps * rate
    print(f'変更後fps={str(fps2)}')
    output = cv2.VideoWriter(output_fp, int(fourcc), fps2, (int(width), int(height)))
    
    while True:
        ret, frame = movie.read()        # フレームを取得
        output.write(frame)               # 動画を保存する
        # フレームが取得できない場合はループを抜ける
        if not ret:
            break
        
    # 撮影用オブジェクトとウィンドウの解放
    movie.release()
    
# 動画リストを連結する。 mp4のみ対応
# - movie_fns [] 動画ファイルリスト（入力）
# - output_fn string 出力ファイル名（動画連結後のファイル名）
def join_movie(movie_fns, output_fn):

    # mp4を設定
    fourcc = cv2.VideoWriter_fourcc('m','p','4','v')

    # 動画リストの先頭動画からfps,画面幅を取得する
    movie = cv2.VideoCapture(movie_fns[0])
    fps = movie.get(cv2.CAP_PROP_FPS) # 動画のFPS
    height = movie.get(cv2.CAP_PROP_FRAME_HEIGHT)
    width = movie.get(cv2.CAP_PROP_FRAME_WIDTH)

    print('fps=' + str(fps))
    print('height=' + str(height))
    print('width=' + str(width))
    
    # pydubを使ってmp4ファイルの読み込み
    audio0 = AudioSegment.from_file(movie_fns[0], "mp4")
    audio_sec = audio0.duration_seconds# 再生時間
    print(f'音声0の長さ={str(audio_sec)}')

    # 出力ファイルを作成する。
    output = cv2.VideoWriter(output_fn, int(fourcc), fps, (int(width), int(height)))

    index = 0;
    first_loop_flg = True
    for movie_fn in (movie_fns):
        print(movie_fn)
        
        if first_loop_flg == True:
            first_loop_flg = False
        else:
            # 音声ファイルの結合
            audio = AudioSegment.from_file(movie_fn, "mp4")
            audio_sec = audio.duration_seconds# 再生時間
            
            audio0 += audio
        
        # 動画ファイルを読み込む
        movie = cv2.VideoCapture(movie_fn)
        #video_frame_count = movie.get(cv2.CAP_PROP_FRAME_COUNT) # フレーム数を取得する
        #fps2 = (audio_sec / video_frame_count) * 1000
        #video_fps = movie.get(cv2.CAP_PROP_FPS)                 # フレームレートを取得する
        #print(f'変更前video_fps={str(video_fps)}' )   
        #movie.set(cv2.CAP_PROP_FPS, fps2)
        #video_fps = movie.get(cv2.CAP_PROP_FPS)                 # フレームレートを取得する
        #print(f'変更後video_fps={str(video_fps)}' )   
        
        #video_len_sec = video_frame_count / video_fps         # 長さ（秒）を計算する
        # print(f'音声{index}の長さ={str(audio_sec)}')
        # print(f'fps2{index}の長さ={str(fps2)}')
        # print(f'cv2長さ={str(video_len_sec)}' )   

        # 動画連結処理
        ret = False
        if movie.isOpened() == True: # 読み込みに成功した場合
            ret, frame = movie.read() # 最初の1フレーム(1コマ）を取得する

        while ret:
            output.write(frame) # 1フレームずつ出力動画へ書き込む
            ret, frame = movie.read() # 次のフレームを取得する

        index = index + 1

    audio0.export("./output/audio.mp3", format="mp3")

# 動画ファイルの再生時間を取得する
def getTimeOfMovieCv2(movie_fn):
    movie = cv2.VideoCapture(movie_fn)
    video_fps = movie.get(cv2.CAP_PROP_FPS)                 # フレームレートを取得する
    video_frame_count = movie.get(cv2.CAP_PROP_FRAME_COUNT) # フレーム数を取得する
    video_time = (video_fps * video_frame_count) / 1000
    return video_time

# 音声ファイルの再生時間を取得する
def getTimeOfMoviePydub(movie_fn):
    movie = AudioSegment.from_file(movie_fn, "mp4")
    movie_sec = movie.duration_seconds# 再生時間
    return movie_sec

# 音声ファイルの再生時間を取得する
def getTimeOfSoundPydub(sound_fn):
    sound = AudioSegment.from_file(sound_fn, "mp3")
    sound_sec = sound.duration_seconds# 再生時間
    return sound_sec
    

print ('inputフォルダ内の動画を連結します。')

# inputフォルダ内の動画ファイル名をすべて取得する。
movie_fns = glob.glob("./input/*.mp4")
movie_fns = sorted(movie_fns) # 動画ファイル名リストを並べ替える。


# 連結後の動画ファイル名（出力ファイル名）
output_fn = "./output/movie_only.mp4"

join_movie(movie_fns, output_fn)

# ■■■□□□■■■□□□
time0 = getTimeOfMovieCv2('./output/movie_only.mp4')
print(f'movie_onlyの再生時間={str(time0)}')

# time1 = getTimeOfMoviePydub('./output/movie_only.mp4')
# print(f'movie_onlyの再生時間={str(time1)}')

sound_time = getTimeOfSoundPydub('./output/audio.mp3')
print(f'音声の再生時間={str(sound_time)}')

rate = sound_time / time0

chageMovieSpeed('./output/movie_only.mp4', './output/movie_only2.mp4', rate)

# 映像を読みこむ
stream_video = ffmpeg.input("./output/movie_only2.mp4")

#オーディオを読み込む
stream_audio = ffmpeg.input("./output/audio.mp3")

# #合成■■■□□□■■■□□□
# stream = ffmpeg.output(stream_video, stream_audio, "./output/output.mp4", vcodec="copy", acodec="copy")
# ffmpeg.run(stream)

print('Success')










