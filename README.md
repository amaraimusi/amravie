# amravie
動画加工ツール Amravie

## info
@since 2021-12-31
@version 0.0.1
@auther amaraimusi

## モードごとのconfig_x.txtの設定例

### mp4を音声なしmp4とmp3に分割するモード
```
mode = split_video_sound
input_mp4_fp = C:\Users\user\git\amravie\src\test_data\MVI_0887.MP4
input_mp4_fpと同じディレクトリに音声なしmp4とmp3を出力します。
```

### 音声なしmp4とmp3を連結する

```
mode = join_silent_video_and_sound
input_mp4_fp = C:\Users\user\git\amravie\src\test_data\MVI_0887_v_only.mp4
input_mp3_fp = C:\Users\user\git\amravie\src\test_data\join_bgm.mp3
```


### mp4とmp3をミキシングするモードの設定例
```
mode = mixing_mp4_mp3
input_mp4_fp = C:\Users\user\git\amravie\src\test_data\MVI_0887.MP4
input_mp3_fp = C:\Users\user\git\amravie\src\test_data\test1.mp3
volume = -10
position = 0
```

volume(ボリューム)はinput_mp3_fpの音量調整値。  -10～10 くらいの範囲で設定する。負値にすると音量は小さくなり、正値にすると音量は大きくなる。
合成位置。 0にすると先頭から合成、3000にすると3秒後から合成


### join_bgms 複数のbgmを連結して1つのbgmにする

```
mode = join_bgms
input_mp3_fp = C:\Users\user\git\amravie\src\test_data\test1.mp3
bgm_fp1=C:\Users\user\git\amravie\src\test_data\test1.mp3
bgm_fp2=C:\Users\user\git\amravie\src\test_data\test2.mp3
bgm_fp3=C:\Users\user\git\amravie\src\test_data\test1.mp3
bgm_fp4=C:\Users\user\git\amravie\src\test_data\test2.mp3
bgm_fp5=C:\Users\user\git\amravie\src\test_data\test1.mp3
bgm_fp6=C:\Users\user\git\amravie\src\test_data\test2.mp3
bgm_fp7=C:\Users\user\git\amravie\src\test_data\test1.mp3
bgm_fp8=C:\Users\user\git\amravie\src\test_data\test2.mp3

# 連結BGM再生時間（秒）
join_bgm_sec = 50
# 連結BGM間隔（秒）
join_intarval = 5
# 連結BGM出力ファイルパス
ouput_join_bgm_fp = C:\Users\user\git\amravie\src\test_data\join_bgm.mp3
```


### 複数のbgmを連結してmp4にミキシングする

```
mode = bgm_mixing
input_mp4_fp = C:\Users\user\git\amravie\src\test_data\MVI_0887.MP4
bgm_fp1=C:\Users\user\git\amravie\src\test_data\test1.mp3
bgm_fp2=C:\Users\user\git\amravie\src\test_data\test2.mp3
bgm_fp3=C:\Users\user\git\amravie\src\test_data\test1.mp3
bgm_fp4=C:\Users\user\git\amravie\src\test_data\test2.mp3
bgm_fp5=C:\Users\user\git\amravie\src\test_data\test1.mp3
bgm_fp6=C:\Users\user\git\amravie\src\test_data\test2.mp3
bgm_fp7=C:\Users\user\git\amravie\src\test_data\test1.mp3
bgm_fp8=C:\Users\user\git\amravie\src\test_data\test2.mp3
```
