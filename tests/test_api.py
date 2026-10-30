import unittest

from chinese_chess.api import Application


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Application()

    def test_get_game(self) -> None:
        status, body = self.app.handle("GET", "/api/game", None)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["pieces"]), 32)

    def test_post_legal_move(self) -> None:
        status, body = self.app.handle("POST", "/api/game/move", {"from": 54, "to": 45})
        self.assertEqual(status, 200)
        self.assertEqual(body["turn"], "black")

    def test_invalid_move_returns_422(self) -> None:
        status, body = self.app.handle("POST", "/api/game/move", {"from": 54, "to": 53})
        self.assertEqual(status, 422)
        self.assertIn("error", body)

    def test_legal_targets(self) -> None:
        status, body = self.app.handle("GET", "/api/game/legal-moves?from=54", None)
        self.assertEqual(status, 200)
        self.assertEqual(body["targets"], [45])

    def test_reset(self) -> None:
        self.app.handle("POST", "/api/game/move", {"from": 54, "to": 45})
        status, body = self.app.handle("POST", "/api/game/reset", {})
        self.assertEqual(status, 200)
        self.assertEqual(body["history"], [])

    def test_get_and_update_config(self) -> None:
        status, body = self.app.handle("PUT", "/api/config", {"board": {"show_coordinates": False}})
        self.assertEqual(status, 200)
        self.assertFalse(body["board"]["show_coordinates"])
        _, saved = self.app.handle("GET", "/api/config", None)
        self.assertFalse(saved["board"]["show_coordinates"])

    def test_bad_config_returns_422(self) -> None:
        status, _ = self.app.handle("PUT", "/api/config", {"robot": {"speed_percent": 200}})
        self.assertEqual(status, 422)

    def test_unknown_route_returns_404(self) -> None:
        status, _ = self.app.handle("GET", "/api/missing", None)
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
