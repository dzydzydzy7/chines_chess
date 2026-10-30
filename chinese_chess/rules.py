from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


class Side(str, Enum):
    RED = "red"
    BLACK = "black"

    @property
    def opponent(self) -> "Side":
        return Side.BLACK if self is Side.RED else Side.RED


class PieceType(str, Enum):
    KING = "king"
    ADVISOR = "advisor"
    ELEPHANT = "elephant"
    HORSE = "horse"
    ROOK = "rook"
    CANNON = "cannon"
    PAWN = "pawn"


class GameStatus(str, Enum):
    PLAYING = "playing"
    CHECK = "check"
    RED_WON = "red_won"
    BLACK_WON = "black_won"


@dataclass(frozen=True, order=True)
class Point:
    row: int
    col: int

    def __post_init__(self) -> None:
        if not 0 <= self.row < 10 or not 0 <= self.col < 9:
            raise ValueError("point is outside the board")

    @property
    def index(self) -> int:
        return self.row * 9 + self.col

    @classmethod
    def from_index(cls, index: int) -> "Point":
        if not 0 <= index < 90:
            raise ValueError("index is outside the board")
        return cls(index // 9, index % 9)

    def offset(self, rows: int, cols: int) -> Optional["Point"]:
        row = self.row + rows
        col = self.col + cols
        if 0 <= row < 10 and 0 <= col < 9:
            return Point(row, col)
        return None


@dataclass(frozen=True)
class Piece:
    side: Side
    kind: PieceType


@dataclass(frozen=True)
class Move:
    source: Point
    target: Point


class IllegalMoveError(ValueError):
    pass


Board = Tuple[Optional[Piece], ...]


@dataclass(frozen=True)
class Position:
    board: Board
    turn: Side = Side.RED
    history: Tuple[Move, ...] = ()

    def __post_init__(self) -> None:
        if len(self.board) != 90:
            raise ValueError("board must contain exactly 90 squares")

    @classmethod
    def initial(cls) -> "Position":
        board: List[Optional[Piece]] = [None] * 90
        back_rank = [
            PieceType.ROOK,
            PieceType.HORSE,
            PieceType.ELEPHANT,
            PieceType.ADVISOR,
            PieceType.KING,
            PieceType.ADVISOR,
            PieceType.ELEPHANT,
            PieceType.HORSE,
            PieceType.ROOK,
        ]
        for side, row in ((Side.BLACK, 0), (Side.RED, 9)):
            for col, kind in enumerate(back_rank):
                board[Point(row, col).index] = Piece(side, kind)
            for col in (1, 7):
                board[Point(row + (2 if side is Side.BLACK else -2), col).index] = Piece(side, PieceType.CANNON)
            pawn_row = row + (3 if side is Side.BLACK else -3)
            for col in (0, 2, 4, 6, 8):
                board[Point(pawn_row, col).index] = Piece(side, PieceType.PAWN)
        return cls(tuple(board))

    def piece_at(self, point: Point) -> Optional[Piece]:
        return self.board[point.index]

    def pseudo_legal_targets(self, source: Point) -> Tuple[Point, ...]:
        piece = self.piece_at(source)
        if piece is None:
            return ()
        generators = {
            PieceType.KING: self._king_targets,
            PieceType.ADVISOR: self._advisor_targets,
            PieceType.ELEPHANT: self._elephant_targets,
            PieceType.HORSE: self._horse_targets,
            PieceType.ROOK: self._rook_targets,
            PieceType.CANNON: self._cannon_targets,
            PieceType.PAWN: self._pawn_targets,
        }
        return generators[piece.kind](source, piece)

    def legal_moves(self) -> Tuple[Move, ...]:
        if self.status() in (GameStatus.RED_WON, GameStatus.BLACK_WON):
            return ()
        moves: List[Move] = []
        for index, piece in enumerate(self.board):
            if piece is None or piece.side is not self.turn:
                continue
            source = Point.from_index(index)
            for target in self.pseudo_legal_targets(source):
                move = Move(source, target)
                candidate = self._move_unchecked(move)
                if not candidate.in_check(self.turn):
                    moves.append(move)
        return tuple(moves)

    def legal_targets(self, source: Point) -> Tuple[Point, ...]:
        return tuple(move.target for move in self.legal_moves() if move.source == source)

    def apply(self, move: Move) -> "Position":
        if move not in self.legal_moves():
            raise IllegalMoveError("move is not legal in the current position")
        return self._move_unchecked(move)

    def _move_unchecked(self, move: Move) -> "Position":
        board = list(self.board)
        board[move.target.index] = board[move.source.index]
        board[move.source.index] = None
        return Position(tuple(board), self.turn.opponent, self.history + (move,))

    def status(self) -> GameStatus:
        red_king = self._find_king(Side.RED)
        black_king = self._find_king(Side.BLACK)
        if red_king is None:
            return GameStatus.BLACK_WON
        if black_king is None:
            return GameStatus.RED_WON
        if not self.legal_moves_without_status_check():
            return GameStatus.BLACK_WON if self.turn is Side.RED else GameStatus.RED_WON
        return GameStatus.CHECK if self.in_check(self.turn) else GameStatus.PLAYING

    def legal_moves_without_status_check(self) -> Tuple[Move, ...]:
        moves: List[Move] = []
        for index, piece in enumerate(self.board):
            if piece is None or piece.side is not self.turn:
                continue
            source = Point.from_index(index)
            for target in self.pseudo_legal_targets(source):
                move = Move(source, target)
                if not self._move_unchecked(move).in_check(self.turn):
                    moves.append(move)
        return tuple(moves)

    def in_check(self, side: Side) -> bool:
        king = self._find_king(side)
        if king is None:
            return True
        enemy_king = self._find_king(side.opponent)
        if enemy_king is not None and king.col == enemy_king.col and not self._pieces_between(king, enemy_king):
            return True
        for index, piece in enumerate(self.board):
            if piece is None or piece.side is not side.opponent:
                continue
            if king in self.pseudo_legal_targets(Point.from_index(index)):
                return True
        return False

    def _find_king(self, side: Side) -> Optional[Point]:
        for index, piece in enumerate(self.board):
            if piece == Piece(side, PieceType.KING):
                return Point.from_index(index)
        return None

    def _empty_or_enemy(self, point: Point, side: Side) -> bool:
        piece = self.piece_at(point)
        return piece is None or piece.side is not side

    def _step_targets(self, source: Point, piece: Piece, offsets: Iterable[Tuple[int, int]]) -> Tuple[Point, ...]:
        targets: List[Point] = []
        for rows, cols in offsets:
            target = source.offset(rows, cols)
            if target is not None and self._empty_or_enemy(target, piece.side):
                targets.append(target)
        return tuple(targets)

    def _king_targets(self, source: Point, piece: Piece) -> Tuple[Point, ...]:
        rows = (7, 8, 9) if piece.side is Side.RED else (0, 1, 2)
        return tuple(
            target
            for target in self._step_targets(source, piece, ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if target.row in rows and 3 <= target.col <= 5
        )

    def _advisor_targets(self, source: Point, piece: Piece) -> Tuple[Point, ...]:
        rows = (7, 8, 9) if piece.side is Side.RED else (0, 1, 2)
        return tuple(
            target
            for target in self._step_targets(source, piece, ((1, 1), (1, -1), (-1, 1), (-1, -1)))
            if target.row in rows and 3 <= target.col <= 5
        )

    def _elephant_targets(self, source: Point, piece: Piece) -> Tuple[Point, ...]:
        targets: List[Point] = []
        for rows, cols in ((2, 2), (2, -2), (-2, 2), (-2, -2)):
            target = source.offset(rows, cols)
            eye = source.offset(rows // 2, cols // 2)
            if target is None or eye is None or self.piece_at(eye) is not None:
                continue
            if piece.side is Side.RED and target.row < 5:
                continue
            if piece.side is Side.BLACK and target.row > 4:
                continue
            if self._empty_or_enemy(target, piece.side):
                targets.append(target)
        return tuple(targets)

    def _horse_targets(self, source: Point, piece: Piece) -> Tuple[Point, ...]:
        targets: List[Point] = []
        moves = (
            (2, 1, 1, 0), (2, -1, 1, 0), (-2, 1, -1, 0), (-2, -1, -1, 0),
            (1, 2, 0, 1), (-1, 2, 0, 1), (1, -2, 0, -1), (-1, -2, 0, -1),
        )
        for rows, cols, leg_rows, leg_cols in moves:
            target = source.offset(rows, cols)
            leg = source.offset(leg_rows, leg_cols)
            if target is not None and leg is not None and self.piece_at(leg) is None and self._empty_or_enemy(target, piece.side):
                targets.append(target)
        return tuple(targets)

    def _rook_targets(self, source: Point, piece: Piece) -> Tuple[Point, ...]:
        return self._line_targets(source, piece, cannon=False)

    def _cannon_targets(self, source: Point, piece: Piece) -> Tuple[Point, ...]:
        return self._line_targets(source, piece, cannon=True)

    def _line_targets(self, source: Point, piece: Piece, cannon: bool) -> Tuple[Point, ...]:
        targets: List[Point] = []
        for rows, cols in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            screen_found = False
            distance = 1
            while True:
                target = source.offset(rows * distance, cols * distance)
                if target is None:
                    break
                occupant = self.piece_at(target)
                if not cannon:
                    if occupant is None:
                        targets.append(target)
                    else:
                        if occupant.side is not piece.side:
                            targets.append(target)
                        break
                elif not screen_found:
                    if occupant is None:
                        targets.append(target)
                    else:
                        screen_found = True
                elif occupant is not None:
                    if occupant.side is not piece.side:
                        targets.append(target)
                    break
                distance += 1
        return tuple(targets)

    def _pawn_targets(self, source: Point, piece: Piece) -> Tuple[Point, ...]:
        direction = -1 if piece.side is Side.RED else 1
        offsets = [(direction, 0)]
        crossed_river = source.row <= 4 if piece.side is Side.RED else source.row >= 5
        if crossed_river:
            offsets.extend(((0, 1), (0, -1)))
        return self._step_targets(source, piece, offsets)

    def _pieces_between(self, first: Point, second: Point) -> int:
        if first.col != second.col:
            return 0
        start, end = sorted((first.row, second.row))
        return sum(
            self.board[Point(row, first.col).index] is not None
            for row in range(start + 1, end)
        )
