#!/usr/bin/env python3
"""Shared ``klt`` prerequisite checks for the ``layout/`` entry points.

Every DRC/ERC/LVS/PEX runner and negative control needs the ``klt`` binary on
``PATH`` and (for the runners) an existing input file. Both failures print one
``error:`` line to stderr and exit 1, which is the prerequisite-failure exit
code those scripts document. Keeping the checks here means the install hint
-- which must point at the *pinned* install guidance in ``layout/README.md``
("Reproducibility: pin the ``klt`` install (#190)") -- lives in one place.

Usage from an entry point::

    REPO_ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(REPO_ROOT / "layout" / "common"))

    import klt_env  # noqa: E402

    klt = klt_env.require_klt()                    # or require_klt(args.klt)
    gds_path = klt_env.resolve_existing(args.gds)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

_INSTALL_HINT = (
    "error: 'klt' not found on PATH. Install a pinned build of "
    "2AMLogic/klayout-tools -- see 'Reproducibility: pin the klt install' "
    "in layout/README.md (an unpinned install can silently change the deck)."
)


def require_klt(override: str | None = None) -> str:
    """Return the ``klt`` path (``override`` wins), or print the hint and exit 1."""
    klt = override or shutil.which("klt")
    if klt is None:
        print(_INSTALL_HINT, file=sys.stderr)
        raise SystemExit(1)
    return klt


def resolve_existing(path: Path) -> Path:
    """Resolve ``path`` against the cwd; print an error and exit 1 if missing."""
    resolved = path if path.is_absolute() else (Path.cwd() / path).resolve()
    if not resolved.exists():
        print(f"error: {resolved} does not exist", file=sys.stderr)
        raise SystemExit(1)
    return resolved
