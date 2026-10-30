from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .config import Config


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._config = self._load()

    def get(self) -> Config:
        return self._config

    def update(self, changes: Mapping[str, Any]) -> Config:
        updated = self._config.updated(changes)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(updated.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self._path)
        self._config = updated
        return updated

    def _load(self) -> Config:
        if not self._path.exists():
            return Config.defaults()
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return Config.defaults().updated(data)
