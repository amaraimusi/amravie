# 033 SceneTransition（シーントランジション）

指示CSVの行順にシーンイラストを並べ、切り替え効果を付けたMP4を作る Windows 用コマンドラインツールです。

## インストール

Python 3.9 と FFmpeg を用意し、コマンドプロンプトで `python --version` と `ffmpeg -version` が実行できることを確認します。FFmpegには libx264 と AAC エンコーダーが必要です。H.265を選ぶ場合は libx265 も必要です。FFmpegをPATHに追加できない場合は `--ffmpeg "C:\ffmpeg\bin\ffmpeg.exe"` を指定します。

```cmd
cd C:\Users\user\git\amravie\src\033_SceneTransition && python -m pip install Pillow
```

## コマンドプロンプトでの実行例

付属の4枚のイラストで試す例。

```cmd
cd C:\Users\user\git\amravie\src\033_SceneTransition && python scene_transition.py TestData\sample.csv -o ..\work\sample.mp4
```

保存先を省略すると、上の例では `TestData\sample.mp4` に出力されます。

音声を追加し、画面比率、フレームレート、コーデックを指定する例。`曲.mp3` はCSVと同じフォルダに置きます。

```cmd
cd C:\Users\user\git\amravie\src\033_SceneTransition && python scene_transition.py TestData\sample.csv -o ..\work\音声付き.mp4 --audio "曲.mp3" --aspect-ratio 4:5 --fps 24 --codec h265
```

| 引数 | 内容 |
| --- | --- |
| `CSV [MP4] [MP3]` | CSVは必須。MP4とMP3は省略可 |
| `-o` / `--output` | MP4保存先。省略時はCSVと同じ場所・ベース名 |
| `-a` / `--audio` | MP3音源。保存先を省略して音源を指定するときにも使用可 |
| `--aspect-ratio` | 既定は16:9（1920×1080）。9:16では1080×1920。画像の縦横比を保持し、余白を黒で埋める |
| `--fps` | 正の整数。既定は30 |
| `--codec` | `h264`（既定）または `h265` |
| `--overwrite` | 既存のMP4を上書きする |
| `--ffmpeg` | FFmpegのコマンド名または実行ファイルパス |
| `--help` | 引数一覧を表示する |

CSV自体は実行時のカレントディレクトリから指定します。画像、MP3、出力先の相対パスはCSVのあるフォルダが基準です。日本語や空白を含むパスも使えます。コマンドラインで空白を含むパスは二重引用符で囲みます。

## 指示CSV

UTF-8（BOMあり・なし）で保存します。ヘッダーと付属サンプルの内容は次のとおりです。

```csv
image_path,duration_ms,transition,transition_ms
scene_002.png,1500,cut,0
scene_003.png,1300,crossfade,300
scene_004.png,1100,wipe,400
scene_005.png,1600,fadeblack,500
```

| 列 | 内容 |
| --- | --- |
| `image_path` | シーンイラストへのパス |
| `duration_ms` | 切り替え後に画像を保持する時間。正の整数（ms） |
| `transition` | この行の画像へ切り替える効果 |
| `transition_ms` | 切り替えに使う時間（ms）。カットなら0、その他は正の整数 |

最初のシーンは `cut,0` を指定します。`transition` を空欄にすると、`transition_ms` が正の場合はクロスディゾルブ、0の場合はカットです。

| 値 | 効果 |
| --- | --- |
| `cut` | 瞬時に切り替える |
| `crossfade` | 前後の画像を徐々に混ぜる |
| `fadeblack` | 黒を経由する |
| `wipe` | 次の画像が右から左へ現れる |
| `slide` | 前の画像が左に抜け、次の画像が右から入る |
| `zoom` | 前の画像を拡大しながら次の画像へ切り替える |
| `blur` | 切り替えの途中で画像をぼかす |

理論上の映像尺は全行の `duration_ms + transition_ms` の合計です。区間の累積時刻を最寄りのフレーム境界に丸めます。短い区間はフレームに割り当てられない場合があります。

MP3を指定すると、映像生成後に音声をAACに変換して組み込みます。映像トラックと音声トラックはそれぞれの長さを維持します。音声が長い場合、MP4全体の再生時間は映像トラックより長くなります。

一時ファイルは `work` と出力先の一時フォルダに作成し、処理終了時に片付けます。CSVの列や数値の不備、画像の欠落はメッセージを表示して終了します。
