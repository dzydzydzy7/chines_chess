from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping


class GameStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._path(str(record["id"]))
        if path.exists():
            previous = self.load(str(record["id"]))
            comparable = dict(previous)
            comparable.pop("saved_at", None)
            candidate = dict(record)
            candidate.pop("saved_at", None)
            if comparable == candidate:
                return previous
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return dict(record)

    def load(self, game_id: str) -> Dict[str, Any]:
        path = self._path(game_id)
        if not path.is_file():
            raise ValueError("game not found: %s" % game_id)
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("invalid saved game")
        return record

    def list(self) -> List[Dict[str, Any]]:
        if not self._directory.exists():
            return []
        summaries = []
        for path in self._directory.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                summaries.append({
                    "id": record["id"],
                    "created_at": record["created_at"],
                    "saved_at": record["saved_at"],
                    "status": record["status"],
                    "move_count": len(record["history"]),
                })
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                continue
        return sorted(summaries, key=lambda item: item["saved_at"], reverse=True)

    def _path(self, game_id: str) -> Path:
        if not game_id or any(character not in "0123456789abcdef" for character in game_id):
            raise ValueError("invalid game id")
        return self._directory / (game_id + ".json")
