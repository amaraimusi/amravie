"""Verify collected real data without modifying any subtitle files."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ext_gather import gather, MANIFEST

source = Path("E:/backup_kenji/mov")
output = source / "srt"
entries = json.loads((output / MANIFEST).read_text(encoding="utf-8"))["files"]
for entry in entries.values():
    origin = Path(entry["source"])
    target = output / entry["name"]
    assert hashlib.sha256(origin.read_bytes()).digest() == hashlib.sha256(target.read_bytes()).digest()
    assert origin.stat().st_mtime_ns == target.stat().st_mtime_ns
    assert output.resolve() not in origin.resolve().parents
with contextlib.redirect_stdout(io.StringIO()):
    counts = gather("srt", source, output)
assert counts == {"copied": 0, "updated": 0, "skipped": len(entries), "errors": 0}, counts
catalog = (Path(__file__).resolve().parents[2] / "index.html").read_text(encoding="utf-8")
assert catalog.index("<h2>ExtGather</h2>") < catalog.index("<h2>InstaThumbPad</h2>")
assert 'href="ExtGather/使い方.html"' in catalog
report = {"verified_files": len(entries), "content_and_timestamps_match": True,
          "second_run": counts, "catalog_first_link_verified": True}
(Path(__file__).parent / "verification.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report))
