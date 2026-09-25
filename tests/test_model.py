import unittest

from gktetris.model import Game, HEIGHT, HIDDEN, LOCK_DELAY, MAX_RESETS, Piece, SPAWNS, WIDTH, shape


class GameTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(seed=42)

    def test_seven_bag_and_seed(self):
        other = Game(seed=42)
        sequence = [self.game.active.kind]
        second = [other.active.kind]
        for _ in range(27):
            self.game._spawn()
            other._spawn()
            sequence.append(self.game.active.kind)
            second.append(other.active.kind)
        self.assertEqual(sequence, second)
        for start in range(0, 28, 7):
            self.assertEqual(set(sequence[start:start + 7]), set(SPAWNS))
        self.assertGreaterEqual(len(self.game.queue), 3)

    def test_collision_with_walls_floor_ceiling_and_stack(self):
        for piece in (Piece("O", -2, 0), Piece("O", 8, 0), Piece("O", 3, 19), Piece("O", 3, -3)):
            self.assertFalse(self.game.fits(piece))
        self.assertTrue(self.game.fits(Piece("O", 3, -2)))
        self.game.board[HIDDEN + 4][4] = "J"
        self.assertFalse(self.game.fits(Piece("O", 3, 4)))

    def test_four_rotations_return_each_shape(self):
        for kind in SPAWNS:
            self.game.active = Piece(kind, 3, 4)
            start = set(self.game.active.cells())
            for _ in range(4):
                self.game.rotate()
            self.assertEqual(set(self.game.active.cells()), start)
            self.assertEqual(shape(kind, 4), shape(kind))

    def test_t_piece_kicks_off_left_wall(self):
        self.game.active = Piece("T", -1, 5, 1)
        self.assertTrue(self.game.fits(self.game.active))
        self.assertTrue(self.game.rotate())
        self.assertEqual(self.game.active, Piece("T", 0, 5, 2))

    def test_i_piece_uses_two_column_wall_kick(self):
        self.game.active = Piece("I", -2, 5, 1)
        self.assertTrue(self.game.rotate())
        self.assertEqual(self.game.active, Piece("I", 0, 5, 2))

    def test_floor_kick(self):
        self.game.active = Piece("T", 3, 18)
        self.assertTrue(self.game.rotate())
        self.assertEqual(self.game.active, Piece("T", 2, 17, 1))

    def test_blocked_rotation_does_not_move_piece(self):
        self.game.active = Piece("T", 3, 8)
        cells = set(self.game.active.cells())
        self.game.board = [["J"] * WIDTH for _ in range(HEIGHT + HIDDEN)]
        for x, y in cells:
            self.game.board[y + HIDDEN][x] = None
        before = self.game.active
        self.assertFalse(self.game.rotate())
        self.assertEqual(self.game.active, before)

    def test_hold_is_once_per_placement_and_resets_orientation(self):
        first = self.game.active.kind
        following = self.game.queue[0]
        self.assertTrue(self.game.hold())
        self.assertEqual(self.game.held, first)
        self.assertEqual(self.game.active.kind, following)
        self.assertFalse(self.game.hold())
        self.game.hard_drop()
        current = self.game.active.kind
        self.game.move(-1)
        self.game.rotate()
        self.assertTrue(self.game.hold())
        self.assertEqual(self.game.held, current)
        self.assertEqual(self.game.active, Piece(first))

    def test_hard_drop_matches_ghost_and_locks_immediately(self):
        self.game.active = Piece("T", 3, 2, 1)
        ghost = self.game.landing()
        distance = ghost.y - self.game.active.y
        next_kind = self.game.queue[0]
        self.game.hard_drop()
        self.assertEqual(self.game.score, distance * 2)
        for x, y in ghost.cells():
            self.assertEqual(self.game.board[y + HIDDEN][x], "T")
        self.assertEqual(self.game.active.kind, next_kind)
        self.assertIn("drop", [e.name for e in self.game.drain_events()])

    def prepare_clear(self, count):
        self.game.board = [[None] * WIDTH for _ in range(HEIGHT + HIDDEN)]
        for y in range(HEIGHT - count, HEIGHT):
            self.game.board[y + HIDDEN] = [None if x == 5 else "J" for x in range(WIDTH)]
        self.game.active = Piece("I", 3, 16, 1)

    def test_single_double_triple_and_tetris_score(self):
        for count, points in enumerate((100, 300, 500, 800), start=1):
            with self.subTest(count=count):
                self.game = Game(42)
                self.prepare_clear(count)
                self.game.hard_drop()
                self.assertEqual(self.game.lines, count)
                self.assertEqual(self.game.score, points)
                self.assertEqual(len(self.game.board), HEIGHT + HIDDEN)
                self.assertFalse(any(all(row) for row in self.game.board))
                event = next(e for e in self.game.drain_events() if e.name == "clear")
                self.assertEqual(event.rows, tuple(range(HEIGHT - count, HEIGHT)))

    def test_clear_collapses_rows_above_and_preserves_order(self):
        self.prepare_clear(2)
        self.game.board[HIDDEN + 10][0] = "S"
        self.game.board[HIDDEN + 11][1] = "Z"
        self.game.hard_drop()
        self.assertEqual(self.game.board[HIDDEN + 12][0], "S")
        self.assertEqual(self.game.board[HIDDEN + 13][1], "Z")

    def test_level_transition_scores_at_previous_level(self):
        self.prepare_clear(1)
        self.game.lines = 9
        self.game.hard_drop()
        self.assertEqual((self.game.score, self.game.lines, self.game.level), (100, 10, 2))
        self.assertAlmostEqual(self.game.gravity, 0.8)
        self.prepare_clear(1)
        self.game.hard_drop()
        self.assertEqual(self.game.score, 300)
        self.game.lines = 999
        self.assertEqual(self.game.gravity, 0.08)

    def test_gravity_uses_elapsed_time(self):
        before = self.game.active
        self.game.update(0.99)
        self.assertEqual(self.game.active, before)
        self.game.update(0.01)
        self.assertEqual(self.game.active.y, before.y + 1)

    def test_lock_delay_starts_at_contact(self):
        self.game.active = Piece("O", 3, 17)
        self.game.update(1.25)
        self.assertEqual(self.game.active.y, 18)
        self.assertAlmostEqual(self.game.lock_time, 0.25)
        self.assertFalse(any(any(row) for row in self.game.board))
        self.game.update(0.25)
        self.assertTrue(any(any(row) for row in self.game.board))

    def test_grounded_movement_resets_timer_but_only_fifteen_times(self):
        self.game.active = Piece("O", 3, 18)
        for i in range(MAX_RESETS):
            self.game.update(0.4)
            self.assertTrue(self.game.move(1 if i % 2 == 0 else -1))
            self.assertEqual(self.game.lock_time, 0)
        self.game.update(0.4)
        self.assertTrue(self.game.move(-1))
        self.assertAlmostEqual(self.game.lock_time, 0.4)
        self.game.update(0.1)
        self.assertTrue(any(any(row) for row in self.game.board))

    def test_failed_move_does_not_reset_lock(self):
        self.game.active = Piece("O", -1, 18)
        self.game.update(0.4)
        self.assertFalse(self.game.move(-1))
        self.assertAlmostEqual(self.game.lock_time, 0.4)
        self.assertEqual(self.game.lock_resets, 0)

    def test_blocked_spawn_ends_game(self):
        self.game.board[HIDDEN] = ["Z"] * WIDTH
        self.game._spawn("O")
        self.assertTrue(self.game.over)

    def test_lock_above_board_ends_game(self):
        self.game.board[HIDDEN + 1][4] = "J"
        self.game.active = Piece("O", 3, -1)
        self.assertTrue(self.game.fits(self.game.active))
        self.game.update(LOCK_DELAY)
        self.assertTrue(self.game.over)
        previous = self.game.active
        self.game.hard_drop()
        self.game.hold()
        self.game.move(1)
        self.game.rotate()
        self.game.update(10)
        self.assertEqual(self.game.active, previous)

    def test_piece_cannot_move_through_stack_during_drop(self):
        self.game.active = Piece("O", 3, 0)
        self.game.board[HIDDEN + 10][4] = "Z"
        self.assertEqual(self.game.landing().y, 8)


if __name__ == "__main__":
    unittest.main()
