from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from enum import Enum
from threading import Event
from typing import Callable, Optional, Tuple

from .rules import GameStatus, Move, PieceType, Point, Position, Side


@dataclass(frozen=True)
class SearchLimits:
    max_depth: int = 1
    max_nodes: Optional[int] = None
    time_limit_ms: Optional[float] = None

    def validate(self) -> None:
        if type(self.max_depth) is not int or self.max_depth < 1:
            raise ValueError("max_depth must be a positive integer")
        if self.max_nodes is not None and (type(self.max_nodes) is not int or self.max_nodes < 0):
            raise ValueError("max_nodes must be a non-negative integer or None")
        if self.time_limit_ms is not None:
            if isinstance(self.time_limit_ms, bool) or not isinstance(self.time_limit_ms, (int, float)):
                raise ValueError("time_limit_ms must be a non-negative number or None")
            if not math.isfinite(self.time_limit_ms) or self.time_limit_ms < 0:
                raise ValueError("time_limit_ms must be a non-negative number or None")


class SearchOutcome(str, Enum):
    COMPLETED = "completed"
    TERMINAL = "terminal"
    NO_MOVES = "no_moves"
    NODE_LIMIT = "node_limit"
    TIME_LIMIT = "time_limit"
    STOPPED = "stopped"


@dataclass(frozen=True)
class SearchResult:
    best_move: Optional[Move]
    score: Optional[int]
    completed_depth: int
    nodes: int
    elapsed_ms: float
    principal_variation: Tuple[Move, ...]
    outcome: SearchOutcome


PIECE_VALUES = {
    PieceType.KING: 100000,
    PieceType.ROOK: 900,
    PieceType.CANNON: 450,
    PieceType.HORSE: 400,
    PieceType.ADVISOR: 200,
    PieceType.ELEPHANT: 200,
    PieceType.PAWN: 100,
}


class BaselineEngine:
    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self._stop = Event()

    def stop(self) -> None:
        self._stop.set()

    def choose_move(self, position: Position, limits: Optional[SearchLimits] = None) -> SearchResult:
        limits = SearchLimits() if limits is None else limits
        limits.validate()
        self._stop.clear()
        started = self._clock()
        deadline = None if limits.time_limit_ms is None else started + limits.time_limit_ms / 1000.0

        interrupted = self._interrupted(deadline)
        if interrupted is not None:
            return self._result(started, None, None, 0, 0, interrupted)
        if limits.max_nodes == 0:
            return self._result(started, None, None, 0, 0, SearchOutcome.NODE_LIMIT)

        legal_moves = position.legal_moves()
        interrupted = self._interrupted(deadline)
        if interrupted is not None:
            return self._result(started, None, None, 0, 0, interrupted)
        if not legal_moves:
            outcome = (
                SearchOutcome.TERMINAL
                if position.status() in (GameStatus.RED_WON, GameStatus.BLACK_WON)
                else SearchOutcome.NO_MOVES
            )
            return self._result(started, None, None, 0, 0, outcome)
        return self._select(position, legal_moves, limits, started, deadline)

    def _select(
        self,
        position: Position,
        legal_moves: Tuple[Move, ...],
        limits: SearchLimits,
        started: float,
        deadline: Optional[float],
    ) -> SearchResult:
        raise NotImplementedError

    def _interrupted(self, deadline: Optional[float]) -> Optional[SearchOutcome]:
        if self._stop.is_set():
            return SearchOutcome.STOPPED
        if deadline is not None and self._clock() >= deadline:
            return SearchOutcome.TIME_LIMIT
        return None

    def _result(
        self,
        started: float,
        best_move: Optional[Move],
        score: Optional[int],
        completed_depth: int,
        nodes: int,
        outcome: SearchOutcome,
    ) -> SearchResult:
        if outcome is SearchOutcome.STOPPED:
            best_move = None
            score = None
            completed_depth = 0
        return SearchResult(
            best_move=best_move,
            score=score,
            completed_depth=completed_depth,
            nodes=nodes,
            elapsed_ms=max(0.0, (self._clock() - started) * 1000.0),
            principal_variation=() if best_move is None else (best_move,),
            outcome=outcome,
        )


class RandomLegalEngine(BaselineEngine):
    def __init__(
        self,
        seed: Optional[int] = None,
        rng: Optional[random.Random] = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        super().__init__(clock)
        if seed is not None and rng is not None:
            raise ValueError("seed and rng cannot both be provided")
        self._random = random.Random(seed) if rng is None else rng

    def _select(
        self,
        position: Position,
        legal_moves: Tuple[Move, ...],
        limits: SearchLimits,
        started: float,
        deadline: Optional[float],
    ) -> SearchResult:
        move = self._random.choice(legal_moves)
        interrupted = self._interrupted(deadline)
        outcome = SearchOutcome.COMPLETED if interrupted is None else interrupted
        return self._result(started, move, 0, 1, 1, outcome)


class GreedyEngine(BaselineEngine):
    def _select(
        self,
        position: Position,
        legal_moves: Tuple[Move, ...],
        limits: SearchLimits,
        started: float,
        deadline: Optional[float],
    ) -> SearchResult:
        best_move: Optional[Move] = None
        best_score: Optional[int] = None
        nodes = 0
        for move in legal_moves:
            interrupted = self._interrupted(deadline)
            if interrupted is not None:
                return self._result(started, best_move, best_score, 0, nodes, interrupted)
            if limits.max_nodes is not None and nodes >= limits.max_nodes:
                return self._result(started, best_move, best_score, 0, nodes, SearchOutcome.NODE_LIMIT)

            captured = position.piece_at(move.target)
            score = 0 if captured is None else PIECE_VALUES[captured.kind]
            nodes += 1
            if best_score is None or score > best_score:
                best_move = move
                best_score = score

            interrupted = self._interrupted(deadline)
            if interrupted is not None:
                return self._result(started, best_move, best_score, 0, nodes, interrupted)

        return self._result(started, best_move, best_score, 1, nodes, SearchOutcome.COMPLETED)


def _position_table(rows: Tuple[Tuple[int, ...], ...]) -> Tuple[int, ...]:
    return tuple(value for row in rows for value in row)


PAWN_POSITION_VALUES = _position_table((
    (40, 40, 40, 40, 40, 40, 40, 40, 40),
    (35, 35, 35, 35, 35, 35, 35, 35, 35),
    (30, 30, 30, 30, 30, 30, 30, 30, 30),
    (25, 25, 25, 25, 25, 25, 25, 25, 25),
    (20, 20, 20, 20, 20, 20, 20, 20, 20),
    (10, 10, 10, 10, 10, 10, 10, 10, 10),
    (0, 0, 0, 0, 0, 0, 0, 0, 0),
    (0, 0, 0, 0, 0, 0, 0, 0, 0),
    (0, 0, 0, 0, 0, 0, 0, 0, 0),
    (0, 0, 0, 0, 0, 0, 0, 0, 0),
))

HORSE_POSITION_VALUES = tuple(value * 2 for value in _position_table((
    (0, 2, 4, 6, 8, 6, 4, 2, 0),
    (2, 4, 6, 8, 10, 8, 6, 4, 2),
    (4, 6, 8, 10, 12, 10, 8, 6, 4),
    (4, 6, 8, 10, 12, 10, 8, 6, 4),
    (4, 6, 8, 10, 12, 10, 8, 6, 4),
    (4, 6, 8, 10, 12, 10, 8, 6, 4),
    (4, 6, 8, 10, 12, 10, 8, 6, 4),
    (4, 6, 8, 10, 12, 10, 8, 6, 4),
    (2, 4, 6, 8, 10, 8, 6, 4, 2),
    (0, 2, 4, 6, 8, 6, 4, 2, 0),
)))

POSITION_VALUES = {
    PieceType.PAWN: PAWN_POSITION_VALUES,
    PieceType.HORSE: HORSE_POSITION_VALUES,
}


def evaluate_position(position: Position, side: Optional[Side] = None) -> int:
    perspective = position.turn if side is None else side
    red_score = 0
    for index, piece in enumerate(position.board):
        if piece is None:
            continue
        row, col = divmod(index, 9)
        table_index = index if piece.side is Side.RED else (9 - row) * 9 + col
        value = PIECE_VALUES[piece.kind]
        table = POSITION_VALUES.get(piece.kind)
        if table is not None:
            value += table[table_index]
        red_score += value if piece.side is Side.RED else -value
    return red_score if perspective is Side.RED else -red_score


def ordered_moves(position: Position, moves: Tuple[Move, ...]) -> Tuple[Move, ...]:
    def order(move: Move) -> Tuple[int, int, int]:
        captured = position.piece_at(move.target)
        if captured is None:
            return (0, 0, 0)
        mover = position.piece_at(move.source)
        mover_value = 0 if mover is None else PIECE_VALUES[mover.kind]
        return (-1, -PIECE_VALUES[captured.kind], mover_value)

    return tuple(sorted(moves, key=order))


def legal_capture_moves(position: Position) -> Tuple[Move, ...]:
    moves = []
    for index, piece in enumerate(position.board):
        if piece is None or piece.side is not position.turn:
            continue
        source = Point.from_index(index)
        for target in position.pseudo_legal_targets(source):
            if position.piece_at(target) is None:
                continue
            move = Move(source, target)
            if not position._move_unchecked(move).in_check(position.turn):
                moves.append(move)
    return tuple(moves)


MATE_SCORE = 1000000
INFINITE_SCORE = 10000000


class _SearchHalt(Exception):
    def __init__(self, outcome: SearchOutcome) -> None:
        self.outcome = outcome


class _SearchState:
    def __init__(
        self,
        limits: SearchLimits,
        deadline: Optional[float],
        clock: Callable[[], float],
        stop: Event,
    ) -> None:
        self.limits = limits
        self.deadline = deadline
        self.clock = clock
        self.stop = stop
        self.nodes = 0

    def check(self) -> None:
        if self.stop.is_set():
            raise _SearchHalt(SearchOutcome.STOPPED)
        if self.deadline is not None and self.clock() >= self.deadline:
            raise _SearchHalt(SearchOutcome.TIME_LIMIT)
        if self.limits.max_nodes is not None and self.nodes >= self.limits.max_nodes:
            raise _SearchHalt(SearchOutcome.NODE_LIMIT)

    def visit(self) -> None:
        self.check()
        self.nodes += 1


class NegamaxEngine(BaselineEngine):
    _prune = False

    def choose_move(self, position: Position, limits: Optional[SearchLimits] = None) -> SearchResult:
        limits = SearchLimits() if limits is None else limits
        limits.validate()
        self._stop.clear()
        started = self._clock()
        deadline = None if limits.time_limit_ms is None else started + limits.time_limit_ms / 1000.0
        state = _SearchState(limits, deadline, self._clock, self._stop)
        try:
            score, principal_variation = self._search(
                position,
                limits.max_depth,
                0,
                -INFINITE_SCORE,
                INFINITE_SCORE,
                state,
            )
        except _SearchHalt as halt:
            return SearchResult(
                best_move=None,
                score=None,
                completed_depth=0,
                nodes=state.nodes,
                elapsed_ms=max(0.0, (self._clock() - started) * 1000.0),
                principal_variation=(),
                outcome=halt.outcome,
            )

        if principal_variation:
            outcome = SearchOutcome.COMPLETED
            completed_depth = limits.max_depth
        else:
            terminal = position.status() in (GameStatus.RED_WON, GameStatus.BLACK_WON)
            outcome = SearchOutcome.TERMINAL if terminal else SearchOutcome.NO_MOVES
            completed_depth = 0
        return SearchResult(
            best_move=principal_variation[0] if principal_variation else None,
            score=score,
            completed_depth=completed_depth,
            nodes=state.nodes,
            elapsed_ms=max(0.0, (self._clock() - started) * 1000.0),
            principal_variation=principal_variation,
            outcome=outcome,
        )

    def _search(
        self,
        position: Position,
        depth: int,
        ply: int,
        alpha: int,
        beta: int,
        state: _SearchState,
    ) -> Tuple[int, Tuple[Move, ...]]:
        if depth == 0:
            return self._quiescence(position, ply, alpha, beta, state, 4)
        state.visit()
        legal_moves = position.legal_moves()
        if not legal_moves:
            status = position.status()
            if status in (GameStatus.RED_WON, GameStatus.BLACK_WON):
                winner = Side.RED if status is GameStatus.RED_WON else Side.BLACK
                score = MATE_SCORE - ply if winner is position.turn else -MATE_SCORE + ply
                return score, ()
            return -MATE_SCORE + ply, ()

        moves = ordered_moves(position, legal_moves) if self._prune else legal_moves
        best_score = -INFINITE_SCORE
        best_variation: Tuple[Move, ...] = ()
        for move in moves:
            child_score, child_variation = self._search(
                position._move_unchecked(move),
                depth - 1,
                ply + 1,
                -beta,
                -alpha,
                state,
            )
            score = -child_score
            if score > best_score:
                best_score = score
                best_variation = (move,) + child_variation
            if self._prune:
                alpha = max(alpha, score)
                if alpha >= beta:
                    break
        return best_score, best_variation

    def _quiescence(
        self,
        position: Position,
        ply: int,
        alpha: int,
        beta: int,
        state: _SearchState,
        depth: int,
    ) -> Tuple[int, Tuple[Move, ...]]:
        state.visit()
        status = position.status()
        if status in (GameStatus.RED_WON, GameStatus.BLACK_WON):
            winner = Side.RED if status is GameStatus.RED_WON else Side.BLACK
            score = MATE_SCORE - ply if winner is position.turn else -MATE_SCORE + ply
            return score, ()

        in_check = status is GameStatus.CHECK
        best_score = -INFINITE_SCORE if in_check else evaluate_position(position)
        best_variation: Tuple[Move, ...] = ()
        if depth == 0:
            return evaluate_position(position), ()
        if self._prune and not in_check:
            if best_score >= beta:
                return best_score, best_variation
            alpha = max(alpha, best_score)

        legal_moves = position.legal_moves() if in_check else legal_capture_moves(position)
        moves = ordered_moves(position, legal_moves) if self._prune else legal_moves
        for move in moves:
            child_score, child_variation = self._quiescence(
                position._move_unchecked(move),
                ply + 1,
                -beta,
                -alpha,
                state,
                depth - 1,
            )
            score = -child_score
            if score > best_score:
                best_score = score
                best_variation = (move,) + child_variation
            if self._prune:
                alpha = max(alpha, score)
                if alpha >= beta:
                    break
        return best_score, best_variation


class AlphaBetaEngine(NegamaxEngine):
    _prune = True

    def choose_move(self, position: Position, limits: Optional[SearchLimits] = None) -> SearchResult:
        limits = SearchLimits() if limits is None else limits
        limits.validate()
        self._stop.clear()
        started = self._clock()
        deadline = None if limits.time_limit_ms is None else started + limits.time_limit_ms / 1000.0
        state = _SearchState(limits, deadline, self._clock, self._stop)
        completed_depth = 0
        completed_score: Optional[int] = None
        completed_variation: Tuple[Move, ...] = ()
        fallback: Tuple[Move, ...] = ()
        outcome = SearchOutcome.COMPLETED
        try:
            state.check()
            legal_moves = position.legal_moves()
            fallback = ordered_moves(position, legal_moves)[:1]
            for depth in range(1, limits.max_depth + 1):
                score, principal_variation = self._search(
                    position,
                    depth,
                    0,
                    -INFINITE_SCORE,
                    INFINITE_SCORE,
                    state,
                )
                if not principal_variation:
                    terminal = position.status() in (GameStatus.RED_WON, GameStatus.BLACK_WON)
                    outcome = SearchOutcome.TERMINAL if terminal else SearchOutcome.NO_MOVES
                    completed_score = score
                    break
                completed_depth = depth
                completed_score = score
                completed_variation = principal_variation
        except _SearchHalt as halt:
            outcome = halt.outcome
            if completed_depth == 0 and fallback:
                completed_variation = fallback

        return SearchResult(
            best_move=completed_variation[0] if completed_variation else None,
            score=completed_score,
            completed_depth=completed_depth,
            nodes=state.nodes,
            elapsed_ms=max(0.0, (self._clock() - started) * 1000.0),
            principal_variation=completed_variation,
            outcome=outcome,
        )
