import tempfile
import unittest
from pathlib import Path

from chinese_chess.ai import AlphaBetaEngine, SearchLimits
from chinese_chess.api import Application
from chinese_chess.config_store import ConfigStore
from chinese_chess.game_store import GameStore
from chinese_chess.rules import Move, Point, Position
from chinese_chess.service import GameService


class ExperienceRegressionTests(unittest.TestCase):
    def test_ai_config_changes_apply_without_process_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = Application(
                config_store=ConfigStore(root / "settings.json"),
                game_store=GameStore(root / "games"),
            )
            original_id = app.game.state()["id"]

            status, _ = app.handle("PUT", "/api/config", {
                "ai": {"enabled": True, "player_side": "red", "difficulty": "hard"},
            })
            self.assertEqual(status, 200)
            enabled = app.game.state()
            self.assertEqual(enabled["mode"], "pve")
            self.assertEqual(enabled["difficulty"], "hard")
            self.assertNotEqual(enabled["id"], original_id)

            app.handle("PUT", "/api/config", {"ai": {"enabled": False}})
            disabled = app.game.state()
            self.assertEqual(disabled["mode"], "pvp")
            self.assertNotEqual(disabled["id"], enabled["id"])

            app.handle("PUT", "/api/config", {"board": {"show_coordinates": False}})
            self.assertEqual(app.game.state()["id"], disabled["id"])

    def test_history_records_the_moving_piece_for_every_ply(self) -> None:
        service = GameService()
        service.move(54, 45)
        service.move(27, 36)
        state = service.move(45, 36)

        self.assertEqual([move["piece"] for move in state["history"]], ["兵", "卒", "兵"])
        self.assertEqual(state["history"][2]["captured"], "卒")

    def test_opening_search_does_not_fall_back_to_cannon_takes_horse(self) -> None:
        result = AlphaBetaEngine().choose_move(
            Position.initial(),
            SearchLimits(max_depth=2, max_nodes=3000, time_limit_ms=1000),
        )

        self.assertGreaterEqual(result.completed_depth, 1)
        self.assertIsNotNone(result.score)
        self.assertIsNotNone(result.best_move)
        self.assertNotIn(
            result.best_move,
            (
                Move(Point(7, 1), Point(0, 1)),
                Move(Point(7, 7), Point(0, 7)),
            ),
        )
        moved_piece = Position.initial().piece_at(result.best_move.source)
        self.assertEqual(moved_piece.kind.value, "horse")


if __name__ == "__main__":
    unittest.main()
