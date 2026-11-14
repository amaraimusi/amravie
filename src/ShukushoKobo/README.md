# 縮小工房（ShukushoKobo / shukusho-kobo）

Web用サムネイルをフォルダ単位で生成するPython 3.9用CLIです。
HTMLの説明は [使い方.html](使い方.html) を開いてください。

## インストール

PowerShellでこのフォルダに移動し、実行します。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 実行例

```powershell
.\.venv\Scripts\python.exe shukusho_kobo.py "TestData"
.\.venv\Scripts\python.exe shukusho_kobo.py "TestData" "work\width600" --width 600
.\.venv\Scripts\python.exe shukusho_kobo.py "TestData" "work\height300" --height 300
.\.venv\Scripts\python.exe shukusho_kobo.py "TestData" "work\thumbnails" --width 640 --height 360 --format webp --quality 85
.\.venv\Scripts\python.exe shukusho_kobo.py --help
```

## 引数

|引数|説明|既定値|
|---|---|---|
|input|対象フォルダ（必須）。ファイル単体は不可|なし|
|output|出力フォルダ（省略可）|入力フォルダの隣の `入力名_resized`|
|--width|最大幅、1以上の整数px|高さのみ指定時は自動計算。両方省略時は400|
|--height|最大高さ、1以上の整数px|幅のみ指定時は自動計算。両方省略時は400|
|--format|keep / png / jpeg / webp|keep|
|--quality|JPEG/WebPの品質、1～100|85|
|--workers|同時処理数、1以上|CPU数と4の小さい方|

片方のサイズだけ指定できます。画像ごとに縦横比を維持して、もう片方を自動計算します。
- `--width 600` のみ: 800×1600 → 600×1200。
- `--height 600` のみ: 1600×800 → 1200×600。
- 両方指定: 幅・高さの枠内に収めます。
- 両方省略: 従来どおり400×400の枠内に収めます（800×400 → 400×200）。

切り抜きや拡大はしません。指定したサイズより小さい画像は元のサイズを維持します。

## 入出力・安全性

- 直下のPNG/JPEG/WebP/BMP/TIFF/GIFを対象とし、サブフォルダは走査しません。
- keepではPNG/JPEG/WebPの形式を維持し、その他はPNGにします。
- GIF、WebP等のアニメーションや複数ページTIFFは先頭フレームのみ出力します。
- LANCZOSで縮小し、EXIFの撮影方向を反映します。透過はPNG/WebPで維持し、JPEG変換時は白背景に合成します。
- 位置情報等のメタデータは除去し、ICC色プロファイルは保持します。色空間の自動変換は行いません。
- 入力 `C:\images\photos` → 省略時の出力 `C:\images\photos_resized`。指定した出力先は必要に応じて作成します。
- 出力先の指定はフォルダです。入力と同じフォルダは拒否します。元画像は変更しません。
- 既存出力は常にスキップします。サイズを変更して再生成する場合は別の出力フォルダを指定してください。
- 形式変換により名前が重複する場合、最初の画像のみ処理し、後続はエラーとして報告します。
- 完成した一時ファイルから出力します。ハードリンク非対応の保存先では排他作成でコピーします。その間の強制終了では不完全な出力が残る場合があるため、該当出力を削除して再実行してください。
- 壊れた画像等は失敗として表示し、残りは続行します。巨大画像はPillowの安全制限が適用されます。
- 終了コード: 0=成功（既存出力のスキップ・対象0件を含む）、1=画像処理の失敗あり、2=引数・フォルダのエラー。
- 約150枚以上でもフォルダ単位で実行できます。メモリ不足の場合は `--workers 1` にしてください。

## テスト

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py" -v
```

一時フォルダで縦横比、透過、上書き防止、元画像保持、エラー継続、形式変換、EXIF回転、150枚一括処理を確認します。
実データの試行用出力には `work` を使用できます。
