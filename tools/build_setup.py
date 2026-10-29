"""Build the standalone Python ZIP installer from the tracked project files."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT = Path(__file__).resolve().parents[1]
TOP_LEVEL = (
    ".dockerignore", ".env.example", "CONTRIBUTING.md", "Dockerfile", "LICENSE", "README.md", "SECURITY.md",
    "compose.yaml", "compose.smart.yaml", "host-smart-snapshot.py",
    "nas-install.py", "pyproject.toml",
)


def files() -> list[Path]:
    chosen = [PROJECT / name for name in TOP_LEVEL]
    chosen += [path for folder in ("docs", "src", "systemd")
               for path in (PROJECT / folder).rglob("*")
               if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"]
    if any(not path.is_file() for path in chosen):
        raise FileNotFoundError("a required installer file is missing")
    return sorted(chosen)


def build(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(PROJECT / "tools" / "setup_launcher.py", "__main__.py")
        for path in files():
            archive.write(path, str(Path("ugreen-telemetry-mqtt") / path.relative_to(PROJECT)))
    with ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("installer archive failed integrity check")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    build(parser.parse_args().destination)
