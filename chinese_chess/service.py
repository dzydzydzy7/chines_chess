from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock, Thread
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from .ai import AlphaBetaEngine, SearchLimits, SearchResult
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


AI_VERSION = "m2.3-alpha-beta-iterative"
DIFFICULTY_DEPTHS = {"easy": 2, "medium": 3, "hard": 5}
DIFFICULTY_NODES = {"easy": 3000, "medium": 40000, "hard": 500000}


class GameService:
    def __init__(
        self,
        store: Optional[GameStore] = None,
        engine_factory: Callable[[], AlphaBetaEngine] = AlphaBetaEngine,
    ) -> None:
        self._store = store
        self._engine_factory = engine_factory
        self._lock = RLock()
        self._generation = 0
        self._ai_engine: Optional[AlphaBetaEngine] = None
        self._mode = "pvp"
        self._player_side = Side.RED
        self._difficulty = "medium"
        self._time_limit_ms = 1000
        self._new_game()

    def _new_game(self) -> None:
        self._position = Position.initial()
        self._captured: List[Optional[str]] = []
        self._moved_pieces: List[str] = []
        self._ai_metadata: List[Optional[Dict[str, Any]]] = []
        self._id = uuid4().hex
        self._created_at = self._now()
        self._saved_at: Optional[str] = None
        self._ai_thinking = False
        self._ai_error: Optional[str] = None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def state(self) -> Dict[str, Any]:
        with self._lock:
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
            for index, (move, captured) in enumerate(zip(self._position.history, self._captured)):
                item = {
                    "from": move.source.index,
                    "to": move.target.index,
                    "piece": self._moved_pieces[index],
                    "captured": captured,
                }
                metadata = self._ai_metadata[index]
                if metadata is not None:
                    item["ai"] = metadata
                history.append(item)
            return {
                "id": self._id,
                "created_at": self._created_at,
                "saved_at": self._saved_at,
                "pieces": pieces,
                "turn": self._position.turn.value,
                "status": self._position.status().value,
                "history": history,
                "mode": self._mode,
                "player_side": self._player_side.value if self._mode == "pve" else None,
                "difficulty": self._difficulty if self._mode == "pve" else None,
                "ai_thinking": self._ai_thinking,
                "ai_error": self._ai_error,
            }

    def move(self, source: int, target: int) -> Dict[str, Any]:
        with self._lock:
            if self._ai_thinking:
                raise ServiceError("AI is thinking")
            if self._mode == "pve" and self._position.turn is not self._player_side:
                raise ServiceError("it is the AI turn")
            self._generation += 1
            self._apply_move(source, target, None)
            self._maybe_start_ai()
            return self.state()

    def _apply_move(self, source: int, target: int, metadata: Optional[Dict[str, Any]]) -> None:
        try:
            move = Move(Point.from_index(source), Point.from_index(target))
            moved_piece = self._position.piece_at(move.source)
            captured_piece = self._position.piece_at(move.target)
            updated = self._position.apply(move)
        except (ValueError, IllegalMoveError) as error:
            raise ServiceError(str(error)) from error
        if moved_piece is None:
            raise ServiceError("move source is empty")
        captured_name = PIECE_NAMES[(captured_piece.side, captured_piece.kind)] if captured_piece else None
        self._position = updated
        self._captured.append(captured_name)
        self._moved_pieces.append(PIECE_NAMES[(moved_piece.side, moved_piece.kind)])
        self._ai_metadata.append(metadata)
        if self._position.status() in (GameStatus.RED_WON, GameStatus.BLACK_WON):
            self.save()

    def undo(self) -> Dict[str, Any]:
        with self._lock:
            if not self._position.history:
                raise ServiceError("nothing to undo")
            was_thinking = self._ai_thinking
            self._cancel_ai()
            count = 1
            if self._mode == "pve" and not was_thinking and len(self._position.history) >= 2:
                if self._ai_metadata[-1] is not None:
                    count = 2
            self._restore_moves(
                self._position.history[:-count],
                self._ai_metadata[:-count],
            )
            self._saved_at = None
            self._maybe_start_ai()
            return self.state()

    def save(self) -> Dict[str, Any]:
        with self._lock:
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
        with self._lock:
            self._cancel_ai()
            self._restore_record(record)
            self._maybe_start_ai()
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
        replay._restore_moves(replay._position.history[:ply], replay._ai_metadata[:ply])
        state = replay.state()
        state["replay_ply"] = ply
        state["replay_length"] = len(history)
        return state

    def _restore_record(self, record: Dict[str, Any]) -> None:
        self._id = record["id"]
        self._created_at = record["created_at"]
        self._saved_at = record["saved_at"]
        self._mode = record.get("mode", "pvp")
        self._player_side = Side(record.get("player_side") or Side.RED.value)
        self._difficulty = record.get("difficulty") or "medium"
        self._time_limit_ms = record.get("time_limit_ms", 1000)
        moves = tuple(
            Move(Point.from_index(item["from"]), Point.from_index(item["to"]))
            for item in record["history"]
        )
        metadata = [item.get("ai") for item in record["history"]]
        self._restore_moves(moves, metadata)

    def _restore_moves(self, moves: Any, metadata: Any = None) -> None:
        position = Position.initial()
        captured: List[Optional[str]] = []
        moved_pieces: List[str] = []
        for move in moves:
            moved_piece = position.piece_at(move.source)
            captured_piece = position.piece_at(move.target)
            if moved_piece is None:
                raise ValueError("saved game has an empty move source")
            moved_pieces.append(PIECE_NAMES[(moved_piece.side, moved_piece.kind)])
            captured.append(PIECE_NAMES[(captured_piece.side, captured_piece.kind)] if captured_piece else None)
            position = position.apply(move)
        self._position = position
        self._captured = captured
        self._moved_pieces = moved_pieces
        self._ai_metadata = list(metadata) if metadata is not None else [None] * len(position.history)
        self._ai_thinking = False
        self._ai_error = None

    def legal_targets(self, source: int) -> List[int]:
        with self._lock:
            try:
                point = Point.from_index(source)
            except ValueError as error:
                raise ServiceError(str(error)) from error
            return [target.index for target in self._position.legal_targets(point)]

    def reset(self) -> Dict[str, Any]:
        with self._lock:
            self._cancel_ai()
            self._mode = "pvp"
            self._new_game()
            return self.state()

    def start_pve(self, player_side: str, difficulty: str, time_limit_ms: int) -> Dict[str, Any]:
        if player_side not in (Side.RED.value, Side.BLACK.value):
            raise ServiceError("player_side must be red or black")
        if difficulty not in DIFFICULTY_DEPTHS:
            raise ServiceError("difficulty must be easy, medium or hard")
        if type(time_limit_ms) is not int or not 1 <= time_limit_ms <= 60000:
            raise ServiceError("time_limit_ms must be between 1 and 60000")
        with self._lock:
            self._cancel_ai()
            self._mode = "pve"
            self._player_side = Side(player_side)
            self._difficulty = difficulty
            self._time_limit_ms = time_limit_ms
            self._new_game()
            self._maybe_start_ai()
            return self.state()

    def close(self) -> None:
        with self._lock:
            self._cancel_ai()

    def _cancel_ai(self) -> None:
        self._generation += 1
        if self._ai_engine is not None:
            self._ai_engine.stop()
        self._ai_engine = None
        self._ai_thinking = False

    def _maybe_start_ai(self) -> None:
        if self._mode != "pve" or self._ai_thinking or self._position.turn is self._player_side:
            return
        if self._position.status() in (GameStatus.RED_WON, GameStatus.BLACK_WON):
            return
        engine = self._engine_factory()
        limits = SearchLimits(
            max_depth=DIFFICULTY_DEPTHS[self._difficulty],
            max_nodes=DIFFICULTY_NODES[self._difficulty],
            time_limit_ms=self._time_limit_ms,
        )
        token = self._generation
        position = self._position
        self._ai_engine = engine
        self._ai_thinking = True
        self._ai_error = None
        thread = Thread(target=self._run_ai, args=(token, position, engine, limits), daemon=True)
        thread.start()

    def _run_ai(
        self,
        token: int,
        position: Position,
        engine: AlphaBetaEngine,
        limits: SearchLimits,
    ) -> None:
        try:
            result = engine.choose_move(position, limits)
            self._commit_ai(token, position, result)
        except Exception as error:
            self._fail_ai(token, str(error))

    def _commit_ai(self, token: int, position: Position, result: SearchResult) -> None:
        with self._lock:
            if token != self._generation or position != self._position or not self._ai_thinking:
                return
            move = result.best_move
            if move is None or move not in position.legal_moves():
                self._fail_ai(token, "AI did not return a legal move")
                return
            metadata = self._search_metadata(result)
            self._generation += 1
            self._ai_thinking = False
            self._ai_engine = None
            self._apply_move(move.source.index, move.target.index, metadata)

    def _fail_ai(self, token: int, message: str) -> None:
        with self._lock:
            if token != self._generation:
                return
            self._ai_thinking = False
            self._ai_engine = None
            self._ai_error = message

    def _search_metadata(self, result: SearchResult) -> Dict[str, Any]:
        return {
            "version": AI_VERSION,
            "difficulty": self._difficulty,
            "limits": {
                "max_depth": DIFFICULTY_DEPTHS[self._difficulty],
                "max_nodes": DIFFICULTY_NODES[self._difficulty],
                "time_limit_ms": self._time_limit_ms,
            },
            "score": result.score,
            "completed_depth": result.completed_depth,
            "nodes": result.nodes,
            "elapsed_ms": result.elapsed_ms,
            "outcome": result.outcome.value,
            "principal_variation": [
                {"from": move.source.index, "to": move.target.index}
                for move in result.principal_variation
            ],
        }
