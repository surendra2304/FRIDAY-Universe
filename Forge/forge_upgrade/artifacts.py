from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    name: str
    path: str
    size_bytes: int
    sha256: str
    content_type: str


class ArtifactManager:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def store(
        self, name: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> ArtifactManifest:
        path = (self.root / name).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.relative_to(self.root)
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        return ArtifactManifest(name, str(path), len(data), digest, content_type)

    def manifest_json(self, artifacts: list[ArtifactManifest]) -> str:
        return json.dumps([a.__dict__ for a in artifacts], indent=2, sort_keys=True)
