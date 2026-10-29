"""Bound metadata checks for files shared between the setup and reader containers."""

from __future__ import annotations

from pathlib import Path


class FileChangeGate:
    def __init__(self, path: Path, check_interval: float = 60.0) -> None:
        self.path = path
        self.check_interval = check_interval
        self.next_check_at = 0.0
        self.mtime: int | None = None

    def due(self, now: float, periodic_at: float) -> bool:
        if now < self.next_check_at and now < periodic_at:
            return False
        self.next_check_at = now + self.check_interval
        try:
            mtime = self.path.stat().st_mtime_ns
        except OSError:
            mtime = None
        changed = mtime != self.mtime
        self.mtime = mtime
        return changed or now >= periodic_at
