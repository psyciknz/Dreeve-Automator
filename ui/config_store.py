"""Reading and writing config.json safely.

* every write is atomic (temp file + ``os.replace``),
* the previous version is copied to ``backups/`` first (pruned to a maximum),
* a *revision* (hash of the file) lets callers detect that the file changed
  underneath them (hand edit, the automator, another browser tab).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

SECRET_SENTINEL = "********"

_BACKUP_RE = re.compile(r"^config-\d{8}-\d{6}(?:-\d+)?\.json$")
_API_KEY_RE = re.compile(r'("dreeve_api_key"\s*:\s*)"(?:[^"\\]|\\.)*"')


class ConfigError(Exception):
    """Base class for store errors."""


class ConfigInvalid(ConfigError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class RevisionConflict(ConfigError):
    pass


class ItemNotFound(ConfigError):
    pass


def default_config() -> dict:
    """What a brand new config.json looks like."""
    return {
        "dreeve_url": "http://localhost:8080",
        "dreeve_api_key": "",
        "refresh_minutes": 5,
        "markers": {},
        "templates": [],
        "route_templates": [],
    }


def redact_text(text: str) -> str:
    """Hide the API key in raw JSON text shown in the browser."""
    return _API_KEY_RE.sub(lambda m: f'{m.group(1)}"{SECRET_SENTINEL}"', text)


def restore_secret_text(text: str, real_key: str) -> str:
    """Put the real API key back if the browser sent the placeholder."""
    return _API_KEY_RE.sub(
        lambda m: m.group(1) + json.dumps(real_key)
        if m.group(0).endswith(f'"{SECRET_SENTINEL}"') else m.group(0),
        text)


def dump(data: Any) -> str:
    return json.dumps(data, indent=4, ensure_ascii=False) + "\n"


class ConfigStore:
    def __init__(
        self,
        path: Path,
        validator: Callable[[dict], None],
        backup_dir: Path | None = None,
        max_backups: int = 20,
    ):
        self.path = Path(path)
        self.backup_dir = Path(backup_dir) if backup_dir else self.path.parent / "backups"
        self.max_backups = max_backups
        self._validator = validator
        self._lock = threading.RLock()

    # ---- reading -------------------------------------------------------
    def exists(self) -> bool:
        return self.path.is_file()

    def read_text(self) -> str:
        try:
            return self.path.read_text(encoding="utf8")
        except FileNotFoundError:
            return ""

    def revision(self) -> str:
        with self._lock:
            try:
                raw = self.path.read_bytes()
            except FileNotFoundError:
                return "none"
            return hashlib.sha256(raw).hexdigest()[:16]

    def mtime(self) -> float | None:
        try:
            return self.path.stat().st_mtime
        except FileNotFoundError:
            return None

    def load(self) -> dict:
        """Parsed config. A missing/empty file yields the default skeleton."""
        with self._lock:
            text = self.read_text()
            if not text.strip():
                return default_config()
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ConfigInvalid(
                    f"config.json is not valid JSON ({exc}). "
                    "Fix it in the Raw JSON editor.") from exc
            if not isinstance(data, dict):
                raise ConfigInvalid("config.json must contain a JSON object.")
            return data

    # ---- writing -------------------------------------------------------
    def _check_revision(self, expected: str | None) -> None:
        if expected is not None and expected != self.revision():
            raise RevisionConflict(
                "config.json changed on disk since this page was loaded. "
                "Reload the page to see the latest version.")

    def update(self, fn: Callable[[dict], Any], expected_revision: str | None = None):
        """Read-modify-write under a lock. ``fn`` mutates the dict in place
        and may return a value; the result is validated before it is saved."""
        with self._lock:
            self._check_revision(expected_revision)
            data = self.load()
            result = fn(data)
            self._validator(data)
            self._write_text(dump(data))
            return result

    def write_text(
        self,
        text: str,
        expected_revision: str | None = None,
        validate: bool = True,
        restore_secret: bool = True,
    ) -> None:
        """Replace the file with ``text`` (used by the raw editor)."""
        with self._lock:
            self._check_revision(expected_revision)
            if restore_secret and SECRET_SENTINEL in text:
                existing = self.load().get("dreeve_api_key", "")
                text = restore_secret_text(text, existing if isinstance(existing, str) else "")
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ConfigInvalid(f"Not valid JSON: {exc}") from exc
            if not isinstance(data, dict):
                raise ConfigInvalid("The config must be a JSON object.")
            if validate:
                self._validator(data)
            self._write_text(text if text.endswith("\n") else text + "\n")

    def _write_text(self, text: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_file() and self.read_text() != text:
            self._backup()
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".config-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, 0o644)
            os.replace(tmp, self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    # ---- backups -------------------------------------------------------
    def _backup(self) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.backup_dir / f"config-{stamp}.json"
        counter = 1
        while target.exists():
            target = self.backup_dir / f"config-{stamp}-{counter}.json"
            counter += 1
        shutil.copy2(self.path, target)
        for old in self._backup_files()[self.max_backups:]:
            with contextlib.suppress(OSError):
                old.unlink()

    def _backup_files(self) -> list[Path]:
        if not self.backup_dir.is_dir():
            return []
        files = [p for p in self.backup_dir.iterdir() if _BACKUP_RE.match(p.name)]
        return sorted(files, key=lambda p: (p.stat().st_mtime, p.name), reverse=True)

    def list_backups(self) -> list[dict]:
        return [
            {"name": p.name, "size": p.stat().st_size, "modified": p.stat().st_mtime}
            for p in self._backup_files()
        ]

    def restore_backup(self, name: str, expected_revision: str | None = None) -> None:
        with self._lock:
            self._check_revision(expected_revision)
            match = next((p for p in self._backup_files() if p.name == name), None)
            if match is None:
                raise ItemNotFound(f"Backup {name!r} not found.")
            self._write_text(match.read_text(encoding="utf8"))
