"""Access to the vendored, unmodified Dreeve-Automator modules.

The upstream modules import each other by bare name (``import const``), so the
vendored ``src`` folder has to be on ``sys.path``. ``const.py`` derives every
file location from its own position on disk; here we re-root everything that
lives under its ``DATA_FOLDER`` to the configured data directory *before* any
other upstream module is imported, so that ``from const import CONFIG_FILE``
elsewhere picks up the new location without touching upstream code.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import ModuleType

VENDOR_ROOT = Path(__file__).resolve().parent.parent 
VENDOR_SRC = VENDOR_ROOT / "src"

_lock = threading.Lock()
_loaded = False

# Populated by load().
const: ModuleType
configure: ModuleType


def load(data_dir: Path) -> None:
    """Import the upstream modules (once per process) using ``data_dir``."""
    global _loaded, const, configure
    with _lock:
        if _loaded:
            return
        if str(VENDOR_SRC) not in sys.path:
            sys.path.append(str(VENDOR_SRC))
        import const as _const

        _reroot_paths(_const, Path(data_dir).resolve())
        import configure as _configure

        const, configure = _const, _configure
        _loaded = True


def _reroot_paths(module: ModuleType, new_data_dir: Path) -> None:
    old = module.DATA_FOLDER
    for name, value in list(vars(module).items()):
        if isinstance(value, Path) and (value == old or old in value.parents):
            setattr(module, name, new_data_dir / value.relative_to(old))
