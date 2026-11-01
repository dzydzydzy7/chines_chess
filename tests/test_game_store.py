import json
import tempfile
import unittest
from pathlib import Path

from chinese_chess.game_store import GameStore
from chinese_chess.rules import Piece, PieceType, Point, Position, Side
from chinese_chess.service import GameService


class GameStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = GameStore(self.root)
        self.addCleanup(self.directory.cleanup)

    def test_save_is_idempotent_and_list_shows_id_and_time(self) -> None:
        service = GameService(store=self.store)
        service.move(54, 45)
        saved = service.save()
        game_id = saved["id"]
        first_path = self.root / (game_id + ".json")
        first_modified = first_path.stat().st_mtime_ns
        service.save()
        self.assertEqual(first_path.stat().st_mtime_ns, first_modified)
        self.assertEqual(len(list(self.root.glob("*.json"))), 1)
        games = self.store.list()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["id"], game_id)
        self.assertIn("created_at", games[0])
        self.assertIn("saved_at", games[0])
        self.assertEqual(games[0]["move_count"], 1)

    def test_restore_by_id_rebuilds_position(self) -> None:
        service = GameService(store=self.store)
        service.move(54, 45)
        service.move(27, 36)
        game_id = service.save()["id"]
        restored = GameService(store=self.store).restore(game_id)
        self.assertEqual(restored["id"], game_id)
        self.assertEqual(restored["turn"], "red")
        self.assertEqual(len(restored["history"]), 2)
        self.assertEqual(restored["history"][1]["to"], 36)

    def test_replay_returns_any_ply_without_changing_active_game(self) -> None:
        service = GameService(store=self.store)
        service.move(54, 45)
        service.move(27, 36)
        game_id = service.save()["id"]
        replay = service.replay(game_id, 1)
        self.assertEqual(replay["turn"], "black")
        self.assertEqual(len(replay["history"]), 1)
        self.assertEqual(replay["replay_ply"], 1)
        self.assertEqual(replay["replay_length"], 2)
        self.assertEqual(len(service.state()["history"]), 2)
        with self.assertRaises(ValueError):
            service.replay(game_id, 3)

    def test_finished_game_is_saved_automatically(self) -> None:
        service = GameService(store=self.store)
        board = [None] * 90
        board[Point(9, 4).index] = Piece(Side.RED, PieceType.KING)
        board[Point(0, 4).index] = Piece(Side.BLACK, PieceType.KING)
        board[Point(1, 4).index] = Piece(Side.RED, PieceType.ROOK)
        service._position = Position(tuple(board), Side.RED)
        state = service.move(13, 4)
        self.assertEqual(state["status"], "red_won")
        self.assertIsNotNone(state["saved_at"])
        self.assertEqual(len(self.store.list()), 1)
        record = json.loads((self.root / (state["id"] + ".json")).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "red_won")


if __name__ == "__main__":
    unittest.main()
