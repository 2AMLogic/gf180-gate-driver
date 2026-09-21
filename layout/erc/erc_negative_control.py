#!/usr/bin/env python3
"""Prove the committed ``erc_status: clean`` supply-island verdict is not vacuous.

The sibling of ``layout/drc/deck_negative_control.py`` and
``layout/lvs/lvs_negative_control.py``, for the ERC half of the flow. A
supply-island verdict that reads ``clean`` is only evidence if the same
invocation would have *fired* on inputs that are genuinely wrong. This script
produces those controls: it re-grades the **same** committed
``layout/gate_driver_core.gds`` + ``layout/erc-supply-spec.json`` pair through
the same ``klt erc`` contract the sibling verdict used
(``layout/erc/run_erc.py``, issue #238), with two deliberate perturbations --
one per rule the ``clean`` verdict rests on -- and asserts each expected
finding fires, plus one unperturbed companion arm that must stay clean.

Three arms, run as a directed pair-plus-companion so both directions are
pinned (mirroring ``layout/ground_rail_negative_control.py``'s
isolated/shorted pair):

``no-deck`` (variant 1 -- deck dependence)
    the identical spec+GDS graded **without** ``--deck``. The device-blind
    connectivity graph then reads the uvlo bias strings' drawn ``ppolyf_u``
    bodies as wires and must report the FALSE ``erc.supply_short`` between
    ``VDD_DRV`` and ``GND_DRV`` -- the mirror-image artifact documented as
    klayout-tools#2183. This proves the sibling clean verdict is
    deck-subtraction-dependent and that the checker detects that artifact
    class rather than silently passing.
``deck-clean`` (the unperturbed companion)
    the identical spec+GDS **with** ``--deck gf180mcu`` -- byte-identical
    inputs to the sibling verdict -- must grade ``erc_status: clean`` with
    zero findings and the deck's device-marker subtraction engaged
    (``provenance.devices`` carrying ``source: "deck"``). An arm that fired
    here would mean the checker (or the deck) drifted, not the layout.
``phantom-supply`` (variant 2 -- one-island-per-supply discrimination)
    a scratch **spec** copy (the LVS control's perturb-the-reference-side
    precedent -- no GDS editing) declaring a fifth ``nets[]`` supply,
    ``VDD_CONTROL``, that the GDS does not label. Zero label/island matches
    must produce an ``erc.unconnected_net`` finding naming that net, graded
    with ``--deck`` against the unmodified sibling GDS. This proves the
    one-island-per-supply rule actually discriminates, rather than passing
    on any declared net list.

The perturbed spec is written under ``layout/build/`` (git-ignored generator
scratch, ``layout/README.md``) and is byte-reproducible from this script, so
nothing binary needs committing. The **reports** (and one request record per
arm, capturing that arm's inputs -- the ERC analogue of the LVS control's
``*.lvs-request.json``) are committed under
``layout/erc/reports/negative-control/<arm>/``, under the same append-only
rule as the block's own reports, named by the shared
``layout/common/report_id.py`` convention.

``--deck`` requires a klayout-tools build that has it (klayout-tools#2217);
this script accepts ``--klt <path>`` (mirroring ``run_erc.py``) so the
control can run from a specific install without touching the PATH pin, and
every committed report's ``provenance.klt_version`` records the exact build
that produced it. When the resolved ``klt`` predates ``--deck`` the deck arms
fail at the flag error -- that is recorded as a tool-version prerequisite
failure (exit 1), not a control verdict.

``klt erc`` exit codes are NOT pass/fail (docs/cli/erc.md: "Gate on
``status``, not the exit code"): 0 (clean), 3 (violations) and 4 (antenna
``not_checked``) are all successful runs and all record a report; only exit
1/2 (failed to run / usage) are errors. Assertions here target
``erc_status``/``erc_findings`` only -- never the antenna rollup ``status``,
which reads ``not_checked`` because the sibling run deliberately passes no
``--pdk``.

Usage (from the repo root)::

    python3 layout/erc/erc_negative_control.py
    python3 layout/erc/erc_negative_control.py --klt /path/to/klt-with-deck

Exit codes: 0 every arm ruled as it must, 1 any did not (or ``klt`` /
``--deck`` is missing) -- a 1 invalidates the sibling ``erc_status: clean``
report until explained, which is the whole point.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "layout" / "common"))

import report_id  # noqa: E402

BUILD_DIR = REPO_ROOT / "layout" / "build"
REPORTS_ROOT = REPO_ROOT / "layout" / "erc" / "reports" / "negative-control"
GDS = REPO_ROOT / "layout" / "gate_driver_core.gds"
SPEC = REPO_ROOT / "layout" / "erc-supply-spec.json"
PERTURBED_SPEC = BUILD_DIR / "erc-negative-control.spec-phantom-supply.json"
DECK = "gf180mcu"

#: The fifth ``nets[]`` supply the phantom-supply arm declares and the GDS
#: deliberately does not label -- any name absent from the merged GDS's
#: 36/10 text objects probes the zero-match branch of the one-island-per-
#: supply rule.
PHANTOM_NET = "VDD_CONTROL"

#: The two supplies the no-deck arm's FALSE short must name (klayout-tools
#: #2183's mirror-image artifact: the uvlo bias-resistor bodies span both
#: rails, so the device-blind graph merges them).
SHORTED_PAIR = {"VDD_DRV", "GND_DRV"}

#: klt erc exit codes that mean "the run succeeded" -- 0 clean, 3 violations,
#: 4 antenna not_checked. Only 1/2 (failed to run / usage) are errors.
_OK_EXITS = (0, 3, 4)


class ControlError(Exception):
    """A tool prerequisite failed before any verdict could be graded."""


def _run(klt: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [klt, "erc", str(GDS.relative_to(REPO_ROOT)), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _grade_arm(
    klt: str,
    arm: str,
    spec: Path,
    deck: str | None,
) -> tuple[str, dict]:
    """Grade one arm, commit its request record + both report formats, and
    return ``(record_id, payload)``. ``spec`` is the repo-relative spec the
    arm ran with; ``deck`` is the curated deck name or ``None``."""
    reports_dir = REPORTS_ROOT / arm
    reports_dir.mkdir(parents=True, exist_ok=True)
    record_id = report_id.record_id(
        reports_dir, _dt.datetime.now(_dt.timezone.utc), report_id.short_sha(REPO_ROOT)
    )

    request = {
        "arm": arm,
        "layout": {
            "file": str(GDS.relative_to(REPO_ROOT)),
            "deck": deck,
        },
        "spec": {
            "file": str(spec),
            "perturbation": (
                {
                    "kind": "phantom nets[] entry",
                    "entry": {"name": PHANTOM_NET, "kind": "supply"},
                }
                if arm == "phantom-supply"
                else None
            ),
        },
    }
    request_path = reports_dir / f"{record_id}.erc-request.json"
    request_path.write_text(json.dumps(request, indent=2) + "\n")

    invocation = [str(spec)]
    if deck is not None:
        invocation += ["--deck", deck]
    json_proc = _run(klt, *invocation, "--format", "json")
    text_proc = _run(klt, *invocation, "--format", "text")
    if json_proc.returncode not in _OK_EXITS:
        print(json_proc.stdout, json_proc.stderr, file=sys.stderr)
        print(
            f"error: klt erc failed on the '{arm}' arm (exit {json_proc.returncode})",
            file=sys.stderr,
        )
        raise ControlError(arm)

    (reports_dir / f"{record_id}.erc.json").write_text(json_proc.stdout)
    (reports_dir / f"{record_id}.erc.txt").write_text(text_proc.stdout)
    return record_id, json.loads(json_proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--klt",
        help="path to the klt binary (default: 'klt' on PATH)",
    )
    args = parser.parse_args()

    klt = args.klt or shutil.which("klt")
    if klt is None:
        print(
            "error: 'klt' not found on PATH. Install with:\n"
            "  uv tool install git+https://github.com/2AMLogic/klayout-tools\n"
            "(no PyPI release yet -- see layout/README.md)",
            file=sys.stderr,
        )
        return 1

    # Tool-version prerequisite: the deck arms need klt erc's --deck flag
    # (klayout-tools#2217). An installed klt that predates it fails at the
    # flag error, which is a prerequisite failure per the sibling scripts'
    # exit contract -- recorded as such, never as a control verdict.
    help_proc = subprocess.run(
        [klt, "erc", "--help"], capture_output=True, text=True, check=False
    )
    if help_proc.returncode != 0 or "--deck" not in help_proc.stdout:
        print(
            f"error: {klt} 'erc' has no --deck flag (klayout-tools#2217 build "
            "required) -- the deck arms cannot run. Point --klt at a build "
            "that has it (layout/erc/run_erc.py records the same "
            "prerequisite).",
            file=sys.stderr,
        )
        return 1
    if not GDS.exists() or not SPEC.exists():
        print(
            f"error: {GDS} or {SPEC} does not exist", file=sys.stderr,
        )
        return 1

    # The phantom-supply arm's perturbed spec: the committed spec plus one
    # declared supply the GDS does not label. Byte-reproducible scratch under
    # layout/build/ -- the LVS control's perturb-the-spec-side precedent.
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    spec_payload = json.loads(SPEC.read_text())
    spec_payload["nets"] = spec_payload["nets"] + [
        {"name": PHANTOM_NET, "kind": "supply"}
    ]
    PERTURBED_SPEC.write_text(json.dumps(spec_payload, indent=2) + "\n")

    try:
        a_id, no_deck = _grade_arm(klt, "no-deck", SPEC.relative_to(REPO_ROOT), None)
        b_id, deck_clean = _grade_arm(
            klt, "deck-clean", SPEC.relative_to(REPO_ROOT), DECK
        )
        c_id, phantom = _grade_arm(
            klt, "phantom-supply", PERTURBED_SPEC.relative_to(REPO_ROOT), DECK
        )
    except ControlError:
        return 1

    print(f"record ids       : no-deck={a_id} deck-clean={b_id} phantom-supply={c_id}")
    print(f"klt              : {no_deck['provenance']['klt_version']}")
    for name, payload in (
        ("no-deck", no_deck),
        ("deck-clean", deck_clean),
        ("phantom-supply", phantom),
    ):
        print(
            f"{name:<15} : erc_status={payload['erc_status']} "
            f"findings={payload['erc_finding_count']} "
            f"deck={payload['provenance']['deck']!r}"
        )

    failures: list[str] = []

    # Arm 1 -- no-deck: the klayout-tools#2183 mirror-image artifact must
    # fire, naming exactly the two supplies the uvlo bias strings span.
    if no_deck["erc_status"] != "violations":
        failures.append(
            f"expected the no-deck arm to grade 'violations', got "
            f"{no_deck['erc_status']!r}"
        )
    else:
        short_findings = [
            f for f in no_deck["erc_findings"] if f["rule"] == "erc.supply_short"
        ]
        if not any(
            {f["net"], f["other_net"]} == SHORTED_PAIR for f in short_findings
        ):
            failures.append(
                "the no-deck arm did not report the expected erc.supply_short "
                f"between VDD_DRV and GND_DRV: {no_deck['erc_findings']!r}"
            )
        if no_deck["provenance"]["deck"] is not None:
            failures.append("the no-deck arm ran with a deck after all")

    # Arm 2 -- unperturbed companion: byte-identical inputs to the sibling
    # verdict must stay clean, with the deck's subtraction actually engaged.
    if deck_clean["erc_status"] != "clean":
        failures.append(
            f"expected the deck-clean arm to grade 'clean', got "
            f"{deck_clean['erc_status']!r} -- the checker (or the deck) "
            "drifted, not the layout"
        )
    if deck_clean["erc_finding_count"] != 0:
        failures.append(
            f"expected zero findings on the deck-clean arm, got "
            f"{deck_clean['erc_finding_count']}"
        )
    if not any(
        d.get("source") == "deck" for d in deck_clean["provenance"]["devices"]
    ):
        failures.append(
            "the deck-clean arm recorded no deck-sourced device subtraction "
            "(provenance.devices) -- --deck did not engage"
        )

    # Arm 3 -- phantom supply: zero label/island matches must fire
    # erc.unconnected_net naming the declared-but-undrawn net.
    if phantom["erc_status"] != "violations":
        failures.append(
            f"expected the phantom-supply arm to grade 'violations', got "
            f"{phantom['erc_status']!r}"
        )
    else:
        unconnected = [
            f
            for f in phantom["erc_findings"]
            if f["rule"] == "erc.unconnected_net" and f["net"] == PHANTOM_NET
        ]
        if not unconnected:
            failures.append(
                f"the phantom-supply arm did not report erc.unconnected_net "
                f"for {PHANTOM_NET}: {phantom['erc_findings']!r}"
            )

    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if failures:
        print(
            "klt erc did not rule as it must on the known-good/known-bad set "
            "-- the block's own 'erc_status: clean' report is not evidence "
            "until this is explained.",
            file=sys.stderr,
        )
        return 1

    print(
        "ok: dropping the deck re-reports the klayout-tools#2183 "
        "erc.supply_short between VDD_DRV and GND_DRV, a phantom fifth "
        "supply fires erc.unconnected_net, and the unperturbed deck arm "
        "stays clean -- the block's own 'erc_status: clean' verdict is a "
        "real verdict"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
