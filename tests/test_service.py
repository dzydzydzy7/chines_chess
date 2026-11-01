import unittest

from chinese_chess.service import GameService, ServiceError


class GameServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GameService()

    def test_new_game_returns_serializable_state(self) -> None:
        state = self.service.state()
        self.assertEqual(state["turn"], "red")
        self.assertEqual(state["status"], "playing")
        self.assertEqual(len(state["pieces"]), 32)
        self.assertEqual(state["history"], [])

    def test_legal_move_returns_updated_state(self) -> None:
        state = self.service.move(54, 45)
        self.assertEqual(state["turn"], "black")
        self.assertEqual(len(state["history"]), 1)
        self.assertEqual(state["history"][0], {"from": 54, "to": 45, "captured": None})

    def test_capture_is_recorded_in_history(self) -> None:
        self.service.move(54, 45)
        self.service.move(27, 36)
        state = self.service.move(45, 36)
        self.assertEqual(state["history"][-1]["captured"], "卒")

    def test_illegal_move_does_not_change_game(self) -> None:
        with self.assertRaises(ServiceError):
            self.service.move(54, 53)
        self.assertEqual(self.service.state()["history"], [])

    def test_legal_targets_are_available(self) -> None:
        self.assertEqual(self.service.legal_targets(54), [45])

    def test_reset_clears_history_and_assigns_new_id(self) -> None:
        original_id = self.service.state()["id"]
        self.service.move(54, 45)
        state = self.service.reset()
        self.assertEqual(state["history"], [])
        self.assertEqual(state["turn"], "red")
        self.assertNotEqual(state["id"], original_id)

    def test_undo_restores_captured_piece_turn_and_history(self) -> None:
        self.service.move(54, 45)
        self.service.move(27, 36)
        self.service.move(45, 36)
        state = self.service.undo()
        self.assertEqual(state["turn"], "red")
        self.assertEqual(len(state["history"]), 2)
        pawn = next(piece for piece in state["pieces"] if piece["square"] == 36)
        self.assertEqual(pawn["name"], "卒")

    def test_undo_can_return_to_initial_position_and_then_rejects(self) -> None:
        self.service.move(54, 45)
        state = self.service.undo()
        self.assertEqual(state["history"], [])
        self.assertEqual(len(state["pieces"]), 32)
        with self.assertRaises(ServiceError):
            self.service.undo()


if __name__ == "__main__":
    unittest.main()
