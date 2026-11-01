from __future__ import annotations

import unittest

from ai_fixtures import fixed_positions
from chinese_chess.ai import AlphaBetaEngine, SearchLimits, SearchOutcome


class IterativeDeepeningTests(unittest.TestCase):
    def test_node_limit_returns_last_complete_iteration(self) -> None:
        position = fixed_positions()["red_capture"]
        first = AlphaBetaEngine().choose_move(position, SearchLimits(max_depth=1))

        result = AlphaBetaEngine().choose_move(
            position,
            SearchLimits(max_depth=3, max_nodes=first.nodes),
        )

        self.assertEqual(result.outcome, SearchOutcome.NODE_LIMIT)
        self.assertEqual(result.completed_depth, 1)
        self.assertEqual(result.best_move, first.best_move)
        self.assertEqual(result.score, first.score)
        self.assertEqual(result.principal_variation, first.principal_variation)
        self.assertEqual(result.nodes, first.nodes)

    def test_time_limit_returns_last_complete_iteration(self) -> None:
        position = fixed_positions()["red_capture"]
        first = AlphaBetaEngine().choose_move(position, SearchLimits(max_depth=1))
        calls = 0

        def clock() -> float:
            nonlocal calls
            calls += 1
            return 0.0 if calls <= first.nodes + 2 else 1.0

        result = AlphaBetaEngine(clock=clock).choose_move(
            position,
            SearchLimits(max_depth=3, time_limit_ms=100),
        )

        self.assertEqual(result.outcome, SearchOutcome.TIME_LIMIT)
        self.assertEqual(result.completed_depth, 1)
        self.assertEqual(result.best_move, first.best_move)
        self.assertEqual(result.score, first.score)

    def test_interrupted_first_iteration_returns_legal_fallback(self) -> None:
        position = fixed_positions()["initial"]
        result = AlphaBetaEngine().choose_move(
            position,
            SearchLimits(max_depth=3, max_nodes=1),
        )

        self.assertEqual(result.outcome, SearchOutcome.NODE_LIMIT)
        self.assertEqual(result.completed_depth, 0)
        self.assertIn(result.best_move, position.legal_moves())
        self.assertEqual(result.principal_variation, (result.best_move,))
        self.assertIsNone(result.score)

    def test_zero_limits_still_return_no_move(self) -> None:
        position = fixed_positions()["initial"]
        for limits in (SearchLimits(max_nodes=0), SearchLimits(time_limit_ms=0)):
            with self.subTest(limits=limits):
                result = AlphaBetaEngine().choose_move(position, limits)
                self.assertIsNone(result.best_move)
                self.assertEqual(result.completed_depth, 0)


if __name__ == "__main__":
    unittest.main()
