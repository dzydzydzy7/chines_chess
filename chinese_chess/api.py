from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any, Dict, Mapping, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .config import ConfigValidationError
from .config_store import ConfigStore
from .game_store import GameStore
from .service import GameService, ServiceError

Response = Tuple[int, Dict[str, Any]]


class Application:
    def __init__(self, config_store: Optional[ConfigStore] = None, game_store: Optional[GameStore] = None) -> None:
        store = GameStore(Path("data/games")) if game_store is None else game_store
        self.game = GameService(store)
        self.config = config_store or ConfigStore(Path("data/settings.json"))
        self._lock = RLock()

    def handle(self, method: str, raw_path: str, payload: Optional[Mapping[str, Any]]) -> Response:
        parsed = urlparse(raw_path)
        try:
            with self._lock:
                return self._dispatch(method, parsed.path, parse_qs(parsed.query), payload)
        except (ServiceError, ConfigValidationError, ValueError, TypeError, KeyError) as error:
            return 422, {"error": str(error)}

    def _dispatch(
        self,
        method: str,
        path: str,
        query: Mapping[str, Any],
        payload: Optional[Mapping[str, Any]],
    ) -> Response:
        if method == "GET" and path == "/api/game":
            return 200, self.game.state()
        if method == "POST" and path == "/api/game/move":
            data = self._payload(payload)
            source = data["from"]
            target = data["to"]
            if type(source) is not int or type(target) is not int:
                raise ServiceError("move squares must be integers")
            return 200, self.game.move(source, target)
        if method == "POST" and path == "/api/game/reset":
            return 200, self.game.reset()
        if method == "POST" and path == "/api/game/undo":
            return 200, self.game.undo()
        if method == "POST" and path == "/api/game/save":
            return 200, self.game.save()
        if method == "GET" and path == "/api/games":
            return 200, {"games": self.game.list_games()}
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "games"]:
            game_id, action = parts[2:]
            if method == "POST" and action == "restore":
                return 200, self.game.restore(game_id)
            if method == "GET" and action == "replay":
                try:
                    ply = int(query.get("ply", ["0"])[0])
                except (ValueError, TypeError) as error:
                    raise ServiceError("ply must be an integer") from error
                return 200, self.game.replay(game_id, ply)
        if method == "GET" and path == "/api/game/legal-moves":
            try:
                source = int(query["from"][0])
            except (KeyError, IndexError, ValueError) as error:
                raise ServiceError("from must be one board square index") from error
            return 200, {"targets": self.game.legal_targets(source)}
        if method == "GET" and path == "/api/config":
            return 200, self.config.get().to_dict()
        if method == "PUT" and path == "/api/config":
            return 200, self.config.update(self._payload(payload)).to_dict()
        return 404, {"error": "API route not found"}

    @staticmethod
    def _payload(payload: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
        if payload is None:
            raise ServiceError("JSON request body is required")
        return payload
