# SubVoice 検証結果

実施日: 2026-10-17（日本時間）
環境: Windows x64 / CPython 3.9.5 / SubVoice専用 .venv

追記: モデル導入後、JVNVの4声すべてで実音声生成に成功しました。以下は初期実装時の記録です。
現在のモデル導入・実音声の検証結果は [モデル検証結果](tts/MODEL_TEST_RESULTS.md) を参照してください。

## 自動テスト

`.venv\Scripts\python.exe -m unittest discover -s tests -v`

**18件成功、失敗0件、スキップ0件（8.562秒）。**
詳細ログ: work/test-output.txt（作業用・Git管理対象外）。

| 確認項目 | 結果 |
|---|---|
| SRT解析・時刻の秒変換・複数行・装飾除去・読み置換 | 成功 |
| 不正SRTの拒否・空本文の処理 | 成功 |
| 開始位置固定・冒頭無音・字幕間無音 | 成功（検証信号） |
| 字幕終了時刻を超えても速度1.0を維持 | 成功（検証Engine） |
| 重複ミックス・ログ・音割れ防止 | 成功（検証信号） |
| avoidの最大加速倍率 | 成功（1.15倍まで） |
| WAV・クレジットTXT・ログ生成・作業ファイル削除 | 成功（CLI、Engineのみ差替え） |
| 入力と同じフォルダへの出力・既存ファイル回避 | 成功 |
| 日本語パス・Windowsドライブパス | 成功 |
| 一部字幕の生成失敗後に後続を処理 | 成功（意図した失敗を注入） |
| モデル不足時の終了コード1・ログ・空WAV削除 | 成功 |
| モデルなしでの解析のみ実行 | 成功 |
| JSON設定とCLI優先・設定値検証 | 成功 |
| スタイル一覧・UNKNOWNクレジット | 成功 |
| エンジンへの速度・ピッチ引数とPCM変換 | 成功（inferをMock化） |
| 異なるサンプルレートの変換 | 成功 |

## 指定実データ

`E:\backup_kenji\mov\n175\n175.srt`

- 正常に105件を解析。
- 最初の開始: 0.500秒。最後の開始: 686.263秒。
- --analyze-onlyのCLI実行: 成功。
- 全105件に検証用Engineの信号を配置し、統合WAVを書き出すテスト: 成功。
- 検証用信号のWAVはテスト用一時領域に作成・削除。入力フォルダには試験音声を置いていません。
- 検証信号はStyle-Bert-VITS2による朗読ではありません。

## 実音声の未検証事項

利用可能なsafetensors/config.json/style_vectors.npyのモデル一式を確認範囲で発見できませんでした。
確認範囲: C:/tts、作業リポジトリ、C:/Users/user/git/python。
ユーザーホーム全体や全ドライブの網羅的なモデル探索は行っていません。
日本語BERTも実際の音声生成用には未取得です。

そのため、日本語音声合成・モデル固有のスタイル・朗読品質・CPU推論速度の実測は未実施です。
実音声を生成するには、利用条件を確認済みの音声モデル一式と、初回BERT/辞書取得可能な接続（または取得済みデータ）が必要です。

```powershell
.venv\Scripts\python.exe subvoice.py "E:\backup_kenji\mov\n175\n175.srt" --model "C:\tts\models\voice"
```

モデルのライセンスと必要クレジットをmodel_profiles.jsonへ登録してください。
不明な場合はUNKNOWNと記録し、利用条件の確認を促します。

## ドキュメント

HTMLヘルプのローカルリンク先、オプション一覧の挿入、src/index.htmlの先頭リンクを検査: 成功。
外部サーバー・外部CSSを必要としません。

## 依存ライブラリ導入

Python 3.9.5 x64の専用仮想環境に `pip install -r requirements.txt` を実行し、導入成功。
`pip check`: `No broken requirements found.`

確認済みの主要バージョン:
- style-bert-vits2 2.5.0
- torch 2.3.1
- transformers 4.41.2
- numpy 1.26.4
- scipy 1.13.1
- soundfile 0.12.1

導入レポートはwork/install-report.jsonに保存（作業用・Git管理対象外）。

## エンジンAPIとCPU起動確認

インストール済みStyle-Bert-VITS2 2.5.0のTTSModel、infer、bert_models.load_modelを実際にimportし、必要な引数を検査: 成功。
torch 2.3.1+cpuの読み込み: 成功。これは実音声モデルによる推論テストではありません。
Transformers初期化前にwork内へキャッシュ既定値を設定し、書込先警告が出ないことを確認しました。
キャッシュ先と既存の明示的環境設定を尊重するテストも成功しています。
