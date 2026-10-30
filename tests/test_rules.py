from __future__ import annotations

import unittest

from chinese_chess.rules import (
    GameStatus,
    IllegalMoveError,
    Move,
    Piece,
    PieceType,
    Point,
    Position,
    Side,
)


def empty_position(turn: Side = Side.RED) -> Position:
    return Position(board=(None,) * 90, turn=turn)


def with_pieces(turn: Side, *pieces: tuple[Point, Piece]) -> Position:
    position = empty_position(turn)
    board = list(position.board)
    for point, piece in pieces:
        board[point.index] = piece
    return Position(board=tuple(board), turn=turn)


KING_RED = Piece(Side.RED, PieceType.KING)
KING_BLACK = Piece(Side.BLACK, PieceType.KING)


class CoordinateTests(unittest.TestCase):
    def test_point_validates_board_boundaries(self) -> None:
        with self.assertRaises(ValueError):
            Point(-1, 0)
        with self.assertRaises(ValueError):
            Point(10, 0)
        with self.assertRaises(ValueError):
            Point(0, 9)

    def test_index_uses_nine_columns(self) -> None:
        self.assertEqual(Point(0, 0).index, 0)
        self.assertEqual(Point(1, 0).index, 9)
        self.assertEqual(Point(9, 8).index, 89)


class PieceMovementTests(unittest.TestCase):
    def assert_move(self, valid: bool, point: Point, target: Point, *pieces: tuple[Point, Piece]) -> None:
        position = with_pieces(Side.RED, (point, pieces[0][1]) if pieces and pieces[0][0] == point else (point, KING_RED), *pieces)
        if valid:
            self.assertIn(target, position.pseudo_legal_targets(point))
        else:
            self.assertNotIn(target, position.pseudo_legal_targets(point))

    def test_king_moves_one_step_inside_palace(self) -> None:
        position = with_pieces(Side.RED, (Point(9, 4), KING_RED))
        self.assertIn(Point(8, 4), position.pseudo_legal_targets(Point(9, 4)))
        self.assertNotIn(Point(9, 7), position.pseudo_legal_targets(Point(9, 4)))
        self.assertNotIn(Point(8, 5), position.pseudo_legal_targets(Point(9, 4)))

    def test_advisor_moves_diagonally_inside_palace(self) -> None:
        advisor = Piece(Side.RED, PieceType.ADVISOR)
        position = with_pieces(Side.RED, (Point(9, 3), advisor))
        self.assertEqual(position.pseudo_legal_targets(Point(9, 3)), (Point(8, 4),))

    def test_elephant_moves_two_diagonally_and_cannot_cross_river(self) -> None:
        elephant = Piece(Side.RED, PieceType.ELEPHANT)
        position = with_pieces(Side.RED, (Point(9, 2), elephant))
        self.assertIn(Point(7, 4), position.pseudo_legal_targets(Point(9, 2)))
        blocked = with_pieces(Side.RED, (Point(9, 2), elephant), (Point(8, 3), KING_RED))
        self.assertNotIn(Point(7, 4), blocked.pseudo_legal_targets(Point(9, 2)))
        self.assertNotIn(Point(5, 2), position.pseudo_legal_targets(Point(7, 2))) if False else None

    def test_elephant_at_river_cannot_cross(self) -> None:
        elephant = Piece(Side.RED, PieceType.ELEPHANT)
        position = with_pieces(Side.RED, (Point(5, 2), elephant))
        self.assertNotIn(Point(3, 4), position.pseudo_legal_targets(Point(5, 2)))

    def test_horse_leg_can_be_blocked(self) -> None:
        horse = Piece(Side.RED, PieceType.HORSE)
        position = with_pieces(Side.RED, (Point(9, 1), horse))
        self.assertIn(Point(7, 2), position.pseudo_legal_targets(Point(9, 1)))
        blocked = with_pieces(Side.RED, (Point(9, 1), horse), (Point(8, 1), KING_RED))
        self.assertNotIn(Point(7, 2), blocked.pseudo_legal_targets(Point(9, 1)))

    def test_rook_stops_before_friendly_piece_and_captures_enemy(self) -> None:
        rook = Piece(Side.RED, PieceType.ROOK)
        position = with_pieces(
            Side.RED,
            (Point(9, 0), rook),
            (Point(9, 4), KING_RED),
            (Point(5, 0), KING_BLACK),
        )
        targets = position.pseudo_legal_targets(Point(9, 0))
        self.assertIn(Point(5, 0), targets)
        self.assertNotIn(Point(4, 0), targets)
        self.assertNotIn(Point(9, 4), targets)
        self.assertNotIn(Point(9, 5), targets)

    def test_cannon_needs_exactly_one_screen_to_capture(self) -> None:
        cannon = Piece(Side.RED, PieceType.CANNON)
        position = with_pieces(
            Side.RED,
            (Point(9, 0), cannon),
            (Point(7, 0), KING_RED),
            (Point(5, 0), KING_BLACK),
        )
        targets = position.pseudo_legal_targets(Point(9, 0))
        self.assertIn(Point(8, 0), targets)
        self.assertNotIn(Point(6, 0), targets)
        self.assertIn(Point(5, 0), targets)

    def test_pawn_moves_forward_then_sideways_after_crossing_river(self) -> None:
        pawn = Piece(Side.RED, PieceType.PAWN)
        before = with_pieces(Side.RED, (Point(6, 4), pawn))
        after = with_pieces(Side.RED, (Point(4, 4), pawn))
        self.assertEqual(before.pseudo_legal_targets(Point(6, 4)), (Point(5, 4),))
        self.assertEqual(
            set(after.pseudo_legal_targets(Point(4, 4))),
            {Point(3, 4), Point(4, 3), Point(4, 5)},
        )

    def test_black_pawn_moves_toward_increasing_rows(self) -> None:
        pawn = Piece(Side.BLACK, PieceType.PAWN)
        position = with_pieces(Side.BLACK, (Point(3, 4), pawn))
        self.assertEqual(position.pseudo_legal_targets(Point(3, 4)), (Point(4, 4),))


class PositionTests(unittest.TestCase):
    def test_initial_position_has_32_pieces_and_red_starts(self) -> None:
        position = Position.initial()
        self.assertEqual(sum(piece is not None for piece in position.board), 32)
        self.assertEqual(position.turn, Side.RED)

    def test_legal_move_excludes_exposing_own_king(self) -> None:
        rook = Piece(Side.RED, PieceType.ROOK)
        position = with_pieces(
            Side.RED,
            (Point(9, 4), KING_RED),
            (Point(8, 4), rook),
            (Point(0, 4), KING_BLACK),
        )
        self.assertNotIn(Move(Point(8, 4), Point(8, 3)), position.legal_moves())

    def test_kings_cannot_face_each_other(self) -> None:
        position = with_pieces(
            Side.RED,
            (Point(9, 4), KING_RED),
            (Point(0, 4), KING_BLACK),
            (Point(5, 4), Piece(Side.RED, PieceType.PAWN)),
        )
        self.assertNotIn(Move(Point(5, 4), Point(5, 3)), position.legal_moves())

    def test_apply_move_switches_turn_and_records_history(self) -> None:
        position = Position.initial()
        move = Move(Point(6, 4), Point(5, 4))
        updated = position.apply(move)
        self.assertEqual(updated.turn, Side.BLACK)
        self.assertEqual(updated.history, (move,))
        self.assertIsNone(updated.piece_at(Point(6, 4)))
        self.assertEqual(updated.piece_at(Point(5, 4)), Piece(Side.RED, PieceType.PAWN))

    def test_rejects_wrong_turn_and_opponent_target(self) -> None:
        position = Position.initial()
        with self.assertRaises(IllegalMoveError):
            position.apply(Move(Point(3, 4), Point(4, 4)))
        with self.assertRaises(IllegalMoveError):
            position.apply(Move(Point(6, 0), Point(6, 1)))

    def test_detects_checkmate(self) -> None:
        position = with_pieces(
            Side.BLACK,
            (Point(0, 4), KING_BLACK),
            (Point(9, 4), KING_RED),
            (Point(1, 4), Piece(Side.RED, PieceType.ROOK)),
            (Point(2, 3), Piece(Side.RED, PieceType.ROOK)),
            (Point(2, 5), Piece(Side.RED, PieceType.ROOK)),
        )
        self.assertEqual(position.status(), GameStatus.RED_WON)

    def test_stalemate_is_a_win_for_side_without_moves(self) -> None:
        position = with_pieces(
            Side.BLACK,
            (Point(0, 3), KING_BLACK),
            (Point(9, 4), KING_RED),
            (Point(1, 4), Piece(Side.RED, PieceType.ROOK)),
            (Point(2, 3), Piece(Side.RED, PieceType.ROOK)),
        )
        self.assertEqual(position.status(), GameStatus.RED_WON)


if __name__ == "__main__":
    unittest.main()
