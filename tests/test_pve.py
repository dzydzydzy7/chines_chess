from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Callable, Optional

from chinese_chess.ai import SearchResult, SearchOutcome
from chinese_chess.game_store import GameStore
from chinese_chess.service import GameService, ServiceError


class ImmediateEngine:
    def __init__(self) -> None:
        self.limits = None
        self.stopped = False

    def choose_move(self, position, limits):  # type: ignore[no-untyped-def]
        self.limits = limits
        move = position.legal_moves()[0]
        return SearchResult(
            best_move=move,
            score=0,
            completed_depth=1,
            nodes=1,
            elapsed_ms=1.0,
            principal_variation=(move,),
            outcome=SearchOutcome.COMPLETED,
        )

    def stop(self) -> None:
        self.stopped = True


class BlockingEngine(ImmediateEngine):
    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()

    def choose_move(self, position, limits):  # type: ignore[no-untyped-def]
        self.entered.set()
        self.release.wait(2)
        try:
            return super().choose_move(position, limits)
        finally:
            self.finished.set()


class EngineFactory:
    def __init__(self, engine_type: type = ImmediateEngine) -> None:
        self.engine_type = engine_type
        self.engines = []

    def __call__(self):  # type: ignore[no-untyped-def]
        engine = self.engine_type()
        self.engines.append(engine)
        return engine


def wait_for(predicate: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not met before timeout")


class PveServiceTests(unittest.TestCase):
    def test_black_player_starts_with_ai_red_move_and_search_record(self) -> None:
        factory = EngineFactory()
        service = GameService(engine_factory=factory)
        service.start_pve("black", "easy", 100)
        wait_for(lambda: len(service.state()["history"]) == 1)

        state = service.state()
        self.assertEqual(state["mode"], "pve")
        self.assertEqual(state["player_side"], "black")
        self.assertEqual(state["difficulty"], "easy")
        self.assertFalse(state["ai_thinking"])
        self.assertEqual(state["turn"], "black")
        metadata = state["history"][0]["ai"]
        self.assertEqual(metadata["difficulty"], "easy")
        self.assertEqual(metadata["completed_depth"], 1)
        self.assertEqual(metadata["nodes"], 1)
        self.assertEqual(metadata["elapsed_ms"], 1.0)
        self.assertIn("version", metadata)
        self.assertIn("limits", metadata)
        self.assertIn("principal_variation", metadata)

    def test_red_player_move_schedules_ai_with_each_difficulty(self) -> None:
        for difficulty, depth in (("easy", 2), ("medium", 3), ("hard", 5)):
            with self.subTest(difficulty=difficulty):
                factory = EngineFactory()
                service = GameService(engine_factory=factory)
                service.start_pve("red", difficulty, 123)
                self.assertFalse(service.state()["ai_thinking"])
                service.move(54, 45)
                wait_for(lambda: len(service.state()["history"]) == 2)
                self.assertEqual(factory.engines[0].limits.max_depth, depth)
                self.assertEqual(factory.engines[0].limits.time_limit_ms, 123)
                self.assertEqual(service.state()["turn"], "red")

    def test_human_move_is_rejected_while_ai_is_thinking(self) -> None:
        factory = EngineFactory(BlockingEngine)
        service = GameService(engine_factory=factory)
        service.start_pve("black", "easy", 100)
        engine = factory.engines[0]
        self.assertTrue(engine.entered.wait(1))
        with self.assertRaises(ServiceError):
            service.move(54, 45)
        engine.release.set()
        self.assertTrue(engine.finished.wait(1))

    def test_reset_invalidates_old_search_result(self) -> None:
        factory = EngineFactory(BlockingEngine)
        service = GameService(engine_factory=factory)
        original_id = service.start_pve("black", "easy", 100)["id"]
        engine = factory.engines[0]
        self.assertTrue(engine.entered.wait(1))

        reset = service.reset()
        engine.release.set()
        self.assertTrue(engine.finished.wait(1))
        wait_for(lambda: not service.state()["ai_thinking"])

        self.assertNotEqual(reset["id"], original_id)
        self.assertEqual(service.state()["history"], [])
        self.assertEqual(service.state()["mode"], "pvp")

    def test_undo_during_thinking_cancels_player_move_and_old_result(self) -> None:
        factory = EngineFactory(BlockingEngine)
        service = GameService(engine_factory=factory)
        service.start_pve("red", "easy", 100)
        service.move(54, 45)
        engine = factory.engines[0]
        self.assertTrue(engine.entered.wait(1))

        undone = service.undo()
        engine.release.set()
        self.assertTrue(engine.finished.wait(1))

        self.assertEqual(undone["history"], [])
        self.assertEqual(service.state()["history"], [])
        self.assertEqual(service.state()["turn"], "red")

    def test_restore_invalidates_old_search_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = GameStore(Path(directory))
            saved = GameService(store=store)
            saved.move(54, 45)
            game_id = saved.save()["id"]

            factory = EngineFactory(BlockingEngine)
            service = GameService(store=store, engine_factory=factory)
            service.start_pve("black", "easy", 100)
            engine = factory.engines[0]
            self.assertTrue(engine.entered.wait(1))
            restored = service.restore(game_id)
            engine.release.set()
            self.assertTrue(engine.finished.wait(1))

            self.assertEqual(restored["id"], game_id)
            self.assertEqual(len(service.state()["history"]), 1)
            self.assertEqual(service.state()["mode"], "pvp")

    def test_ai_metadata_and_pve_settings_survive_save_and_restore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = GameStore(Path(directory))
            service = GameService(store=store, engine_factory=EngineFactory())
            service.start_pve("black", "medium", 100)
            wait_for(lambda: len(service.state()["history"]) == 1)
            game_id = service.save()["id"]

            restored = GameService(store=store, engine_factory=EngineFactory()).restore(game_id)
            self.assertEqual(restored["mode"], "pve")
            self.assertEqual(restored["player_side"], "black")
            self.assertEqual(restored["difficulty"], "medium")
            self.assertEqual(restored["history"][0]["ai"]["difficulty"], "medium")

    def test_completed_pve_undo_removes_human_and_ai_moves(self) -> None:
        service = GameService(engine_factory=EngineFactory())
        service.start_pve("black", "easy", 100)
        wait_for(lambda: len(service.state()["history"]) == 1)
        service.move(27, 36)
        wait_for(lambda: len(service.state()["history"]) == 3)

        state = service.undo()
        self.assertEqual(len(state["history"]), 1)
        self.assertEqual(state["turn"], "black")


if __name__ == "__main__":
    unittest.main()
