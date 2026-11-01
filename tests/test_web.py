import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple

from chinese_chess.api import Application
from chinese_chess.config_store import ConfigStore
from chinese_chess.web import make_handler


class WebServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        store = ConfigStore(Path(self.directory.name) / "settings.json")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Application(store)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def request(self, method: str, path: str, body: Any = None) -> Tuple[int, Any]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        encoded = json.dumps(body) if body is not None else None
        headers = {"Content-Type": "application/json"} if encoded else {}
        connection.request(method, path, encoded, headers)
        response = connection.getresponse()
        data = response.read()
        content_type = response.getheader("Content-Type")
        connection.close()
        return response.status, json.loads(data) if content_type.startswith("application/json") else data.decode("utf-8")

    def test_serves_web_ui(self) -> None:
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn('data-tab="board"', body)
        self.assertIn('data-tab="settings"', body)

    def test_real_http_move_round_trip(self) -> None:
        status, body = self.request("POST", "/api/game/move", {"from": 54, "to": 45})
        self.assertEqual(status, 200)
        self.assertEqual(body["turn"], "black")
        status, body = self.request("POST", "/api/game/move", {"from": 54, "to": 53})
        self.assertEqual(status, 422)
        self.assertIn("error", body)

    def test_real_http_config_round_trip(self) -> None:
        status, body = self.request("PUT", "/api/config", {"board": {"show_legal_moves": False}})
        self.assertEqual(status, 200)
        self.assertFalse(body["board"]["show_legal_moves"])

    def test_real_http_pve_ai_move_round_trip(self) -> None:
        status, body = self.request(
            "POST",
            "/api/game/pve",
            {"player_side": "black", "difficulty": "easy", "time_limit_ms": 100},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["mode"], "pve")
        for _ in range(100):
            status, current = self.request("GET", "/api/game")
            if not current["ai_thinking"]:
                break
        self.assertEqual(status, 200)
        self.assertFalse(current["ai_thinking"])
        self.assertEqual(len(current["history"]), 1)
        self.assertEqual(current["turn"], "black")
        self.assertEqual(current["history"][0]["ai"]["difficulty"], "easy")


if __name__ == "__main__":
    unittest.main()
