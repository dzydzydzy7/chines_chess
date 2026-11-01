from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .game_store import GameStore
from .rules import GameStatus, IllegalMoveError, Move, PieceType, Point, Position, Side


class ServiceError(ValueError):
    pass


PIECE_NAMES = {
    (Side.RED, PieceType.KING): "帅",
    (Side.RED, PieceType.ADVISOR): "仕",
    (Side.RED, PieceType.ELEPHANT): "相",
    (Side.RED, PieceType.HORSE): "马",
    (Side.RED, PieceType.ROOK): "车",
    (Side.RED, PieceType.CANNON): "炮",
    (Side.RED, PieceType.PAWN): "兵",
    (Side.BLACK, PieceType.KING): "将",
    (Side.BLACK, PieceType.ADVISOR): "士",
    (Side.BLACK, PieceType.ELEPHANT): "象",
    (Side.BLACK, PieceType.HORSE): "马",
    (Side.BLACK, PieceType.ROOK): "车",
    (Side.BLACK, PieceType.CANNON): "炮",
    (Side.BLACK, PieceType.PAWN): "卒",
}


class GameService:
    def __init__(self, store: Optional[GameStore] = None) -> None:
        self._store = store
        self._new_game()

    def _new_game(self) -> None:
        self._position = Position.initial()
        self._captured: List[Optional[str]] = []
        self._id = uuid4().hex
        self._created_at = self._now()
        self._saved_at: Optional[str] = None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def state(self) -> Dict[str, Any]:
        pieces: List[Dict[str, Any]] = []
        for index, piece in enumerate(self._position.board):
            if piece is not None:
                pieces.append({
                    "square": index,
                    "side": piece.side.value,
                    "kind": piece.kind.value,
                    "name": PIECE_NAMES[(piece.side, piece.kind)],
                })
        history = []
        for move, captured in zip(self._position.history, self._captured):
            history.append({"from": move.source.index, "to": move.target.index, "captured": captured})
        return {
            "id": self._id,
            "created_at": self._created_at,
            "saved_at": self._saved_at,
            "pieces": pieces,
            "turn": self._position.turn.value,
            "status": self._position.status().value,
            "history": history,
        }

    def move(self, source: int, target: int) -> Dict[str, Any]:
        try:
            move = Move(Point.from_index(source), Point.from_index(target))
            captured_piece = self._position.piece_at(move.target)
            updated = self._position.apply(move)
        except (ValueError, IllegalMoveError) as error:
            raise ServiceError(str(error)) from error
        captured_name = PIECE_NAMES[(captured_piece.side, captured_piece.kind)] if captured_piece else None
        self._position = updated
        self._captured.append(captured_name)
        if self._position.status() in (GameStatus.RED_WON, GameStatus.BLACK_WON):
            return self.save()
        return self.state()

    def undo(self) -> Dict[str, Any]:
        if not self._position.history:
            raise ServiceError("nothing to undo")
        self._restore_moves(self._position.history[:-1])
        self._saved_at = None
        return self.state()

    def save(self) -> Dict[str, Any]:
        state = self.state()
        if self._store is None:
            raise ServiceError("game storage is not configured")
        previous_saved_at = self._saved_at
        self._saved_at = self._now()
        state["saved_at"] = self._saved_at
        saved = self._store.save(state)
        self._saved_at = saved["saved_at"]
        if self._saved_at == previous_saved_at:
            return state
        return self.state()

    def list_games(self) -> List[Dict[str, Any]]:
        if self._store is None:
            return []
        return self._store.list()

    def restore(self, game_id: str) -> Dict[str, Any]:
        if self._store is None:
            raise ServiceError("game storage is not configured")
        record = self._store.load(game_id)
        self._restore_record(record)
        return self.state()

    def replay(self, game_id: str, ply: int) -> Dict[str, Any]:
        if self._store is None:
            raise ServiceError("game storage is not configured")
        record = self._store.load(game_id)
        history = record["history"]
        if type(ply) is not int or not 0 <= ply <= len(history):
            raise ValueError("replay ply is outside the game")
        replay = GameService()
        replay._restore_record(record)
        replay._restore_moves(replay._position.history[:ply])
        state = replay.state()
        state["replay_ply"] = ply
        state["replay_length"] = len(history)
        return state

    def _restore_record(self, record: Dict[str, Any]) -> None:
        self._id = record["id"]
        self._created_at = record["created_at"]
        self._saved_at = record["saved_at"]
        moves = tuple(
            Move(Point.from_index(item["from"]), Point.from_index(item["to"]))
            for item in record["history"]
        )
        self._restore_moves(moves)

    def _restore_moves(self, moves: Any) -> None:
        position = Position.initial()
        captured: List[Optional[str]] = []
        for move in moves:
            captured_piece = position.piece_at(move.target)
            captured.append(PIECE_NAMES[(captured_piece.side, captured_piece.kind)] if captured_piece else None)
            position = position.apply(move)
        self._position = position
        self._captured = captured

    def legal_targets(self, source: int) -> List[int]:
        try:
            point = Point.from_index(source)
        except ValueError as error:
            raise ServiceError(str(error)) from error
        return [target.index for target in self._position.legal_targets(point)]

    def reset(self) -> Dict[str, Any]:
        self._new_game()
        return self.state()
