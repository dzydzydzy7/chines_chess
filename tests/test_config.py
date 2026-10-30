import unittest

from chinese_chess.config import Config, ConfigValidationError


class ConfigTests(unittest.TestCase):
    def test_default_config_covers_every_project_subsystem(self) -> None:
        config = Config.defaults()
        data = config.to_dict()
        self.assertEqual(set(data), {"board", "ai", "vision", "robot", "system"})
        self.assertTrue(data["board"]["show_legal_moves"])
        self.assertEqual(data["system"]["host"], "0.0.0.0")

    def test_update_replaces_only_known_values(self) -> None:
        config = Config.defaults().updated({"board": {"show_coordinates": False}, "ai": {"time_limit_ms": 1500}})
        self.assertFalse(config.show_coordinates)
        self.assertEqual(config.ai_time_limit_ms, 1500)
        self.assertTrue(config.show_legal_moves)

    def test_rejects_unknown_sections_and_fields(self) -> None:
        with self.assertRaises(ConfigValidationError):
            Config.defaults().updated({"unknown": {}})
        with self.assertRaises(ConfigValidationError):
            Config.defaults().updated({"board": {"unknown": True}})

    def test_validates_values_and_types(self) -> None:
        with self.assertRaises(ConfigValidationError):
            Config.defaults().updated({"ai": {"time_limit_ms": 0}})
        with self.assertRaises(ConfigValidationError):
            Config.defaults().updated({"board": {"show_coordinates": "yes"}})
        with self.assertRaises(ConfigValidationError):
            Config.defaults().updated({"robot": {"speed_percent": 101}})


if __name__ == "__main__":
    unittest.main()
