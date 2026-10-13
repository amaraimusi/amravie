import hashlib
import os
import shutil
import time
import uuid
from .verification import fingerprint, digest, safe_path, is_link
from .resume import verified_prefix
from .state_manager import atomic_json, read_json


class ConflictError(Exception):
    pass


class Transfer:
    def __init__(self, source, destination, state, options, stop, progress, logger):
        self.source, self.destination, self.state = source, destination, state
        self.options, self.stop, self.progress, self.logger = options, stop, progress, logger
        self.meta = destination / ".naskeeper"

    def paths(self, rel):
        key = hashlib.sha256(rel.encode("utf-8")).hexdigest()
        return (safe_path(self.destination, rel), self.meta / "temp" / (key + ".part"),
                self.meta / "temp" / (key + ".json"), self.meta / "receipts" / (key + ".json"))

    def process(self, rel):
        src = safe_path(self.source, rel)
        fp = fingerprint(src)
        dst, part, manifest, receipt = self.paths(rel)
        record = read_json(receipt)
        # リカバリー情報の対象パスも検査する。
        known = record.get("relative") == rel and record.get("source_root") == str(self.source)
        if dst.exists():
            st = dst.stat()
            same = st.st_size == fp["size"] and abs(st.st_mtime_ns - fp["mtime"]) <= self.options.mtime_tolerance * 1e9
            if same and (self.options.verify == "size" or digest(src, self.options.buffer_size, self.stop) == digest(dst, self.options.buffer_size, self.stop)):
                if fingerprint(src) != fp:
                    raise OSError("コピー元が差分判定中に変更されました")
                atomic_json(receipt, {"relative": rel, "source_root": str(self.source), "fingerprint": fp,
                                      "sha256": digest(dst, self.options.buffer_size, self.stop),
                                      "completed": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
                self.state.update(rel, fp, "completed", transferred=fp["size"], verified=fp["size"])
                self.progress.credit(fp["size"])
                self.logger.info("SKIPPED %s", rel)
                return "skipped"
            if not known or digest(dst, self.options.buffer_size, self.stop) != record.get("sha256"):
                raise ConflictError("既存ファイルの由来または整合性を確認できないため保留します")
        dst.parent.mkdir(parents=True, exist_ok=True)
        saved = read_json(manifest)
        offset = 0
        if part.exists():
            if is_link(part):
                raise ConflictError("部分ファイルがリンクです")
            if self.options.resume and saved.get("fingerprint") == fp and saved.get("source_root") == str(self.source) and saved.get("relative") == rel:
                offset = verified_prefix(src, part, fp, self.options.buffer_size, self.stop)
        atomic_json(manifest, {"relative": rel, "source_root": str(self.source), "fingerprint": fp})
        self.progress.credit(offset)
        self.state.update(rel, fp, "copying", transferred=offset, verified=offset)
        last_checkpoint = time.monotonic()
        with src.open("rb") as inp, part.open("r+b" if part.exists() else "w+b") as out:
            out.truncate(offset)
            inp.seek(offset)
            out.seek(offset)
            while offset < fp["size"]:
                if self.stop.is_set():
                    out.flush()
                    os.fsync(out.fileno())
                    self.state.update(rel, fp, "interrupted", transferred=offset)
                    raise InterruptedError("中断されました")
                data = inp.read(min(self.options.buffer_size, fp["size"] - offset))
                if not data:
                    raise OSError("コピー元が転送中に短くなりました")
                written = out.write(data)
                if written != len(data):
                    raise OSError("部分書き込みが発生しました")
                offset += written
                self.progress.update(rel, offset, fp["size"], sent=written)
                if time.monotonic() - last_checkpoint >= 5:
                    out.flush()
                    os.fsync(out.fileno())
                    self.state.update(rel, fp, "copying", transferred=offset)
                    last_checkpoint = time.monotonic()
            out.flush()
            os.fsync(out.fileno())
        if fingerprint(src) != fp:
            raise OSError("コピー元が転送中に変更されました")
        if part.stat().st_size != fp["size"]:
            raise OSError("コピー先のサイズが一致しません")
        destination_hash = digest(part, self.options.buffer_size, self.stop)
        if self.options.verify == "hash" and destination_hash != digest(src, self.options.buffer_size, self.stop):
            raise OSError("SHA-256検証に失敗しました")
        if fingerprint(src) != fp:
            raise OSError("コピー元が検証中に変更されました")
        os.utime(str(part), ns=(fp["mtime"], fp["mtime"]))
        # 保存直前にもリンク／競合を検査する。旧正常ファイルは確定まで保持する。
        safe_path(self.destination, rel)
        if dst.exists():
            if not known or digest(dst, self.options.buffer_size, self.stop) != record.get("sha256"):
                raise ConflictError("転送中に既存ファイルが変更されました")
            if self.options.keep_versions:
                version = self.meta / "versions" / (uuid.uuid4().hex + ".bak")
                shutil.copy2(str(dst), str(version))
                if digest(version, self.options.buffer_size, self.stop) != record["sha256"]:
                    raise OSError("旧版の保存検証に失敗しました")
                atomic_json(version.with_suffix(".json"), {"relative": rel, "saved": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        if self.stop.is_set():
            raise InterruptedError("中断されました")
        # 置換後にDBが失われてもNAS上のpending記録と実ファイルから再構築できる。
        pending = receipt.with_suffix(".pending.json")
        new_record = {"relative": rel, "source_root": str(self.source), "fingerprint": fp,
                      "sha256": destination_hash, "completed": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        atomic_json(pending, new_record)
        os.replace(str(part), str(dst))
        atomic_json(receipt, new_record)
        for path in (manifest, pending):
            try:
                path.unlink()
            except OSError:
                pass
        self.state.update(rel, fp, "completed", transferred=offset, verified=offset)
        self.logger.info("COPIED %s (%d bytes)", rel, fp["size"])
        return "copied"

    def recover(self, rel):
        dst, part, manifest, receipt = self.paths(rel)
        pending = receipt.with_suffix(".pending.json")
        record = read_json(pending)
        if record.get("relative") == rel and record.get("source_root") == str(self.source) and dst.is_file():
            if digest(dst, self.options.buffer_size, self.stop) == record.get("sha256"):
                atomic_json(receipt, record)
                pending.unlink()
