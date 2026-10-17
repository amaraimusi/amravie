# SubVoice — 字幕読み上げツール

Python 3.9でSRT字幕をStyle-Bert-VITS2に渡し、各字幕の開始時刻から自然な朗読を配置するCLIです。
開始位置 ＞ 自然な朗読 ＞ 終了時刻を優先。終了時刻への強制フィットは行いません。

## 必要環境・Windowsへの導入

Python 3.9 x64、モデルをロードする十分なメモリとディスク容量、初回取得用インターネット接続。
CPUが既定でCUDAは必須ではありません。CPU推論は時間がかかる場合があります。

```powershell
cd C:\Users\user\git\amravie\src\SubVoice
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

以後のpythonはこの専用環境のものを使ってください。既存のWinPythonのライブラリは変更しません。

## Style-Bert-VITS2とモデル配置

PyPI配布の2.5.0（Python >=3.9）を使用。本体はコピーせず、ライブラリAPIを直接呼び出します。
日本語JP/JP-Extraのsafetensorsモデルを対象とし、ONNXは未対応です。
モデルは同梱しません。配布元で利用条件を確認して取得してください。
モデルフォルダに `.safetensors`、`config.json`、`style_vectors.npy` を配置します。
重みが1個なら自動検出し、複数ある場合はsafetensorsファイル自体を指定します。
初回に日本語BERT `ku-nlp/deberta-v2-large-japanese-char-wwm` を取得し、work/bert-cacheへ保存します。
取得済みBERTは `--bert-model` で指定できます。日本語辞書の初回取得にも接続が必要な場合があります。

確認した一次資料（2026-10-17）:
- https://pypi.org/project/style-bert-vits2/2.5.0/
- https://github.com/litagin02/Style-Bert-VITS2/blob/2.5.0/style_bert_vits2/tts_model.py
- https://github.com/litagin02/Style-Bert-VITS2/blob/2.5.0/style_bert_vits2/nlp/bert_models.py
- https://github.com/litagin02/Style-Bert-VITS2/blob/2.5.0/pyproject.toml

## 基本実行

```powershell
.venv\Scripts\python.exe subvoice.py "E:\backup_kenji\mov\n175\n175.srt" --model "C:\tts\models\voice"
.venv\Scripts\python.exe subvoice.py --model "C:\tts\models\voice" --list-styles
.venv\Scripts\python.exe subvoice.py "movie.srt" --model "C:/tts/models/voice" --speed 0.95 --style Neutral
.venv\Scripts\python.exe subvoice.py "movie.srt" --analyze-only
```

`subvoice_config.example.json` を `subvoice_config.json` にコピーし実際のモデルを登録すれば、
`python subvoice.py "movie.srt" --config subvoice_config.json` で実行できます。
SubVoiceフォルダのsubvoice_config.jsonは存在すれば自動読込みするため、`python subvoice.py "movie.srt"` だけでも実行できます。
CLI指定がJSONより優先します。設定のキーは引数名のハイフンをアンダースコアにしたものです。
設定JSONの相対パスは実行時のカレントディレクトリ基準です。

## モデル管理とライセンス

model_profiles.jsonは初期状態では空です。次のように登録すると `--model my_voice` で選択できます。
プロファイル中のモデル相対パスはプロファイルファイルの親を基準に解決します。

```json
{
  "my_voice": {
    "name": "モデル正式名称",
    "path": "C:/tts/models/voice",
    "source": "配布元URL",
    "license": "UNKNOWN",
    "credit": "配布元で指定されたクレジット文章"
  }
}
```

ライセンス情報は推測しません。未登録の項目はUNKNOWN、未登録クレジットには確認を促す文章を出します。
モデルの公開・商用利用・クレジット条件は配布元に従ってください。クレジットTXTは利用許可の保証ではありません。
エンジンのライセンスと音声モデルの条件は別です。2.5.0のパッケージメタデータはAGPL-3.0です。
配布・組込み時には原文を確認してください。

## 音声と重複の仕様

speed=1.0が標準、0.9は遅く、1.1は速くなります。inferのlengthへ1/speedを渡します。
styleはモデル固有。pitch/intonationは通常1.0で、変更時はエンジンの後処理により音質が変わります。
allow/warnはいずれも開始位置・自然な速度を保ち重複を警告します。
avoidのみ、次字幕の開始までの空きに応じ1回再合成します。既定最大1.15倍、指定可能上限1.25倍。
収まらない重複は残して警告します。開始時刻を遅らせたり音声を切断したりしません。

改行は空白として結合し、HTML/SRT装飾タグは除去、句読点は保持します。
読み辞書は `dictionary.example.json` のような「表記:読み」の単純置換です。
長いキーを優先し1回だけ置換します。音素・アクセント辞書ではありません。
UTF-8（BOM可）が既定。別の文字コードは `--encoding cp932` などで指定します。

## オプション一覧

| 引数 | 説明・初期値 |
|---|---|
| SRT | 入力ファイル |
| --model | プロファイル名・モデルフォルダ・safetensors |
| --config | JSON設定ファイル |
| --profiles | 台帳JSON（同梱model_profiles.json） |
| --output-dir | 出力先（SRTと同じ場所） |
| --work-dir | 作業先（SubVoice/work） |
| --dictionary | 読み置換JSON |
| --encoding | SRT文字コード（utf-8-sig） |
| --device | cpu / cuda（cpu） |
| --bert-model | 日本語BERTのパスまたはHF ID |
| --style | スタイル名（Neutral） |
| --speaker-id | 話者ID（0） |
| --speed | 速度倍率（1.0） |
| --style-weight | スタイル強度（1.0） |
| --pitch | ピッチ倍率（1.0） |
| --intonation | 抑揚倍率（1.0） |
| --sdp-ratio | DP/SDP比率 0～1（0.2） |
| --noise | 音声ノイズ係数（0.6） |
| --noise-w | SDPノイズ係数（0.8） |
| --overlap-mode | allow / warn / avoid（warn） |
| --max-speedup | avoidの最大加速率 1～1.25（1.15） |
| --overwrite | 明示的に同名を上書き |
| --keep-work | 実行時一時ファイルを保持 |
| --list-styles | モデルのスタイル一覧を表示 |
| --analyze-only | モデルなしでSRT解析のみ |
| --help | CLIヘルプ |

## 出力ファイル・作業ファイル

既定は入力と同じフォルダに `n175_subvoice.wav`、`n175_subvoice_credit.txt`、`n175_subvoice.log`。
3ファイルのいずれかが既存なら共通名に_001等を付けます。--overwriteのみ上書きを許可します。
WAVは44.1kHz・モノラル・PCM16。冒頭と字幕間は無音、最後は音声末尾までです。
字幕終了時刻までの無音追加はしません。重複音声を加算し、ピーク超過時は全体ゲインを下げます。
長尺は作業ディスクへメモリマップを使用するため十分な空き容量が必要です。

一時音声はwork/run-*に隔離し、成功・失敗時に削除。--keep-workで保存可能です。
BERTキャッシュは再利用のため保持し、不要なら手動削除できます。
字幕音声の再合成キャッシュは未実装。Engineインターフェースの前段へ追加できる構造です。
解析のみではログだけを作成し、WAV/クレジットは出力しません。
終了コードは0=成功、1=継続不能、2=一部字幕失敗（成功分の音声を出力）。

## 構成・テスト

subvoice.py（制御）、config.py、srt_parser.py、tts_engine.py（共通EngineインターフェースとSBV2）、
model_manager.py、audio_timeline.py、credit_manager.pyに分離。
requirements.txt、model_profiles.json、設定/辞書のexample.json、SubVoice_使い方.html、
tests/test_subvoice.py、TEST_RESULTS.md、work/.gitkeepを同梱します。

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe subvoice.py "E:\backup_kenji\mov\n175\n175.srt" --analyze-only
```

実データテストは指定SRTが存在すれば実行します。検証用Engineは一定値の信号を生成します。
これはStyle-Bert-VITS2の朗読ではありません。実音声の検証状況はTEST_RESULTS.mdを参照。

## トラブルシューティング

- ライブラリ不足: 実行中のPythonが専用環境か確認しrequirements.txtを導入してください。
- モデル未指定: --modelか設定JSONに登録してください。
- モデル読込失敗: 3ファイルの存在・対応するconfig・スタイル数を確認してください。
- スタイルエラー: --list-stylesでモデル固有の名称を確認してください。
- BERT/日本語辞書取得失敗: 接続・書込権限・空き容量、--bert-modelのパスを確認してください。
- CUDAエラー: --device cpuに戻してください。
- SRT解析エラー: ログのブロック、文字コード、タイムスタンプ、空行を確認してください。
- 一部字幕失敗: ログの字幕番号を確認。全件失敗時はWAVを出力しません。
- 出力失敗: 権限・空き容量・別アプリでWAVを開いていないか確認してください。

## 本環境での検証状況

Python 3.9.5への依存導入、pip check、エンジンAPIのimport、18件のテストが成功しました。
モデル導入後、JVNVの女性2声・男性2声すべてで実際の日本語朗読を生成できました。
`--model jvnv_f1` / `jvnv_f2` / `jvnv_m1` / `jvnv_m2` で切り替えられます。
日本語BERTとOpen JTalk辞書もwork内へ取得済みです。SentencePieceとProtobufをrequirements.txtへ追加しました。
[音声モデル一覧・試聴・商用利用条件](tts/音声モデル一覧.html)、[実音声テスト結果](tts/MODEL_TEST_RESULTS.md)を参照してください。
初期実装時の検証記録はTEST_RESULTS.mdに残しています。Hugging Faceの管理情報もwork/huggingfaceに保持します。
