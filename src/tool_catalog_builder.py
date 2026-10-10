#!/usr/bin/env python3
"""src 内の Python ツール目録を SQLite・テキスト・HTML へ出力する。"""

from __future__ import annotations

import html
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "python_tools.sqlite"
TEXT_PATH = ROOT / "python_tools.txt"
HTML_PATH = ROOT / "index.html"


TOOLS = [
    {
        "tool_name": "ExtGather",
        "japanese_name": "拡張子別ファイル収集ツール",
        "purpose": "指定拡張子のファイルを下層フォルダまで探索し、1つの出力フォルダへ収集する。",
        "usage_example": 'python ExtGather\\ext_gather.py srt "E:\\backup_kenji\\mov" "E:\\backup_kenji\\mov\\srt"',
        "description": "同名ファイルを区別し、コピー元が新しい場合のみ更新。出力フォルダは探索から除外。README.mdにコピー元を記録し、--dry-runで事前確認できる。",
        "entry_file": "ExtGather/ext_gather.py",
        "tool_kind": "コマンドライン",
        "dependencies": "Python 3.9以上（標準ライブラリのみ）",
    },
    {
        "tool_name": "InstaThumbPad",
        "japanese_name": "サムネ余白メーカー",
        "purpose": "元サムネイルを原寸で背景の中央に重ね、横幅に余白のある画像を作る。",
        "usage_example": 'python InstaThumbPad\\insta_thumb_pad.py "InstaThumbPad\\back1.png" "InstaThumbPad\\サムネ45.png" 20',
        "description": "余白率は左右合計の追加割合（％）。背景のみ縦横比を保って伸縮する。出力省略時は元画像名_instapad.png。既存ファイルは上書きしない。",
        "entry_file": "InstaThumbPad/insta_thumb_pad.py",
        "tool_kind": "コマンドライン",
        "dependencies": "Python 3.9以上, Pillow",
    },
    {
        "tool_name": "Time Lapse",
        "japanese_name": "音声付きタイムラプス生成",
        "purpose": "動画と音声を指定倍率で高速化し、H.264/AAC の MP4 として出力する。",
        "usage_example": 'python 21_time_lapse.py "input.mp4" "output.mp4" 4',
        "description": "出力先に空文字を指定した場合は入力名に _b を付ける。倍率が2以下なら音量を半分、2より大きい場合は atempo を2段にして音量を1/10にする。出力FPSは30。",
        "entry_file": "21_time_lapse.py",
        "tool_kind": "コマンドライン",
        "dependencies": "Python 3, ffmpeg-python, FFmpeg",
    },
    {
        "tool_name": "Time Lapse Ex",
        "japanese_name": "無音タイムラプス生成",
        "purpose": "動画を指定倍率で高速化し、元音声を除去して動画長に合う無音音声を付ける。",
        "usage_example": 'python 22_time_lapse_ex.py "input.mp4" "output.mp4" 8',
        "description": "作業ディレクトリに一時ファイル temp_time_lapse.mp4、temp_video.mp4、silent_temp.mp3 を作成し、終了時に削除する。出力FPSは30。",
        "entry_file": "22_time_lapse_ex.py",
        "tool_kind": "コマンドライン",
        "dependencies": "Python 3, ffmpeg-python, pydub, FFmpeg",
    },
    {
        "tool_name": "Directory List",
        "japanese_name": "ディレクトリ構造一覧",
        "purpose": "指定ディレクトリのフォルダ・ファイル構造をツリー形式で標準出力へ表示する。",
        "usage_example": 'python dir_list.py "C:\\Users\\user\\git\\amravie\\src" 3',
        "description": "第2引数は表示する階層数で、省略時は2階層。名前順に表示し、アクセス拒否の場所はその旨を表示する。",
        "entry_file": "dir_list.py",
        "tool_kind": "コマンドライン",
        "dependencies": "Python 3（標準ライブラリのみ）",
    },
    {
        "tool_name": "File Rename",
        "japanese_name": "ファイル更新日付き一括リネーム",
        "purpose": "設定ファイルで指定したフォルダ内の各ファイル名の先頭に更新日を付け、一括変更する。",
        "usage_example": "file_rename.txt の target_dir を設定し、src で python file_rename.py",
        "description": "更新日は yy_mmdd 形式。拡張子を問わずフォルダ直下の全項目を処理するため、実行前に対象フォルダを必ず確認すること。既に日付が付いた名前も再実行すると再度変更される。",
        "entry_file": "file_rename.py",
        "tool_kind": "設定ファイル型コマンドライン",
        "dependencies": "Python 3, vendor.CrudBase.ConfigX, file_rename.txt",
    },
    {
        "tool_name": "Scene Timestamp",
        "japanese_name": "動画シーン時刻検出",
        "purpose": "MP4 の画面色差からハードカットを検出し、各シーンの開始・終了・長さを CSV または JSON に出力する。",
        "usage_example": 'python scene_timestamp.py "input.mp4" --format csv --threshold 0.12 --min-scene 3',
        "description": "既定では0.2秒間隔で比較し、色差閾値0.12、最短シーン3秒。-o を省略すると入力名_scenes.csv/json を入力動画と同じ場所へ作る。検出が少ない場合は --threshold を下げる。",
        "entry_file": "scene_timestamp.py",
        "tool_kind": "コマンドライン",
        "dependencies": "Python 3, OpenCV (cv2), NumPy",
    },
    {
        "tool_name": "ClipNormalizer",
        "japanese_name": "動画クリップ正規化",
        "purpose": "MP4素材を、後で安全に連結しやすい同一解像度・CFR・ゼロ開始PTSの形式へ変換する。",
        "usage_example": 'python ClipNormalizer\\clip_normalizer.py "input.mp4" "normalized.mp4" --fps 30 --width 1920 --height 1080',
        "description": "既定は1920x1080、30fps、H.264/libx264、AAC 48kHz、CRF 18。縦横比を維持して黒帯で埋め、変換後にコーデック、寸法、FPS、開始時刻、音声を検証する。幅と高さは偶数が必要。",
        "entry_file": "ClipNormalizer/clip_normalizer.py",
        "tool_kind": "コマンドライン",
        "dependencies": "Python 3, FFmpeg, ffprobe",
    },
    {
        "tool_name": "ClipNormalizer Batch",
        "japanese_name": "動画クリップ一括正規化",
        "purpose": "ディレクトリ内の MP4 をまとめて ClipNormalizer と同じ連結向け形式へ正規化する。",
        "usage_example": 'python ClipNormalizer\\clip_normalizer_batch.py "input_folder" "output_folder" --recursive --overwrite',
        "description": "出力先省略時は入力フォルダ名_normalizedを作る。--recursive でサブフォルダも処理し、相対構造を維持する。既存出力は --overwrite がなければスキップし、各ファイルを検証後に確定する。",
        "entry_file": "ClipNormalizer/clip_normalizer_batch.py",
        "tool_kind": "コマンドライン",
        "dependencies": "Python 3, clip_normalizer.py, FFmpeg, ffprobe",
    },
    {
        "tool_name": "ClipJoiner",
        "japanese_name": "正規化済み動画連結",
        "purpose": "形式が揃った複数の MP4 を並べ替え、映像を再エンコードせず1本に連結する。",
        "usage_example": 'python clip_joiner\\clip_joiner.py "input_folder" "joined.mp4" --sort name --overwrite',
        "description": "名前・更新日時・作成日時で並べ替え可能。形式の互換性を事前確認し、完成動画と同じベース名の SQLite とテキストレポートも作る。通常は音声もcopy、問題時は --audio-codec ac3。出力省略時は入力フォルダの親へフォルダ名.mp4を作る。",
        "entry_file": "clip_joiner/clip_joiner.py",
        "tool_kind": "コマンドライン",
        "dependencies": "Python 3, FFmpeg, ffprobe",
    },
    {
        "tool_name": "Video Scene Cutter",
        "japanese_name": "動画シーン切り出し",
        "purpose": "MP4 から開始・終了タイムスタンプで指定した範囲を映像・音声付きで切り出す。",
        "usage_example": 'python video_scene_cutter\\video_scene_cutter.py "input.mp4" "00:03:41,338" "00:03:47,300" -o "scene.mp4"',
        "description": "時刻形式は HH:MM:SS,mmm（小数点も可）。出力省略時は入力動画と同じ場所に自動命名する。H.264 CRF 18/AAC 192kbpsで再エンコードし、既存ファイルの上書きには --overwrite が必要。",
        "entry_file": "video_scene_cutter/video_scene_cutter.py",
        "tool_kind": "コマンドライン",
        "dependencies": "Python 3.9.5以上, FFmpeg",
    },
]


def file_updated(relative_path: str) -> str:
    stamp = (ROOT / relative_path).stat().st_mtime
    return datetime.fromtimestamp(stamp).astimezone().isoformat(timespec="seconds")


def build_database() -> None:
    DB_PATH.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.executescript("""
            CREATE TABLE tools (
                id INTEGER PRIMARY KEY,
                tool_name TEXT NOT NULL,
                japanese_name TEXT,
                purpose TEXT NOT NULL,
                usage_example TEXT NOT NULL,
                description TEXT NOT NULL,
                entry_file TEXT NOT NULL UNIQUE,
                tool_kind TEXT NOT NULL,
                dependencies TEXT NOT NULL,
                last_updated TEXT NOT NULL
            );
            CREATE TABLE catalog_info (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE INDEX idx_tools_name ON tools(tool_name);
            CREATE INDEX idx_tools_updated ON tools(last_updated);
        """)
        rows = [dict(item, last_updated=file_updated(item["entry_file"])) for item in TOOLS]
        db.executemany("""
            INSERT INTO tools (
                tool_name, japanese_name, purpose, usage_example, description,
                entry_file, tool_kind, dependencies, last_updated
            ) VALUES (
                :tool_name, :japanese_name, :purpose, :usage_example, :description,
                :entry_file, :tool_kind, :dependencies, :last_updated
            )
        """, rows)
        db.executemany("INSERT INTO catalog_info(key, value) VALUES (?, ?)", [
            ("title", "Pythonツール一覧"),
            ("generated_at", datetime.now().astimezone().isoformat(timespec="seconds")),
            ("source_directory", str(ROOT)),
            ("excluded", "vendor, build, dist, 未使用, __pycache__, テストコード, model内の直接実行できない内部クラス"),
        ])


def read_rows() -> list[sqlite3.Row]:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        return db.execute("SELECT * FROM tools ORDER BY CASE WHEN tool_name = 'ExtGather' THEN 0 WHEN tool_name = 'InstaThumbPad' THEN 1 ELSE 2 END, tool_name COLLATE NOCASE").fetchall()


def build_text(rows: list[sqlite3.Row]) -> None:
    lines = ["Pythonツール一覧", "=" * 72, f"収録数: {len(rows)}", ""]
    for index, row in enumerate(rows, 1):
        lines.extend([
            f"[{index}] {row['tool_name']}（{row['japanese_name']}）",
            f"目的: {row['purpose']}",
            f"使用例: {row['usage_example']}",
            f"説明: {row['description']}",
            f"入口: {row['entry_file']}",
            f"種別: {row['tool_kind']}",
            f"依存: {row['dependencies']}",
            f"最終更新日: {row['last_updated']}",
            "-" * 72,
        ])
    TEXT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def build_html(rows: list[sqlite3.Row]) -> None:
    cards = []
    for row in rows:
        search = " ".join(str(row[key]) for key in row.keys()).casefold()
        help_paths = {"ExtGather": "ExtGather/使い方.html", "InstaThumbPad": "InstaThumbPad/使い方.html"}
        help_path = help_paths.get(row['tool_name'])
        help_link = f'<p><a href="{help_path}">使い方（HTML）</a></p>' if help_path else ''
        cards.append(f"""
        <article class="card" data-search="{html.escape(search, quote=True)}">
          <div class="card-head"><div><h2>{html.escape(row['tool_name'])}</h2><p class="ja">{html.escape(row['japanese_name'] or '')}</p></div><span class="kind">{html.escape(row['tool_kind'])}</span></div>
          <p class="purpose">{html.escape(row['purpose'])}</p>
          {help_link}
          <dl>
            <dt>使用例</dt><dd><code>{html.escape(row['usage_example'])}</code></dd>
            <dt>その他説明</dt><dd>{html.escape(row['description'])}</dd>
            <dt>実行ファイル</dt><dd><code>{html.escape(row['entry_file'])}</code></dd>
            <dt>必要なもの</dt><dd>{html.escape(row['dependencies'])}</dd>
            <dt>最終更新日</dt><dd>{html.escape(row['last_updated'])}</dd>
          </dl>
        </article>""")
    page = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pythonツール一覧</title>
<style>
:root{{--ink:#18212b;--muted:#64717d;--paper:#f4f1e9;--card:#fffdf8;--accent:#176b67;--line:#d9d4c8}}
*{{box-sizing:border-box}} body{{margin:0;color:var(--ink);background:var(--paper);font-family:"Yu Gothic UI","Noto Sans JP",sans-serif;line-height:1.7}}
header{{background:linear-gradient(120deg,#123f45,#176b67);color:white;padding:54px max(5vw,24px) 42px}} .eyebrow{{letter-spacing:.14em;opacity:.72;font-size:.82rem}}
h1{{font-size:clamp(2rem,5vw,3.4rem);margin:.1em 0}} header p{{max-width:720px;margin:0;opacity:.86}} main{{width:min(1120px,90vw);margin:28px auto 64px}}
.toolbar{{display:flex;gap:14px;align-items:center;margin-bottom:22px}} input{{width:100%;padding:14px 16px;border:1px solid var(--line);border-radius:10px;background:white;font-size:1rem}}
#count{{white-space:nowrap;color:var(--muted)}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:18px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:15px;padding:23px;box-shadow:0 7px 24px #27343a0b}} .card-head{{display:flex;justify-content:space-between;gap:16px;align-items:start}}
h2{{margin:0;font-size:1.35rem}} .ja{{margin:0;color:var(--accent);font-weight:700}} .kind{{background:#dcece8;color:#165653;padding:3px 9px;border-radius:99px;font-size:.76rem;white-space:nowrap}}
.purpose{{font-size:1.04rem}} dl{{margin:0}} dt{{font-size:.78rem;font-weight:700;color:var(--muted);margin-top:12px}} dd{{margin:1px 0 0}} code{{background:#edeae2;border-radius:5px;padding:2px 5px;overflow-wrap:anywhere}}
.hidden{{display:none}} footer{{text-align:center;color:var(--muted);padding:0 20px 35px;font-size:.85rem}} @media(max-width:520px){{.grid{{grid-template-columns:1fr}}.card-head{{display:block}}.kind{{display:inline-block;margin-top:8px}}}}
</style></head><body>
<header><div class="eyebrow">AMRAVIE / TOOL CATALOG</div><h1>Pythonツール一覧</h1><p>src 配下にある実行可能な Python ツールの目的、使い方、注意点をまとめた一覧です。データの正本は python_tools.sqlite です。</p></header>
<main><div class="toolbar"><input id="search" type="search" placeholder="名前、目的、ファイル名などで検索…" autofocus><span id="count">{len(rows)} 件</span></div><section class="grid">{''.join(cards)}</section></main>
<footer>SQLiteから生成 / 最終更新日は各実行ファイルのファイル更新日時</footer>
<script>const q=document.querySelector('#search'),cards=[...document.querySelectorAll('.card')],count=document.querySelector('#count');q.addEventListener('input',()=>{{const s=q.value.trim().toLocaleLowerCase();let n=0;cards.forEach(c=>{{const show=c.dataset.search.includes(s);c.classList.toggle('hidden',!show);if(show)n++}});count.textContent=n+' 件'}});</script>
</body></html>"""
    HTML_PATH.write_text(page, encoding="utf-8")


def main() -> None:
    build_database()
    rows = read_rows()
    build_text(rows)
    build_html(rows)
    print(f"作成完了: {DB_PATH.name}, {TEXT_PATH.name}, {HTML_PATH.name} ({len(rows)}件)")


if __name__ == "__main__":
    main()
