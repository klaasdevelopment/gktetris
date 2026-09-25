"""Small, failure-tolerant local preferences file."""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile


@dataclass
class Settings:
    best: int = 0
    muted: bool = False
    music: bool = True


def settings_path() -> Path:
    root = os.environ.get("XDG_CONFIG_HOME")
    base = Path(root) if root and Path(root).is_absolute() else Path.home() / ".config"
    return base / "gktetris" / "settings.json"


def load(path: Path | None = None) -> Settings:
    try:
        data = json.loads((path or settings_path()).read_text())
        if not isinstance(data, dict):
            return Settings()
        return Settings(
            best=data["best"] if type(data.get("best")) is int and data["best"] >= 0 else 0,
            muted=data["muted"] if type(data.get("muted")) is bool else False,
            music=data["music"] if type(data.get("music")) is bool else True,
        )
    except (OSError, ValueError):
        return Settings()


def save(settings: Settings, path: Path | None = None) -> bool:
    target = path or settings_path()
    temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(asdict(settings), stream, indent=2)
            stream.write("\n")
        temporary.replace(target)
        return True
    except OSError:
        return False
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
