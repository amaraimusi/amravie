import json
from pathlib import Path


class ModelManager:
    def __init__(self, model, profiles):
        profiles = Path(profiles)
        registry = (
            json.loads(profiles.read_text(encoding="utf-8-sig"))
            if profiles.exists()
            else {}
        )
        self.metadata = dict(registry.get(model, {}))
        raw = self.metadata.get("path", model)
        if not raw:
            raise ValueError("--model または設定ファイルにモデルを指定してください")
        path = Path(raw).expanduser()
        if model in registry and not path.is_absolute():
            path = profiles.parent / path
        folder = path if path.is_dir() else path.parent
        candidates = sorted(folder.glob("*.safetensors")) if path.is_dir() else [path]
        if len(candidates) != 1:
            raise ValueError("safetensorsが複数または未検出です。ファイルを直接指定してください: " + str(path))
        self.weights = candidates[0]
        self.config = folder / "config.json"
        self.vectors = folder / "style_vectors.npy"
        for f in (self.weights, self.config, self.vectors):
            if not f.is_file():
                raise FileNotFoundError("モデルファイルがありません: " + str(f))
        self.metadata.setdefault("name", folder.name)
        self.metadata["path"] = str(self.weights.resolve())

    def styles(self):
        data = json.loads(self.config.read_text(encoding="utf-8-sig"))["data"]
        return data.get(
            "style2id", {str(i): i for i in range(data.get("num_styles", 1))}
        )
