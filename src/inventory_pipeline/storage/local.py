"""Local filesystem raw storage backend -- the default for development."""

from __future__ import annotations

from pathlib import Path

from inventory_pipeline.storage.base import RawStorage


class LocalRawStorage(RawStorage):
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def _path(self, key: str) -> Path:
        return self.base_dir / key

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def write_text(self, key: str, content: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def read_text(self, key: str) -> str:
        return self._path(key).read_text(encoding="utf-8")

    def list_keys(self, prefix: str) -> list[str]:
        root = self._path(prefix)
        if not root.exists():
            return []
        base = self.base_dir
        return [str(p.relative_to(base)) for p in root.rglob("*") if p.is_file()]
