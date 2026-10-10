# amravie
動画加工ツール Amravie

## MP4のシーン切替時刻を検出する

クロスフェードのない動画を一定間隔で比較し、画面全体の色差からシーン切替を検出します。

```powershell
pip install -r requirements.txt
python src/scene_timestamp.py C:\path\to\video.mp4
```

結果は入力動画と同じ場所の `video_scenes.csv` に保存されます。画面内の動きで
誤検出する場合は閾値を上げ、切替を見逃す場合は下げます。

```powershell
python src/scene_timestamp.py video.mp4 --threshold 0.15
python src/scene_timestamp.py video.mp4 --threshold 0.08
python src/scene_timestamp.py video.mp4 --format json
```

主な調整項目:

- `--threshold`: 色差の閾値（既定値 0.12）
- `--interval`: フレーム比較間隔（既定値 0.2秒）
- `--min-scene`: 最短シーン長（既定値 3秒）

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
