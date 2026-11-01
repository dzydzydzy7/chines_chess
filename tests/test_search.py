from __future__ import annotations

import unittest

from ai_fixtures import fixed_positions, position_with_pieces
from chinese_chess.ai import (
    MATE_SCORE,
    AlphaBetaEngine,
    NegamaxEngine,
    SearchLimits,
    SearchOutcome,
    evaluate_position,
    ordered_moves,
)
from chinese_chess.rules import Move, Piece, PieceType, Point, Position, Side


class EvaluationTests(unittest.TestCase):
    def test_initial_position_is_balanced_for_both_sides(self) -> None:
        position = Position.initial()
        self.assertEqual(evaluate_position(position, Side.RED), 0)
        self.assertEqual(evaluate_position(position, Side.BLACK), 0)

    def test_material_score_uses_requested_side_perspective(self) -> None:
        position = position_with_pieces(
            Side.RED,
            (Point(9, 3), Piece(Side.RED, PieceType.KING)),
            (Point(0, 4), Piece(Side.BLACK, PieceType.KING)),
            (Point(5, 0), Piece(Side.RED, PieceType.ROOK)),
        )
        self.assertEqual(evaluate_position(position, Side.RED), 900)
        self.assertEqual(evaluate_position(position, Side.BLACK), -900)
        self.assertEqual(evaluate_position(position), 900)

    def test_horse_position_table_mirrors_red_and_black_rows(self) -> None:
        red = position_with_pieces(
            Side.RED,
            (Point(9, 3), Piece(Side.RED, PieceType.KING)),
            (Point(0, 4), Piece(Side.BLACK, PieceType.KING)),
            (Point(6, 4), Piece(Side.RED, PieceType.HORSE)),
        )
        black = position_with_pieces(
            Side.BLACK,
            (Point(9, 3), Piece(Side.RED, PieceType.KING)),
            (Point(0, 4), Piece(Side.BLACK, PieceType.KING)),
            (Point(3, 4), Piece(Side.BLACK, PieceType.HORSE)),
        )
        self.assertEqual(evaluate_position(red, Side.RED), -evaluate_position(black, Side.RED))
        self.assertEqual(evaluate_position(red), evaluate_position(black))

    def test_pawn_position_table_rewards_advancement_symmetrically(self) -> None:
        red = position_with_pieces(
            Side.RED,
            (Point(9, 3), Piece(Side.RED, PieceType.KING)),
            (Point(0, 4), Piece(Side.BLACK, PieceType.KING)),
            (Point(4, 2), Piece(Side.RED, PieceType.PAWN)),
        )
        black = position_with_pieces(
            Side.BLACK,
            (Point(9, 3), Piece(Side.RED, PieceType.KING)),
            (Point(0, 4), Piece(Side.BLACK, PieceType.KING)),
            (Point(5, 2), Piece(Side.BLACK, PieceType.PAWN)),
        )
        self.assertGreater(evaluate_position(red, Side.RED), 100)
        self.assertEqual(evaluate_position(red, Side.RED), -evaluate_position(black, Side.RED))


class MoveOrderingTests(unittest.TestCase):
    def test_higher_value_captures_are_ordered_first(self) -> None:
        position = fixed_positions()["red_capture"]
        moves = ordered_moves(position, position.legal_moves())
        self.assertEqual(moves[0], Move(Point(5, 4), Point(3, 4)))

    def test_non_capture_order_is_stable(self) -> None:
        position = fixed_positions()["quiet"]
        legal_moves = position.legal_moves()
        self.assertEqual(ordered_moves(position, legal_moves), legal_moves)


class SearchTests(unittest.TestCase):
    def test_alpha_beta_matches_unpruned_negamax_root_score(self) -> None:
        for name in ("quiet", "red_capture", "exchange", "mate_in_one"):
            position = fixed_positions()[name]
            for depth in (1, 2):
                with self.subTest(position=name, depth=depth):
                    limits = SearchLimits(max_depth=depth)
                    negamax = NegamaxEngine().choose_move(position, limits)
                    alpha_beta = AlphaBetaEngine().choose_move(position, limits)
                    self.assertEqual(alpha_beta.outcome, SearchOutcome.COMPLETED)
                    self.assertEqual(alpha_beta.score, negamax.score)
                    self.assertEqual(alpha_beta.completed_depth, depth)
                    self.assertEqual(alpha_beta.principal_variation[0], alpha_beta.best_move)

    def test_alpha_beta_matches_negamax_at_depth_three_with_one_root_move(self) -> None:
        position = fixed_positions()["unique_evasion"]
        limits = SearchLimits(max_depth=3)
        negamax = NegamaxEngine().choose_move(position, limits)
        alpha_beta = AlphaBetaEngine().choose_move(position, limits)
        self.assertEqual(alpha_beta.score, negamax.score)

    def test_finds_mate_in_one_and_scores_distance(self) -> None:
        position = fixed_positions()["mate_in_one"]
        for engine in (NegamaxEngine(), AlphaBetaEngine()):
            with self.subTest(engine=type(engine).__name__):
                result = engine.choose_move(position, SearchLimits(max_depth=2))
                self.assertIsNotNone(result.best_move)
                self.assertEqual(position.apply(result.best_move).status().value, "red_won")
                self.assertEqual(result.score, MATE_SCORE - 1)
                self.assertEqual(result.principal_variation, (result.best_move,))

    def test_finds_the_only_legal_evasion(self) -> None:
        position = fixed_positions()["unique_evasion"]
        self.assertEqual(position.legal_moves(), (Move(Point(0, 4), Point(0, 5)),))
        result = AlphaBetaEngine().choose_move(position, SearchLimits(max_depth=3))
        self.assertEqual(result.best_move, position.legal_moves()[0])

    def test_never_moves_pinned_rook_away_from_king_file(self) -> None:
        position = fixed_positions()["pinned_rook"]
        result = AlphaBetaEngine().choose_move(position, SearchLimits(max_depth=2))
        self.assertIn(result.best_move, position.legal_moves())
        self.assertNotEqual(result.best_move, Move(Point(8, 4), Point(8, 3)))

    def test_search_accounts_for_opponent_recapture(self) -> None:
        position = fixed_positions()["exchange"]
        result = AlphaBetaEngine().choose_move(position, SearchLimits(max_depth=2))
        self.assertEqual(result.best_move, Move(Point(5, 4), Point(5, 6)))
        self.assertEqual(len(result.principal_variation), 2)

        replayed = position
        for move in result.principal_variation:
            replayed = replayed.apply(move)
        self.assertEqual(len(replayed.history), 2)

    def test_terminal_root_reports_loss_for_side_to_move(self) -> None:
        position = fixed_positions()["checkmate"]
        for engine in (NegamaxEngine(), AlphaBetaEngine()):
            with self.subTest(engine=type(engine).__name__):
                result = engine.choose_move(position, SearchLimits(max_depth=3))
                self.assertEqual(result.outcome, SearchOutcome.TERMINAL)
                self.assertEqual(result.score, -MATE_SCORE)
                self.assertIsNone(result.best_move)
                self.assertEqual(result.principal_variation, ())

    def test_repetition_loss_can_be_a_win_for_side_to_move(self) -> None:
        position = position_with_pieces(
            Side.RED,
            (Point(9, 3), Piece(Side.RED, PieceType.KING)),
            (Point(0, 4), Piece(Side.BLACK, PieceType.KING)),
            (Point(1, 0), Piece(Side.RED, PieceType.ROOK)),
        )
        cycle = (
            ((1, 0), (1, 4)), ((0, 4), (0, 5)),
            ((1, 4), (1, 5)), ((0, 5), (0, 4)),
            ((1, 5), (1, 4)), ((0, 4), (0, 5)),
            ((1, 4), (1, 5)), ((0, 5), (0, 4)),
            ((1, 5), (1, 4)),
        )
        for source, target in cycle:
            position = position.apply(Move(Point(*source), Point(*target)))
        self.assertEqual(position.status().value, "black_won")
        self.assertEqual(position.turn, Side.BLACK)

        result = AlphaBetaEngine().choose_move(position)
        self.assertEqual(result.outcome, SearchOutcome.TERMINAL)
        self.assertEqual(result.score, MATE_SCORE)
        self.assertIsNone(result.best_move)

    def test_zero_limits_interrupt_search_without_a_move(self) -> None:
        position = fixed_positions()["initial"]
        for limits in (SearchLimits(max_nodes=0), SearchLimits(time_limit_ms=0)):
            with self.subTest(limits=limits):
                result = AlphaBetaEngine().choose_move(position, limits)
                self.assertIsNone(result.best_move)
                self.assertEqual(result.completed_depth, 0)
                self.assertEqual(result.principal_variation, ())

    def test_search_does_not_modify_position(self) -> None:
        position = fixed_positions()["exchange"]
        original = (position.board, position.turn, position.history)
        AlphaBetaEngine().choose_move(position, SearchLimits(max_depth=3))
        self.assertEqual((position.board, position.turn, position.history), original)


if __name__ == "__main__":
    unittest.main()
