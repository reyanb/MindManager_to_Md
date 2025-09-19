"""Build a self-contained Windows executable for the Mindmap converter."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller_run

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_SCRIPT = PROJECT_ROOT / "mindmap_app.py"
DIST_DIR = PROJECT_ROOT / "windows_app" / "dist"
BUILD_DIR = PROJECT_ROOT / "windows_app" / "build"
SPEC_DIR = PROJECT_ROOT / "windows_app"


def find_tkdnd_folder() -> str | None:
    """Return path to tkdnd resources bundled with tkinterdnd2, if present."""
    try:
        import tkinterdnd2  # type: ignore
    except ModuleNotFoundError:
        return None

    base_path = Path(tkinterdnd2.__file__).resolve().parent
    candidates = [
        base_path / "tkdnd2.9",
        base_path / "lib" / "tkdnd2.9",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def build_executable(extra_args: list[str] | None = None) -> None:
    if not APP_SCRIPT.exists():
        raise FileNotFoundError(f"Cannot find app entry point: {APP_SCRIPT}")

    args: list[str] = [
        "--clean",
        "--noconfirm",
        "--windowed",
        f"--name=MindmapToMarkdown",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        f"--specpath={SPEC_DIR}",
    ]

    tkdnd_folder = find_tkdnd_folder()
    if tkdnd_folder:
        destination = "tkdnd2.9"
        args.extend([
            "--add-data",
            f"{tkdnd_folder}{os.pathsep}{destination}",
        ])

    if extra_args:
        args.extend(extra_args)

    args.append(str(APP_SCRIPT))

    pyinstaller_run(args)


if __name__ == "__main__":
    build_executable(sys.argv[1:])
