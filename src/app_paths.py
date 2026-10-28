"""Locations of bundled resources and user-writable files.

Running from source, both are the repository root. In a frozen (PyInstaller) build,
bundled resources live in the extraction folder (``sys._MEIPASS``), while files the
user can change or create are kept next to the executable so they persist.
"""
import sys
from pathlib import Path


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def resource_root():
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def user_root():
    return Path(sys.executable).resolve().parent if is_frozen() else resource_root()


def resource_path(*parts):
    """Read-only bundled file or folder."""
    return resource_root().joinpath(*parts)


def user_path(*parts):
    """File or folder the user may edit or that the app writes to."""
    return user_root().joinpath(*parts)


def data_folder(name):
    """Folder such as 'Fixed Points': a copy next to the exe wins over the bundled one."""
    external = user_path(name)
    if is_frozen() and external.is_dir():
        return external
    return resource_path(name)
