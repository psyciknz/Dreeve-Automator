"""Runtime settings, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _number(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    username: str
    password: str
    map_lat: float
    map_lon: float
    map_zoom: int
    max_backups: int

    @property
    def auth_enabled(self) -> bool:
        return bool(self.username and self.password)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.environ.get("DREEVE_UI_DATA_DIR", PROJECT_ROOT / "data")),
            username=os.environ.get("DREEVE_UI_USERNAME", ""),
            password=os.environ.get("DREEVE_UI_PASSWORD", ""),
            map_lat=_number("DREEVE_UI_MAP_LAT", 20.0),
            map_lon=_number("DREEVE_UI_MAP_LON", 0.0),
            map_zoom=int(_number("DREEVE_UI_MAP_ZOOM", 2)),
            max_backups=int(_number("DREEVE_UI_MAX_BACKUPS", 20)),
        )
