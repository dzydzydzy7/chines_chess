import tempfile
import unittest
from pathlib import Path

from chinese_chess.api import Application
from chinese_chess.config import Config, ConfigValidationError
from chinese_chess.config_store import ConfigStore
from chinese_chess.game_store import GameStore


class PveApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.app = Application(
            config_store=ConfigStore(root / "settings.json"),
            game_store=GameStore(root / "games"),
        )

    def test_start_pve_route_returns_mode_side_and_difficulty(self) -> None:
        status, body = self.app.handle(
            "POST",
            "/api/game/pve",
            {"player_side": "red", "difficulty": "hard", "time_limit_ms": 100},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["mode"], "pve")
        self.assertEqual(body["player_side"], "red")
        self.assertEqual(body["difficulty"], "hard")
        self.assertFalse(body["ai_thinking"])

    def test_invalid_pve_options_return_422(self) -> None:
        for payload in (
            {"player_side": "green", "difficulty": "easy", "time_limit_ms": 100},
            {"player_side": "red", "difficulty": "impossible", "time_limit_ms": 100},
        ):
            with self.subTest(payload=payload):
                status, body = self.app.handle("POST", "/api/game/pve", payload)
                self.assertEqual(status, 422)
                self.assertIn("error", body)

    def test_config_stores_player_side(self) -> None:
        config = Config.defaults().updated({"ai": {"player_side": "black"}})
        self.assertEqual(config.ai_player_side, "black")
        self.assertEqual(config.to_dict()["ai"]["player_side"], "black")
        with self.assertRaises(ConfigValidationError):
            Config.defaults().updated({"ai": {"player_side": "green"}})


if __name__ == "__main__":
    unittest.main()
