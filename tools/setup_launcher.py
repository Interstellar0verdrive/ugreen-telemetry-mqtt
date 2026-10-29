"""Entry point embedded as __main__.py in the single-file NAS installer."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile


ROOT = "ugreen-telemetry-mqtt/"
REQUIRED = {ROOT + "nas-install.py", ROOT + "compose.yaml", ROOT + "compose.smart.yaml"}


def main() -> int:
    if os.geteuid() != 0 and sys.argv[1:] not in (["--help"], ["-h"]):
        print("Run this installer with sudo on the NAS.", file=sys.stderr)
        return 2
    archive = Path(sys.argv[0]).resolve()
    with ZipFile(archive) as bundle:
        names = bundle.namelist()
        if not REQUIRED.issubset(names) or any(
            not name.startswith(ROOT) or name.startswith("/") or ".." in Path(name).parts
            for name in names if name != "__main__.py"
        ):
            print("Invalid installer archive.", file=sys.stderr)
            return 2
        with tempfile.TemporaryDirectory(prefix="ugreen-telemetry-setup-", dir="/root" if os.geteuid() == 0 else None) as temp:
            bundle.extractall(temp, members=(name for name in names if name != "__main__.py"))
            installer = Path(temp) / ROOT / "nas-install.py"
            return subprocess.run([sys.executable, str(installer), *sys.argv[1:]], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
