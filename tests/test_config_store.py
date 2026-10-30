import tempfile
import unittest
from pathlib import Path

from chinese_chess.config_store import ConfigStore


class ConfigStoreTests(unittest.TestCase):
    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = ConfigStore(path)
            store.update({"ai": {"difficulty": "hard"}})
            self.assertEqual(ConfigStore(path).get().ai_difficulty, "hard")

    def test_missing_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "missing.json")
            self.assertEqual(store.get().ai_difficulty, "medium")


if __name__ == "__main__":
    unittest.main()
