from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gktetris.storage import Settings, load, save, settings_path


class SettingsTests(unittest.TestCase):
    def test_roundtrip_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "settings.json"
            self.assertEqual(load(path), Settings())
            expected = Settings(best=3200, muted=True, music=False)
            self.assertTrue(save(expected, path))
            self.assertEqual(load(path), expected)
            self.assertEqual(len(list(path.parent.iterdir())), 1)

    def test_malformed_and_wrong_types(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            for contents in ('{', 'null', '[]', '{"best": -1, "muted": "yes", "music": 0}', '{"best": true}'):
                path.write_text(contents)
                self.assertEqual(load(path), Settings())

    def test_unwritable_location_is_tolerated(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "file"
            file.write_text("not a directory")
            self.assertFalse(save(Settings(), file / "settings.json"))

    def test_xdg_location(self):
        with patch.dict("os.environ", {"XDG_CONFIG_HOME": "/tmp/custom-config"}):
            self.assertEqual(settings_path(), Path("/tmp/custom-config/gktetris/settings.json"))
        with patch.dict("os.environ", {"XDG_CONFIG_HOME": "relative"}):
            self.assertEqual(settings_path(), Path.home() / ".config/gktetris/settings.json")
