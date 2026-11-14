#!/usr/bin/env python3
"""Shared pass/fail epilogue for the ``layout/`` negative controls.

The four negative controls -- ``layout/drc/deck_negative_control.py``,
``layout/lvs/lvs_negative_control.py``, ``layout/erc/erc_negative_control.py``,
``layout/ground_rail_negative_control.py`` -- all end the same way: print
every collected ``FAIL:`` line to stderr, then either explain what those
failures invalidate and exit 1, or state that the sibling report's verdict is
a real one and exit 0. Each control's docstring documents that same exit-code
contract ("0 ... 1 it did not -- a 1 invalidates the sibling report until
explained"); this module is where the contract is actually implemented, once.

This is the verdict half of the skeleton :mod:`klt_report` describes. That
module owns the ``klt``-invocation half and exists so "a runner cannot drift
from its siblings"; the verdict half is what makes these scripts *controls*
rather than runners, and it had four copies, which had already drifted in
where the ``for failure in failures`` loop sat relative to ``if failures``
(issue #468). Identical behaviour, but no two copies could be diffed against
each other -- which is how a real divergence in this same file family (a
hardcoded ``"klt"`` in two of the four) survived until issue #451 found it.
The drift is settled here in the form that reads as "report the failures,
then explain what they invalidate": the loop lives inside the failure branch.

The sentence a failing control prints is this repo's verification contract in
prose (CLAUDE.md: "Verification is the product: no claim without a
testbench"). Four independently-worded copies could each be weakened
independently; one frame with four caller-supplied specifics cannot.

Each caller keeps its own assertion logic and its own wording -- only the
print/return skeleton lives here, so f-string interpolations
(``EXPECTED_RULE``, ``total + 1``) stay at the call site.

Usage from a negative control::

    REPO_ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(REPO_ROOT / "layout" / "common"))

    import control_verdict  # noqa: E402

    ...
    return control_verdict.control_verdict(
        failures,
        invalidates=(
            "The gf180mcu deck did not flag a fixture it must flag -- a "
            "'status: clean' report produced with this deck is not evidence "
            "until this is explained."
        ),
        confirms=(
            f"ok: the gf180mcu deck flagged the known-bad fixture "
            f"({EXPECTED_RULE} x1) -- 'status: clean' on the block is a real "
            f"verdict"
        ),
    )
"""

from __future__ import annotations

import sys
from collections.abc import Sequence


def control_verdict(
    failures: Sequence[str], *, invalidates: str, confirms: str
) -> int:
    """Print a negative control's verdict; return the exit code it owes.

    ``failures`` is the control's collected assertion failures, in the order
    the control appended them (never sorted or deduplicated -- that order is
    how the control means them to be read). ``invalidates`` is the one
    sentence naming the sibling claim those failures take away; ``confirms``
    is the ``ok:`` line stating that the sibling verdict is real.

    Non-empty ``failures``: every ``FAIL: <failure>`` line goes to stderr,
    then ``invalidates``, and the return is ``1``. ``confirms`` is not
    printed -- it is the very claim the failures invalidate.

    Empty ``failures``: ``confirms`` goes to stdout, stderr stays untouched,
    and the return is ``0``.

    The return value is the caller's exit code, so a control's ``main()``
    ends ``return control_verdict.control_verdict(...)``.
    """
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(invalidates, file=sys.stderr)
        return 1

    print(confirms)
    return 0
