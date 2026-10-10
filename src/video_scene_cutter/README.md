# 動画シーン切り出しツール

MP4動画から、開始・終了タイムスタンプで指定した範囲を切り出します。
Python 3.9.5以降とFFmpegが必要です。

## 使い方

```powershell
python video_scene_cutter.py 入力動画.mp4 "00:03:41,338" "00:03:47,300"
```

出力先を指定する場合:

```powershell
python video_scene_cutter.py 入力動画.mp4 "00:03:41,338" "00:03:47,300" -o 切り出し動画.mp4
```

出力先を省略すると、入力動画と同じディレクトリへ保存します。既存ファイルを
上書きする場合は `--overwrite` を追加してください。FFmpegがPATHにない場合は、
`--ffmpeg C:\path\to\ffmpeg.exe` のように実行ファイルを指定できます。


コマンドプロンプト

python "C:\Users\user\git\amravie\src\video_scene_cutter\video_scene_cutter.py" "E:\backup_kenji\mov\n173\n173a1.mp4" "00:03:41,338" "00:03:47,300" --output "E:\backup_kenji\mov\n174\scene.mp4"