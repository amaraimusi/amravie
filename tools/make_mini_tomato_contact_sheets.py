import sqlite3
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

DB = Path(r"E:\backup_kenji\mov\n175\mini_tomato_scenes.sqlite")
OUT = Path(r"C:\Users\user\git\amravie\mini_tomato_contact_sheets")
OUT.mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype(r"C:\Windows\Fonts\meiryo.ttc", 18)
small = ImageFont.truetype(r"C:\Windows\Fonts\meiryo.ttc", 14)

with sqlite3.connect(DB) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT scene_id,video_code,video_scene_number,cut_path,actual_duration_seconds,scene_summary FROM mini_tomato_scenes ORDER BY scene_id").fetchall()

cards = []
for row in rows:
    frames = []
    duration = float(row["actual_duration_seconds"])
    for pos, fraction in enumerate((0.12, 0.50, 0.88), 1):
        jpg = OUT / f"scene_{row['scene_id']:03d}_{pos}.jpg"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{duration*fraction:.3f}", "-i", row["cut_path"],
            "-frames:v", "1", "-vf", "scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2:black",
            str(jpg),
        ], check=True)
        frames.append(Image.open(jpg).convert("RGB"))
    card = Image.new("RGB", (1440, 330), "#161616")
    draw = ImageDraw.Draw(card)
    title = f"SCENE {row['scene_id']:03d} | {row['video_code']} #{row['video_scene_number']:02d} | {duration:.1f}s"
    draw.text((12, 7), title, fill="white", font=font)
    summary = row["scene_summary"]
    if len(summary) > 72:
        summary = summary[:72] + "…"
    draw.text((12, 35), summary, fill="#d0d0d0", font=small)
    for i, frame in enumerate(frames):
        card.paste(frame, (i * 480, 60))
    cards.append(card)

for batch_start in range(0, len(cards), 8):
    batch = cards[batch_start:batch_start + 8]
    sheet = Image.new("RGB", (1440, 330 * len(batch)), "black")
    for i, card in enumerate(batch):
        sheet.paste(card, (0, i * 330))
    first = batch_start + 1
    last = batch_start + len(batch)
    path = OUT / f"scenes_{first:03d}_{last:03d}.jpg"
    sheet.save(path, quality=90)
    print(path)
