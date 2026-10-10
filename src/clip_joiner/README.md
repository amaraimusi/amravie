# ClipJoiner（動画連結ツール）

正規化済みのMP4を自然名前順などで並べ、FFmpeg concat demuxerのストリームコピーで連結します。動画と同じベース名のSQLiteおよびUTF-8テキストレポートも作成します。

```powershell
python clip_joiner.py "E:\backup_kenji\mov\n174\TEST"
python clip_joiner.py INPUT_DIR OUTPUT.mp4 --sort mtime --reverse
python clip_joiner.py INPUT_DIR --overwrite --duration-tolerance 0.1
python clip_joiner.py INPUT_DIR --overwrite --audio-codec ac3
```

FFmpegとffprobeをPATH上、またはこのディレクトリの一つ上に配置してください。入力ファイル自体は変更しません。既存出力は `--overwrite` を指定した場合だけ置き換えます。

通常はAAC音声も無変換の `--audio-codec copy` を使います。AACの再生に問題がある環境では、映像を無変換のまま音声だけAC3 192kbpsへ変換する `--audio-codec ac3` を利用できます。
