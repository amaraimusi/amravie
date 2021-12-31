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

