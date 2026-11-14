#!/usr/bin/env python3
"""Pin that both ``klt draw`` negative controls run the *resolved* ``klt``.

``layout/drc/deck_negative_control.py`` and
``layout/ground_rail_negative_control.py`` each draw a deliberately-bad
fixture with ``klt draw``.  Both used to build that argv around the literal
string ``"klt"`` while calling :func:`klt_env.require_klt` purely as a
presence guard and throwing its return value away (issue #451) -- so the
binary the guard approved and the binary that actually ran were the same
thing only by coincidence of ``PATH``.

That matters because these are *negative controls*: their entire claim is
"the same tool that produced the sibling verdict was used here".  The moment
``require_klt`` resolves anything other than what a bare ``PATH`` lookup gives
-- an explicit override, a future ``--klt`` flag like the ERC arms already
take (``layout/erc/run_erc.py``) -- a hardcoded argv silently runs a
*different* ``klt`` and the control's claim stops being true.

The pin is structural rather than textual: it asserts ``argv[0]`` is the path
:func:`klt_env.require_klt` returned, which a grep for the literal cannot do.
Both controls route through :func:`klt_report.run_klt`, so stubbing that one
shared helper both captures the argv and exercises each script's draw-failure
path (``KltRunError`` -> exit 1, via ``GenError`` for the ground-rail one).

Stdlib only: no ``klt`` is executed, no PDK is read, no GDS is written, and
both scripts' ``layout/build/`` scratch is redirected into a temp dir, so this
runs on the PDK-free CI runner and writes nothing into the tree.
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "layout" / "common"))

import klt_env  # noqa: E402  (path set above)
import klt_report  # noqa: E402  (path set above)

#: Deliberately neither a bare ``klt`` nor anything on ``PATH``: if a control
#: ever goes back to hardcoding the literal, the captured argv[0] is ``"klt"``
#: and the assertion below names exactly that regression.
PINNED_KLT = "/nonexistent/pinned-klt-0.0.0/bin/klt"


def _load(relpath: str):
    """Import a ``layout/`` entry point by path (they are scripts, not modules)."""
    path = REPO_ROOT / relpath
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


class ResolvedKltBinaryTest(unittest.TestCase):
    """Each control's ``klt draw`` argv must start with the resolved binary."""

    def _run_capturing_draw(self, module, build_attrs):
        """Call ``module.main()`` with ``klt draw`` stubbed; return (rc, argv)."""
        seen = []

        def fake_run_klt(cwd, argv, ok_codes=(0,)):
            seen.append(list(argv))
            raise klt_report.KltRunError("draw")

        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory())
            stack.enter_context(
                mock.patch.object(klt_env, "require_klt", return_value=PINNED_KLT)
            )
            stack.enter_context(mock.patch.object(klt_report, "run_klt", fake_run_klt))
            for attr, make_value in build_attrs.items():
                stack.enter_context(mock.patch.object(module, attr, make_value(tmp)))
            rc = module.main()

        self.assertEqual(len(seen), 1, "expected exactly one klt draw invocation")
        return rc, seen[0]

    def test_deck_negative_control_draws_with_the_resolved_binary(self):
        module = _load("layout/drc/deck_negative_control.py")
        rc, argv = self._run_capturing_draw(
            module,
            {
                "BUILD_DIR": lambda tmp: Path(tmp),
                "FIXTURE_GDS": lambda tmp: Path(tmp) / "drc-negative-control.gds",
            },
        )
        self.assertEqual(
            argv[0],
            PINNED_KLT,
            "deck_negative_control draws with a klt other than the one "
            "klt_env.require_klt resolved (issue #451)",
        )
        self.assertEqual(argv[1], "draw")
        self.assertEqual(rc, 1, "a failed draw must exit 1, not raise")

    def test_ground_rail_negative_control_draws_with_the_resolved_binary(self):
        module = _load("layout/ground_rail_negative_control.py")
        rc, argv = self._run_capturing_draw(
            module, {"BUILD_DIR": lambda tmp: os.path.join(tmp, "build")}
        )
        self.assertEqual(
            argv[0],
            PINNED_KLT,
            "ground_rail_negative_control draws with a klt other than the one "
            "klt_env.require_klt resolved (issue #451)",
        )
        self.assertEqual(argv[1], "draw")
        self.assertEqual(
            rc, 1, "a failed draw must reach main()'s GenError path and exit 1"
        )


if __name__ == "__main__":
    unittest.main()
