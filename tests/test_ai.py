from __future__ import annotations

import random
import threading
import unittest

from ai_fixtures import fixed_positions
from chinese_chess.ai import (
    GreedyEngine,
    RandomLegalEngine,
    SearchLimits,
    SearchOutcome,
)
from chinese_chess.rules import Move, Point


class SearchLimitsTests(unittest.TestCase):
    def test_defaults_allow_a_shallow_baseline_search(self) -> None:
        limits = SearchLimits()
        self.assertEqual(limits.max_depth, 1)
        self.assertIsNone(limits.max_nodes)
        self.assertIsNone(limits.time_limit_ms)

    def test_rejects_invalid_limits(self) -> None:
        for limits in (
            SearchLimits(max_depth=0),
            SearchLimits(max_nodes=-1),
            SearchLimits(time_limit_ms=-1),
        ):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                limits.validate()


class BaselineEngineTests(unittest.TestCase):
    def test_random_engine_returns_legal_move_and_search_metadata(self) -> None:
        position = fixed_positions()["initial"]
        result = RandomLegalEngine(seed=7).choose_move(position, SearchLimits(max_depth=4))

        self.assertIn(result.best_move, position.legal_moves())
        self.assertEqual(result.score, 0)
        self.assertEqual(result.completed_depth, 1)
        self.assertEqual(result.nodes, 1)
        self.assertGreaterEqual(result.elapsed_ms, 0)
        self.assertEqual(result.principal_variation, (result.best_move,))
        self.assertEqual(result.outcome, SearchOutcome.COMPLETED)

    def test_random_engine_is_reproducible_with_a_seed(self) -> None:
        position = fixed_positions()["initial"]
        first = RandomLegalEngine(seed=19).choose_move(position)
        second = RandomLegalEngine(seed=19).choose_move(position)
        self.assertEqual(first.best_move, second.best_move)

    def test_greedy_engine_prefers_the_most_valuable_capture(self) -> None:
        position = fixed_positions()["red_capture"]
        result = GreedyEngine().choose_move(position)

        self.assertEqual(result.best_move, Move(Point(5, 4), Point(3, 4)))
        self.assertEqual(result.score, 400)
        self.assertEqual(result.completed_depth, 1)
        self.assertEqual(result.nodes, len(position.legal_moves()))
        self.assertEqual(result.principal_variation, (result.best_move,))

    def test_greedy_engine_scores_non_capture_as_zero(self) -> None:
        result = GreedyEngine().choose_move(fixed_positions()["quiet"])
        self.assertEqual(result.score, 0)

    def test_terminal_position_has_no_move_or_principal_variation(self) -> None:
        position = fixed_positions()["checkmate"]
        for engine in (RandomLegalEngine(seed=1), GreedyEngine()):
            with self.subTest(engine=type(engine).__name__):
                result = engine.choose_move(position)
                self.assertIsNone(result.best_move)
                self.assertIsNone(result.score)
                self.assertEqual(result.completed_depth, 0)
                self.assertEqual(result.nodes, 0)
                self.assertEqual(result.principal_variation, ())
                self.assertEqual(result.outcome, SearchOutcome.TERMINAL)

    def test_zero_time_limit_returns_safely_without_a_move(self) -> None:
        position = fixed_positions()["initial"]
        for engine in (RandomLegalEngine(seed=1), GreedyEngine()):
            with self.subTest(engine=type(engine).__name__):
                result = engine.choose_move(position, SearchLimits(time_limit_ms=0))
                self.assertIsNone(result.best_move)
                self.assertEqual(result.nodes, 0)
                self.assertEqual(result.completed_depth, 0)
                self.assertEqual(result.outcome, SearchOutcome.TIME_LIMIT)

    def test_zero_node_limit_returns_safely_without_a_move(self) -> None:
        position = fixed_positions()["initial"]
        for engine in (RandomLegalEngine(seed=1), GreedyEngine()):
            with self.subTest(engine=type(engine).__name__):
                result = engine.choose_move(position, SearchLimits(max_nodes=0))
                self.assertIsNone(result.best_move)
                self.assertEqual(result.nodes, 0)
                self.assertEqual(result.outcome, SearchOutcome.NODE_LIMIT)

    def test_greedy_node_limit_returns_best_move_from_completed_candidates(self) -> None:
        position = fixed_positions()["initial"]
        result = GreedyEngine().choose_move(position, SearchLimits(max_nodes=1))

        self.assertEqual(result.best_move, position.legal_moves()[0])
        self.assertEqual(result.nodes, 1)
        self.assertEqual(result.completed_depth, 0)
        self.assertEqual(result.outcome, SearchOutcome.NODE_LIMIT)

    def test_stop_during_random_selection_discards_the_move(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        class PausingRandom(random.Random):
            def choice(self, moves):  # type: ignore[no-untyped-def]
                entered.set()
                release.wait(1)
                return moves[0]

        engine = RandomLegalEngine(rng=PausingRandom())
        holder = []

        def search() -> None:
            holder.append(engine.choose_move(fixed_positions()["initial"]))

        thread = threading.Thread(target=search)
        thread.start()
        self.assertTrue(entered.wait(1))
        engine.stop()
        release.set()
        thread.join(1)

        self.assertFalse(thread.is_alive())
        self.assertEqual(holder[0].outcome, SearchOutcome.STOPPED)
        self.assertIsNone(holder[0].best_move)
        self.assertEqual(holder[0].principal_variation, ())

    def test_engine_can_search_again_after_stop(self) -> None:
        engine = GreedyEngine()
        engine.stop()
        result = engine.choose_move(fixed_positions()["initial"])
        self.assertEqual(result.outcome, SearchOutcome.COMPLETED)
        self.assertIsNotNone(result.best_move)

    def test_fixed_positions_never_produce_illegal_moves(self) -> None:
        for name, position in fixed_positions().items():
            legal_moves = position.legal_moves()
            for engine in (RandomLegalEngine(seed=3), GreedyEngine()):
                with self.subTest(position=name, engine=type(engine).__name__):
                    original = position
                    result = engine.choose_move(position)
                    self.assertIs(position, original)
                    if legal_moves:
                        self.assertIn(result.best_move, legal_moves)
                    else:
                        self.assertIsNone(result.best_move)

    def test_real_time_limit_interrupts_greedy_selection(self) -> None:
        engine = GreedyEngine()
        result = engine.choose_move(
            fixed_positions()["initial"],
            SearchLimits(time_limit_ms=0.001),
        )
        self.assertIn(result.outcome, (SearchOutcome.TIME_LIMIT, SearchOutcome.COMPLETED))
        if result.best_move is not None:
            self.assertIn(result.best_move, fixed_positions()["initial"].legal_moves())
        self.assertLess(result.elapsed_ms, 1000)


if __name__ == "__main__":
    unittest.main()
