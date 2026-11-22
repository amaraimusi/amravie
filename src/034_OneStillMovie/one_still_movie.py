"""MP3と1枚の画像からMP4を生成する。"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


def main():
    parser = argparse.ArgumentParser(description="MP3と1枚の画像からMP4を生成します。")
    parser.add_argument("mp3", type=Path, help="MP3ファイル")
    parser.add_argument("image", type=Path, help="静止画ファイル（PNG、JPEGなど）")
    parser.add_argument("output", nargs="?", type=Path, help="出力MP4ファイル（省略可）")
    args = parser.parse_args()

    mp3 = args.mp3.absolute()
    image = args.image.absolute()
    output = args.output.absolute() if args.output else mp3.with_suffix(".mp4")
    for label, path in (("MP3", mp3), ("画像", image)):
        if not path.is_file():
            parser.error(f"{label}ファイルが見つかりません。{path}")
    if mp3.suffix.lower() != ".mp3":
        parser.error("MP3ファイルの拡張子は .mp3 を指定してください。")
    if output.suffix.lower() != ".mp4":
        parser.error("出力ファイルの拡張子は .mp4 を指定してください。")
    if output.exists() or output.is_symlink():
        parser.error(f"出力先に同名のファイルまたはフォルダがあります。{output}")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        parser.error("FFmpegが見つかりません。ffmpegをPATHに追加してください。")

    try:
        with TemporaryDirectory(prefix=".one-still-movie-", dir=output.parent) as directory:
            temporary_output = Path(directory) / "movie.mp4"
            subprocess.run(
                [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-xerror",
                    "-f", "image2", "-pattern_type", "none",
                    "-framerate", "10", "-i", str(image), "-i", str(mp3),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-vf", "loop=loop=-1:size=1,pad=ceil(iw/2)*2:ceil(ih/2)*2",
                    "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage,zerolatency",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(temporary_output),
                ],
                check=True,
            )
            # 完成した動画だけを公開し、変換中に同名ファイルができても上書きしない。
            if os.name == "nt":
                temporary_output.rename(output)
            else:
                os.link(temporary_output, output)
    except subprocess.CalledProcessError:
        print("FFmpegでの動画生成に失敗しました。", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"動画を保存できませんでした。{error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("動画生成を中断しました。", file=sys.stderr)
        return 130

    print(f"作成しました。{output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
