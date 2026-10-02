import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import unittest
from unittest.mock import patch
import pygame

from gktetris.app import App, SIZE
from gktetris.audio import Audio
from gktetris.model import Game, Piece
from gktetris.storage import Settings


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App(persistent=False, seed=5)

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def setUp(self):
        self.app.game = Game(5)
        self.app.settings = Settings()
        self.app.state = "playing"
        self.app.running = True
        self.app.clear_keys()
        self.app.audio.sync(False, True, True)

    def down(self, key, repeat=False):
        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=key, repeat=repeat))

    def up(self, key):
        self.app.handle(pygame.event.Event(pygame.KEYUP, key=key))

    def test_hard_drop_ignores_held_key_repeat(self):
        self.down(pygame.K_DOWN)
        first_count = sum(bool(cell) for row in self.app.game.board for cell in row)
        self.assertEqual(first_count, 4)
        self.down(pygame.K_DOWN, repeat=True)
        self.down(pygame.K_DOWN)
        self.assertEqual(sum(bool(cell) for row in self.app.game.board for cell in row), first_count)
        self.up(pygame.K_DOWN)
        self.down(pygame.K_DOWN)
        self.assertEqual(sum(bool(cell) for row in self.app.game.board for cell in row), 8)

    def test_horizontal_repeat_and_release(self):
        x = self.app.game.active.x
        self.down(pygame.K_LEFT)
        self.assertEqual(self.app.game.active.x, x - 1)
        self.app.update(0.15)
        self.assertEqual(self.app.game.active.x, x - 1)
        self.app.update(0.011)
        self.assertEqual(self.app.game.active.x, x - 2)
        self.up(pygame.K_LEFT)
        self.app.update(0.2)
        self.assertEqual(self.app.game.active.x, x - 2)

    def test_latest_horizontal_direction_wins(self):
        self.down(pygame.K_LEFT)
        self.down(pygame.K_RIGHT)
        self.app.update(0.17)
        self.assertEqual(self.app.game.active.x, 4)
        self.up(pygame.K_RIGHT)
        self.app.update(0.17)
        self.assertEqual(self.app.game.active.x, 3)

    def test_focus_loss_pauses_and_clears_held_keys(self):
        self.down(pygame.K_LEFT)
        piece = self.app.game.active
        self.app.handle(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.assertEqual(self.app.state, "paused")
        self.assertEqual(self.app.held_keys, [])
        self.app.update(2)
        self.assertEqual(self.app.game.active, piece)
        self.down(pygame.K_RETURN)
        self.assertEqual(self.app.state, "playing")
        self.app.update(0.2)
        self.assertEqual(self.app.game.active, piece)

    def test_pause_rotation_hold_and_restart(self):
        self.app.game.active = Piece("T", 3, 4)
        self.down(pygame.K_UP)
        self.assertEqual(self.app.game.active.rotation, 1)
        self.down(pygame.K_c)
        self.assertEqual(self.app.game.held, "T")
        self.down(pygame.K_p)
        self.assertEqual(self.app.state, "paused")
        self.up(pygame.K_p)
        self.down(pygame.K_p)
        self.assertEqual(self.app.state, "playing")
        self.app.game.score = 1234
        self.app.state = "over"
        self.down(pygame.K_RETURN)
        self.assertEqual(self.app.state, "playing")
        self.assertEqual(self.app.game.score, 0)
        self.assertEqual(self.app.settings.best, 1234)

    def test_escape_pauses_then_exits(self):
        self.down(pygame.K_ESCAPE)
        self.assertEqual(self.app.state, "paused")
        self.up(pygame.K_ESCAPE)
        self.down(pygame.K_ESCAPE)
        self.assertFalse(self.app.running)

    def test_sound_preferences_toggle(self):
        self.down(pygame.K_m)
        self.assertTrue(self.app.settings.muted)
        self.assertTrue(self.app.audio.muted)
        self.down(pygame.K_n)
        self.assertFalse(self.app.settings.music)
        self.up(pygame.K_m)
        self.down(pygame.K_m)
        self.assertFalse(self.app.audio.muted)

    def test_synthesized_audio_plays_on_dummy_device(self):
        self.assertTrue(self.app.audio.available)
        self.assertGreater(self.app.audio.song.get_length(), 10)
        self.assertTrue(self.app.audio.channel.get_busy())
        for name, sound in self.app.audio.sounds.items():
            self.assertGreater(sound.get_length(), 0, name)
            self.app.audio.play(name)

    def test_missing_audio_device_is_nonfatal(self):
        with patch("pygame.mixer.init", side_effect=pygame.error("No audio device")):
            audio = Audio()
        self.assertFalse(audio.available)
        audio.sync(False, True, True)
        audio.play("start")
        audio.close()

    def test_all_screens_render_at_different_sizes(self):
        for size in (SIZE, (800, 600), (1400, 800), (400, 700)):
            pygame.display.set_mode(size, pygame.RESIZABLE)
            with patch("pygame.display.set_mode") as set_mode:
                self.app.handle(pygame.event.Event(pygame.VIDEORESIZE, w=size[0], h=size[1]))
                set_mode.assert_not_called()
            self.assertEqual(self.app.screen.get_size(), size)
            for state in ("ready", "playing", "paused", "over"):
                self.app.state = state
                self.app.render()
        pygame.display.set_mode(SIZE, pygame.RESIZABLE)
