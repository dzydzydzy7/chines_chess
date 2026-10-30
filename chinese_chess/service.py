from __future__ import annotations

from typing import Any, Dict, List, Optional

from .rules import IllegalMoveError, Move, PieceType, Point, Position, Side


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
    def __init__(self) -> None:
        self._position = Position.initial()
        self._captured: List[Optional[str]] = []

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
        return self.state()

    def legal_targets(self, source: int) -> List[int]:
        try:
            point = Point.from_index(source)
        except ValueError as error:
            raise ServiceError(str(error)) from error
        return [target.index for target in self._position.legal_targets(point)]

    def reset(self) -> Dict[str, Any]:
        self._position = Position.initial()
        self._captured.clear()
        return self.state()
