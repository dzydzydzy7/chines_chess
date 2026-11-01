from __future__ import annotations

from typing import Dict, Tuple

from chinese_chess.rules import Piece, PieceType, Point, Position, Side


def position_with_pieces(turn: Side, *pieces: Tuple[Point, Piece]) -> Position:
    board = [None] * 90
    for point, piece in pieces:
        board[point.index] = piece
    return Position(board=tuple(board), turn=turn)


def fixed_positions() -> Dict[str, Position]:
    red_king = Piece(Side.RED, PieceType.KING)
    black_king = Piece(Side.BLACK, PieceType.KING)
    return {
        "initial": Position.initial(),
        "quiet": position_with_pieces(
            Side.RED,
            (Point(9, 3), red_king),
            (Point(0, 4), black_king),
            (Point(6, 0), Piece(Side.RED, PieceType.PAWN)),
            (Point(3, 8), Piece(Side.BLACK, PieceType.PAWN)),
        ),
        "red_capture": position_with_pieces(
            Side.RED,
            (Point(9, 3), red_king),
            (Point(0, 4), black_king),
            (Point(5, 4), Piece(Side.RED, PieceType.ROOK)),
            (Point(5, 6), Piece(Side.BLACK, PieceType.PAWN)),
            (Point(3, 4), Piece(Side.BLACK, PieceType.HORSE)),
        ),
        "black_capture": position_with_pieces(
            Side.BLACK,
            (Point(9, 3), red_king),
            (Point(0, 4), black_king),
            (Point(5, 4), Piece(Side.BLACK, PieceType.ROOK)),
            (Point(5, 6), Piece(Side.RED, PieceType.PAWN)),
            (Point(3, 4), Piece(Side.RED, PieceType.HORSE)),
        ),
        "red_in_check": position_with_pieces(
            Side.RED,
            (Point(9, 4), red_king),
            (Point(0, 3), black_king),
            (Point(5, 4), Piece(Side.BLACK, PieceType.ROOK)),
            (Point(9, 0), Piece(Side.RED, PieceType.ROOK)),
        ),
        "checkmate": position_with_pieces(
            Side.BLACK,
            (Point(0, 4), black_king),
            (Point(9, 4), red_king),
            (Point(1, 4), Piece(Side.RED, PieceType.ROOK)),
            (Point(2, 3), Piece(Side.RED, PieceType.ROOK)),
            (Point(2, 5), Piece(Side.RED, PieceType.ROOK)),
        ),
        "mate_in_one": position_with_pieces(
            Side.RED,
            (Point(0, 4), black_king),
            (Point(9, 4), red_king),
            (Point(8, 4), Piece(Side.RED, PieceType.ROOK)),
            (Point(2, 3), Piece(Side.RED, PieceType.ROOK)),
            (Point(2, 5), Piece(Side.RED, PieceType.ROOK)),
        ),
        "unique_evasion": position_with_pieces(
            Side.BLACK,
            (Point(0, 4), black_king),
            (Point(9, 4), red_king),
            (Point(1, 4), Piece(Side.RED, PieceType.ROOK)),
            (Point(2, 3), Piece(Side.RED, PieceType.ROOK)),
        ),
        "pinned_rook": position_with_pieces(
            Side.RED,
            (Point(9, 4), red_king),
            (Point(0, 4), black_king),
            (Point(8, 4), Piece(Side.RED, PieceType.ROOK)),
            (Point(6, 0), Piece(Side.RED, PieceType.PAWN)),
        ),
        "exchange": position_with_pieces(
            Side.RED,
            (Point(9, 3), red_king),
            (Point(0, 4), black_king),
            (Point(5, 4), Piece(Side.RED, PieceType.ROOK)),
            (Point(5, 6), Piece(Side.BLACK, PieceType.PAWN)),
            (Point(3, 4), Piece(Side.BLACK, PieceType.HORSE)),
            (Point(1, 4), Piece(Side.BLACK, PieceType.ROOK)),
        ),
    }
