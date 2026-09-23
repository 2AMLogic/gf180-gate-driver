#!/usr/bin/env python3
"""Reusable folded, cross-row-tied high-``m`` power-device array generator.

Issue #254. A very-high-``m`` multi-finger power device drawn as a single row
is routinely wider on its long axis than the core it has to fit in — the
standard fix is folding the same ``m`` fingers across several physical rows.
The hard part is not the fold, it is tying the folded rows' per-row G/S/D
buses into **one shared net each**, so the folded layout is still
electrically the same ``m``-finger device rather than ``rows`` separate
smaller devices. No generator in this catalog drew one before this module, so
each consumer invented (or failed to invent) it.

Correcting a false impossibility claim (F-018 / F-023)
--------------------------------------------------------

Recorded as FRICTION F-018 (the wrong conclusion) and F-023 (the correction,
with the working scheme and its measured effect) in
``2AMLogic/gf180-drone-fc``.

A single-layer (Metal1-only) scheme was attempted upstream of this issue:
vertical "riser" columns at a fixed X, reaching a farther row's own bus. That
*specific* scheme genuinely does not work — a riser reaching a farther row's
bus also spans, at that same X, the other nets' bus bands in every
unmirrored row it passes over, because gate/source/drain are Y-stacked
within each row (confirmed by drawing it and inspecting the merged Metal1
geometry). From that one failed scheme, the conclusion recorded downstream
was *"cross-row ties need a second routing layer"* — an impossibility claim
from one failed attempt, not a proof, and it propagated as an established
fact into three downstream artifacts.

**The scheme that works, verified against a real ``klt`` install (this
module): mirror alternate rows in Y.** ``klt gen-compose``'s
``blocks[].orientation: "mirror_y"`` (``(x, y) -> (x, -y)``, direction
``90 <-> 270``) flips a row's own gate pad (``mos_array`` always reports it
on the *top* edge, facing ``90``) down to face the row below it. Two such
rows, stacked with a plain gap between them, therefore have their gate pads
facing each other directly across that gap — nothing else is drawn there, so
one plain box merges them into a single polygon, no via needed (``klt gen
mos_array``'s ``gate_contact: true`` puts the gate pad on the *same* metal
role as source/drain, which is what makes a same-layer box a legal tie at
all).  The source and drain pads need no such trick: ``mos_array`` always
reports source on the device's *left* edge (``180``) and drain on its
*right* edge (``0``), and a Y-mirror does not change a horizontal-facing
direction — so source stays on the left and drain stays on the right in
*both* rows, meaning a straight Metal1 run in a channel outside the block's
own left/right edges connects the two rows' source (resp. drain) pads
without ever crossing the other row's own interior. (This differs cosmetically
from the original F-023 write-up's own framing — "nested Y-intervals,
inner net takes the inner trunk column" — because that framing describes a
*shared*-channel routing style; ``mos_array``'s own pad geometry already
separates S/G/D onto three distinct X columns, so no channel-sharing or
nesting trick is needed here. The result is electrically the same thing F-023
reports: the two rows' three buses tie into three single nets, and the two
gate buses are the only pair that ever meets across the inter-row gap.)

Verified against a real ``klt`` install + resolved gf180mcu PDK (not merely
argued): a ``fingers=4`` two-row fold (``m=8`` total) extracts as **eight**
transistors sharing exactly one ``(s, g, d)`` net triple (up to the
source/drain swap a "parallel" folded device's alternating orientation
produces) — one folded ``m=8`` device, not two ``m=4`` devices. A negative
control that skips the tie and gives each row's own G/S/D pads their own
honest per-row label (``G0``/``S0``/``D0``, ``G1``/``S1``/``D1`` — the
*exact* shape the issue reports the untied arrays shipped in) extracts as two
disjoint ``(s, g, d)`` triples instead, which is precisely the regression
:func:`fold_connectivity_verdict` exists to catch (see "Connectivity check"
below) — the untied fold passed every *geometric* assertion that existed
before this module (finger count, bounding box); nothing checked electrical
connectivity across the fold.

The two-row mirror/nest scheme, its cost, and its limit
--------------------------------------------------------

- **Cost**: one dedicated trunk channel of width ``2 * trunk_margin_um``
  (default ``2.0`` um total, one margin on each side) beyond the folded
  block's own left/right edges, plus one ``gap_um`` (default ``4.0`` um,
  matching F-023's own measured cost) of clear vertical space between the two
  rows for the gate tie box and the two side channels' vertical runs to pass
  through.
- **Limit: two rows only.** The nesting/facing property this scheme relies on
  — "the two rows immediately adjacent to a gap have their gate pads facing
  each other, and nothing else is drawn in that gap" — holds for exactly one
  gap, i.e. exactly two rows. A third row has no adjacent gap on one of its
  two sides that is *also* adjacent to a second row's gap, so its own gate
  pad cannot be tied the same way without either (a) a notch-routed
  same-layer scheme (the nearer net's riser needs an explicit gap at every
  farther net's own per-row crossing Y — ``C(nets, 2)`` sets of notches for
  every additional row pair) or (b) a real second routing layer with vias.
  Neither is implemented here: :func:`fold_rows` **raises** for ``rows > 2``
  rather than silently drawing ``rows`` disjoint devices — the exact failure
  mode this issue exists to stop consumers from shipping by accident. This is
  a stated limit of *this generator*, not a re-assertion that no same-layer
  ``rows > 2`` scheme can exist (the "transferable lesson" of issues #254's
  own F-018/F-023 history: an impossibility claim needs a proof, or an
  explicit hedge that it is one attempted scheme, not an exhaustive
  argument).

Usage
-----

::

    python3 layout/common/power_array_folded.py \\
        --w-um 4.0 --l-um 0.6 --fingers 8 --rows 2 --flavor nfet \\
        --voltage-flavor medium_voltage --out-dir /tmp/fold_demo

Needs ``klt`` on ``PATH`` and a resolvable gf180mcu PDK install (see
``layout/README.md``) — same requirement as ``gen_gate_driver_core.py``. The
CLI generates the folded array, then runs :func:`check_fold_connectivity`
against the result and prints PASS/FAIL, so a manual run is also a manual
connectivity proof (open the written GDS in ``klayout``/``klt render`` to see
the mirrored gate buses meet across the inter-row gap with nothing else
drawn there — the exact failure mode F-018 missed).

Connectivity check
-------------------

:func:`fold_connectivity_verdict` is a **pure** function (a ``klt
extract``-shaped dict in, a check record out) exactly like
``check_gate_driver_core.py``'s own ``ground_rail_isolation_verdict`` /
``mim_stack_verdict`` — so its failing directions (a broken tie, a
half-connected fold) are pinned in
``layout/common/test_power_array_folded.py`` against synthetic extraction
facts, the same way those two are pinned against synthetic ``klt components``
/ ``klt extract`` responses rather than against a real broken GDS this repo
would otherwise have to keep around on purpose.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAYOUT_DIR = os.path.dirname(HERE)
sys.path.insert(0, LAYOUT_DIR)

from gen_gate_driver_core import GenError, _klt  # noqa: E402  (path set above)

#: Same default as gen_gate_driver_core.py / check_gate_driver_core.py — the
#: 5-metal gf180mcu Option-D build this repo's own layout flow targets.
DEFAULT_PDK = "gf180mcuD"

#: Vertical clear space between the two rows (F-023's own measured cost),
#: holding the gate tie box and the two side channels' vertical runs.
GAP_UM_DEFAULT = 4.0

#: Horizontal clearance from the folded block's own left/right edge to the
#: source/drain trunk column on that side.
TRUNK_MARGIN_UM_DEFAULT = 1.0

_DIRECTION_MIRROR_Y = {0: 0, 180: 180, 90: 270, 270: 90}


class FoldError(GenError):
    """A folded-array generation or connectivity-check step could not be completed."""


def fold_rows(fingers: int, rows: int) -> list[int]:
    """Split ``fingers`` across ``rows`` physical rows -- ``rows in (1, 2)`` only.

    ``rows=1`` returns ``[fingers]`` (no fold, degrade to a plain single-row
    device -- see the module CLI / :func:`generate`'s own ``rows=1`` path).
    ``rows=2`` requires an even ``fingers`` and returns an **equal** split
    (``[fingers // 2, fingers // 2]``): F-023's own two measured examples (an
    ``m=225``+``m=225`` pair, and a folded clamp's ``m=650``+``m=650`` pair)
    are both equal splits, and an uneven split would give the two rows
    different widths -- breaking the shared S/D/G column alignment this
    scheme's cross-row ties rely on (both rows are generated from the *same*
    ``klt gen mos_array`` params specifically so their ports line up exactly).

    ``rows > 2`` always raises -- see the module docstring's "The two-row
    mirror/nest scheme, its cost, and its limit" section for why, and for
    what a ``rows > 2`` caller needs to implement instead.
    """
    if rows not in (1, 2):
        raise FoldError(
            f"power_array_folded only supports rows=1 or rows=2 today (got "
            f"rows={rows}) -- the two-row mirror/nest tie scheme's "
            f"gate-pads-face-each-other property (F-023) holds for exactly "
            f"one inter-row gap (two rows); a rows>2 request needs a "
            f"notch-routed same-layer scheme or a second routing layer with "
            f"vias, neither of which this generator draws (see the module "
            f"docstring's 'two rows only' limit)"
        )
    if rows == 1:
        if fingers < 1:
            raise FoldError(f"fingers must be >= 1 (got {fingers})")
        return [fingers]
    if fingers < 2 or fingers % 2 != 0:
        raise FoldError(
            f"power_array_folded's two-row scheme only draws an equal split "
            f"across the two rows (fingers must be even and >= 2, got "
            f"fingers={fingers}) -- an uneven split would give the two rows "
            f"different widths, breaking the shared S/D/G trunk-column "
            f"alignment the cross-row ties rely on"
        )
    return [fingers // 2, fingers // 2]


def _mirror_y(x: float, y: float, direction_deg: int) -> tuple[float, float, int]:
    """``klt gen-compose``'s own ``orientation: "mirror_y"`` point transform.

    ``(x, y) -> (x, -y)``, direction ``90 <-> 270``, ``0``/``180`` unchanged --
    see ``klayout-tools`` ``docs/cli/gen-compose.md``'s "Block orientation
    (mirror/rotate, #1166)" section, "Transform semantics" table. Applied here
    purely in Python (no ``klt`` call) so :func:`build_tie_shapes` can compute
    row1's absolute pad coordinates directly, matching exactly what ``klt
    gen-compose`` will draw when the caller places row1 with that same
    orientation.
    """
    return x, -y, _DIRECTION_MIRROR_Y[direction_deg]


def _ports_by_role(report: dict) -> dict[str, dict]:
    """Map a ``mos_array`` report's ``U0_S``/``U0_D``/``U0_G`` ports to s/d/g."""
    roles: dict[str, dict] = {}
    for port in report.get("ports", []):
        suffix = port["name"].rsplit("_", 1)[-1].lower()
        if suffix in ("s", "d", "g"):
            roles[suffix] = port
    missing = {"s", "d", "g"} - set(roles)
    if missing:
        raise FoldError(
            f"row report for {report.get('cell_name')!r} is missing port(s) "
            f"{sorted(missing)}"
        )
    return roles


def row_offset_y(row_report: dict, gap_um: float) -> float:
    """Y-offset for row1 (``mirror_y``-oriented) placed above row0 (offset 0).

    row0 occupies ``[row_report.bbox_um.y0, row_report.bbox_um.y1]``. row1 is
    the *same* report, mirrored in Y about its own local origin (so its local
    bbox becomes ``[-y1, -y0]``) and then translated by this offset so its own
    bottom edge sits ``gap_um`` above row0's own top edge.
    """
    bbox = row_report["bbox_um"]
    return bbox["y1"] + gap_um + bbox["y1"]


def row_pads(
    report: dict, orientation: str, offset_y: float
) -> dict[str, tuple[float, float, int, float, dict]]:
    """One row's S/D/G pad ``(x_um, y_um, direction_deg, width_um, layer)``.

    ``orientation`` is ``"none"`` (row0) or ``"mirror_y"`` (row1) -- the same
    two values a ``klt gen-compose`` ``blocks[].orientation`` field accepts
    for this scheme. Both rows share one X origin (this generator applies no
    X offset or X mirroring between rows), so a role's ``x_um`` is identical
    across rows by construction -- :func:`build_tie_shapes` asserts this
    rather than assuming it.
    """
    if orientation not in ("none", "mirror_y"):
        raise FoldError(f"unsupported row orientation {orientation!r}")
    roles = _ports_by_role(report)
    out: dict[str, tuple[float, float, int, float, dict]] = {}
    for role, port in roles.items():
        x, y, direction = port["x_um"], port["y_um"], port["direction_deg"]
        if orientation == "mirror_y":
            x, y, direction = _mirror_y(x, y, direction)
        out[role] = (x, y + offset_y, direction, port["width_um"], port["layer"])
    return out


def _hbar(layer: list[int], x0: float, x1: float, y: float, width: float) -> dict:
    return {
        "layer": layer,
        "rect_um": [min(x0, x1), y - width / 2.0, max(x0, x1), y + width / 2.0],
    }


def _vbar(layer: list[int], x: float, y0: float, y1: float, width: float) -> dict:
    return {
        "layer": layer,
        "rect_um": [x - width / 2.0, min(y0, y1), x + width / 2.0, max(y0, y1)],
    }


def build_tie_shapes(
    row_report: dict,
    gap_um: float = GAP_UM_DEFAULT,
    trunk_margin_um: float = TRUNK_MARGIN_UM_DEFAULT,
) -> tuple[list[dict], dict, dict, float]:
    """Build the ``klt draw`` cross-row tie shapes for a two-row mirrored fold.

    Returns ``(shapes, row0_pads, row1_pads, offset_y)``. ``shapes`` is a
    ``klt draw`` ``params.shapes`` list: three rectangles per source/drain
    net (a stub from each row's own pad out to a shared trunk column beyond
    the block's left/right edge, plus the trunk column itself) and one plain
    box directly tying the two rows' gate pads across the inter-row gap ("a
    plain box -- nothing else is drawn in that gap", per the module
    docstring). Every shape is on the row's own S/D/G metal layer, which must
    be a single shared layer across all three ports (requires ``mos_array``'s
    ``gate_contact: true`` -- a bare-poly gate lands on a different layer than
    source/drain, and a plain metal box cannot tie a poly gate without a via,
    so that case raises here rather than drawing a silently-non-electrical
    box).
    """
    bbox = row_report["bbox_um"]
    offset_y = row_offset_y(row_report, gap_um)
    row0 = row_pads(row_report, "none", 0.0)
    row1 = row_pads(row_report, "mirror_y", offset_y)

    layers = {(v[4]["layer"], v[4]["datatype"]) for v in (*row0.values(), *row1.values())}
    if len(layers) != 1:
        raise FoldError(
            f"power_array_folded's cross-row tie needs source/drain/gate on "
            f"one shared metal layer to draw a plain-box tie (got layers "
            f"{sorted(layers)}) -- pass gate_contact=True to `klt gen "
            f"mos_array` so the gate pad lands on the same metal role as "
            f"source/drain (a bare-poly gate, gate_contact=False, is on a "
            f"different layer and cannot be tied by a metal box alone)"
        )
    layer = list(next(iter(layers)))

    for role in ("s", "d", "g"):
        x0, x1 = row0[role][0], row1[role][0]
        if x0 != x1:
            raise FoldError(
                f"row0/row1 {role!r} pad x-positions disagree ({x0} vs "
                f"{x1}) -- both rows must come from the *same* mos_array "
                f"report (this function's own contract) for the shared "
                f"trunk columns this scheme relies on to line up"
            )

    trunk_x_left = bbox["x0"] - trunk_margin_um
    trunk_x_right = bbox["x1"] + trunk_margin_um

    sx0, sy0, _sd0, sw0, _sl0 = row0["s"]
    sx1, sy1, _sd1, sw1, _sl1 = row1["s"]
    dx0, dy0, _dd0, dw0, _dl0 = row0["d"]
    dx1, dy1, _dd1, dw1, _dl1 = row1["d"]
    gx0, gy0, _gd0, gw0, _gl0 = row0["g"]
    gx1, gy1, _gd1, gw1, _gl1 = row1["g"]

    shapes = [
        _hbar(layer, trunk_x_left, sx0, sy0, sw0),
        _vbar(layer, trunk_x_left, sy0, sy1, max(sw0, sw1)),
        _hbar(layer, trunk_x_left, sx1, sy1, sw1),
        _hbar(layer, dx0, trunk_x_right, dy0, dw0),
        _vbar(layer, trunk_x_right, dy0, dy1, max(dw0, dw1)),
        _hbar(layer, dx1, trunk_x_right, dy1, dw1),
        _vbar(layer, gx0, gy0, gy1, max(gw0, gw1)),
    ]
    return shapes, row0, row1, offset_y


def generate(
    *,
    w_um: float,
    l_um: float,
    fingers: int,
    rows: int = 2,
    flavor: str = "nfet",
    voltage_flavor: str = "",
    gate_contact: bool = True,
    gap_um: float = GAP_UM_DEFAULT,
    trunk_margin_um: float = TRUNK_MARGIN_UM_DEFAULT,
    pdk: str = DEFAULT_PDK,
    out_dir: str,
    cell_name: str = "power_array_folded",
    net_names: tuple[str, str, str] = ("S", "D", "G"),
) -> dict:
    """Generate a folded, cross-row-tied power array; write GDS(s) to ``out_dir``.

    ``rows=1`` degrades to a plain ``klt gen mos_array`` call (no fold, no
    cross-row tie needed -- documented in the module docstring's "Usage" /
    :func:`fold_rows` sections). This path draws **no net labels** -- same as
    a bare ``klt gen mos_array`` call anywhere else in this catalog (labeling
    is the caller's own wiring step, per ``gen_gate_driver_core.py``'s
    ``Interconnect`` class) -- so :func:`check_fold_connectivity` is only
    meaningful against a ``rows=2`` result; there is no fold to verify
    connectivity across when there is only one row.

    ``rows=2`` draws the two-row mirrored/nested fold
    (:func:`build_tie_shapes`) and composes row0 + row1 + the tie cell with
    ``klt gen-compose``, promoting row0's own S/D/G ports (electrically
    identical to row1's, once tied) as the composed cell's top-level
    ``net_names`` labels.

    Returns a report dict with ``gds_path``/``cell_name``/``bbox_um`` plus
    every parameter used, so a caller (or :func:`check_fold_connectivity`)
    never has to re-derive them.
    """
    if not gate_contact:
        raise FoldError(
            "power_array_folded always needs gate_contact=True -- see "
            "build_tie_shapes()'s docstring for why a bare-poly gate cannot "
            "be tied by a plain metal box"
        )
    per_row = fold_rows(fingers, rows)
    os.makedirs(out_dir, exist_ok=True)
    s_name, d_name, g_name = net_names

    base_params: dict = {
        "w_um": round(w_um, 4),
        "l_um": round(l_um, 4),
        "finger_topology": "parallel",
        "rows": 1,
        "cols": 1,
        "dummy": 0,
        "topology": "array",
        "flavor": flavor,
        "gate_contact": True,
    }
    if voltage_flavor:
        base_params["voltage_flavor"] = voltage_flavor

    if rows == 1:
        params = dict(base_params, fingers=per_row[0])
        gds_path = os.path.join(out_dir, f"{cell_name}.gds")
        report = _klt(
            "gen",
            "mos_array",
            "--pdk",
            pdk,
            "--params",
            json.dumps(params),
            "--cell-name",
            cell_name,
            "-o",
            gds_path,
        )
        roles = _ports_by_role(report)
        return {
            "gds_path": gds_path,
            "cell_name": cell_name,
            "pdk": pdk,
            "rows": 1,
            "fingers": fingers,
            "fingers_per_row": [fingers],
            "w_um": w_um,
            "l_um": l_um,
            "flavor": flavor,
            "voltage_flavor": voltage_flavor,
            "net_names": {"s": s_name, "d": d_name, "g": g_name},
            "bbox_um": report["bbox_um"],
            "ports": {role: roles[role] for role in ("s", "d", "g")},
            "generator_report": report,
        }

    row_fingers = per_row[0]
    row_params = dict(base_params, fingers=row_fingers)
    row_cell_name = f"{cell_name}_row"
    row_gds = os.path.join(out_dir, f"{row_cell_name}.gds")
    row_report = _klt(
        "gen",
        "mos_array",
        "--pdk",
        pdk,
        "--params",
        json.dumps(row_params),
        "--cell-name",
        row_cell_name,
        "-o",
        row_gds,
    )

    shapes, _row0_pads, _row1_pads, offset_y = build_tie_shapes(
        row_report, gap_um=gap_um, trunk_margin_um=trunk_margin_um
    )
    tie_cell_name = f"{cell_name}_tie"
    tie_gds = os.path.join(out_dir, f"{tie_cell_name}.gds")
    tie_report = _klt(
        "draw",
        "--params",
        json.dumps({"shapes": shapes}),
        "--cell-name",
        tie_cell_name,
        "-o",
        tie_gds,
    )

    gds_path = os.path.join(out_dir, f"{cell_name}.gds")
    compose_request = {
        "blocks": [
            {
                "id": "row0",
                "generator_report": row_report,
                "offset_um": {"x": 0.0, "y": 0.0},
            },
            {
                "id": "row1",
                "generator_report": row_report,
                "orientation": "mirror_y",
                "offset_um": {"x": 0.0, "y": offset_y},
            },
            {
                "id": "tie",
                "generator_report": tie_report,
                "offset_um": {"x": 0.0, "y": 0.0},
            },
        ],
        "placement": {
            "strategy": "explicit",
            "order": ["row0", "row1", "tie"],
            "origins_um": {
                "row0": {"x": 0.0, "y": 0.0},
                "row1": {"x": 0.0, "y": offset_y},
                "tie": {"x": 0.0, "y": 0.0},
            },
        },
        "pins": [
            {"net": s_name, "block": "row0", "port": "U0_S"},
            {"net": d_name, "block": "row0", "port": "U0_D"},
            {"net": g_name, "block": "row0", "port": "U0_G"},
        ],
        "options": {"cell_name": cell_name, "output": gds_path},
    }
    compose_request_path = os.path.join(out_dir, f"{cell_name}.compose_request.json")
    with open(compose_request_path, "w", encoding="utf-8") as handle:
        json.dump(compose_request, handle, indent=2)
    compose_report = _klt("gen-compose", compose_request_path)

    return {
        "gds_path": gds_path,
        "cell_name": cell_name,
        "pdk": pdk,
        "rows": 2,
        "fingers": fingers,
        "fingers_per_row": per_row,
        "w_um": w_um,
        "l_um": l_um,
        "flavor": flavor,
        "voltage_flavor": voltage_flavor,
        "gap_um": gap_um,
        "trunk_margin_um": trunk_margin_um,
        "net_names": {"s": s_name, "d": d_name, "g": g_name},
        "bbox_um": compose_report["bbox_um"],
        "compose_report": compose_report,
        "row_report": row_report,
        "tie_report": tie_report,
    }


# --------------------------------------------------------------------------- #
# Connectivity check (AC3): asserts electrical connectivity, not just finger
# count and bounding box -- the untied fold F-018 shipped passed both.
# --------------------------------------------------------------------------- #


def fold_connectivity_verdict(
    extraction: dict, net_names: dict, expected_fingers: int
) -> dict:
    """Pure verdict: does ``extraction`` show one folded device, or ``rows`` disjoint ones?

    ``extraction`` is a ``klt extract --format json`` response shape:
    ``{"devices": [{"nets": {"s": ..., "g": ..., "d": ..., "b": ...}, ...}, ...]}``.
    ``net_names`` is ``{"s": ..., "d": ..., "g": ...}`` -- the three net names
    the fold's cross-row ties are supposed to have merged every row's own pad
    onto (:func:`generate`'s own ``net_names`` argument).

    Asserts:

    - exactly ``expected_fingers`` extracted transistors (one per drawn
      finger, across every row -- a missing/duplicated finger is also a
      finger-count bug, not just a connectivity one);
    - every transistor's gate net is ``net_names["g"]`` (a broken or missing
      gate tie leaves some fingers on a different, or anonymous, net);
    - every transistor's *unordered* source/drain net pair is
      ``{net_names["s"], net_names["d"]}`` (a "parallel" folded device's
      fingers alternate orientation, so source/drain order is not
      meaningful -- same convention ``check_gate_driver_core.py``'s own
      ``devices`` check uses).

    Pure (extraction facts in, check record out) so the untied-fold failing
    direction -- unreachable from a *correct* generated GDS -- is exercised
    in ``test_power_array_folded.py`` against a synthetic extraction dict
    instead, the same pattern ``ground_rail_isolation_verdict``/
    ``mim_stack_verdict`` in ``check_gate_driver_core.py`` already use.
    """
    failures: list[str] = []
    devices = extraction.get("devices", [])

    if len(devices) != expected_fingers:
        failures.append(
            f"expected {expected_fingers} extracted transistors (one per "
            f"drawn finger across every row), got {len(devices)}"
        )

    expected_g = net_names["g"]
    expected_ds = frozenset({net_names["s"], net_names["d"]})

    bad_g = sorted({d["nets"].get("g") for d in devices} - {expected_g})
    if bad_g:
        failures.append(
            f"gate net is not uniformly {expected_g!r} across every finger "
            f"-- also found {bad_g} (the cross-row gate tie is missing, "
            f"broken, or only partially drawn)"
        )

    found_ds_pairs = {frozenset({d["nets"].get("s"), d["nets"].get("d")}) for d in devices}
    bad_ds = sorted(
        (sorted(pair) for pair in found_ds_pairs if pair != expected_ds),
        key=lambda pair: pair,
    )
    if bad_ds:
        failures.append(
            f"source/drain net pair is not uniformly "
            f"{sorted(expected_ds)} across every finger -- also found "
            f"{bad_ds} (the cross-row source/drain tie is missing, broken, "
            f"or only partially drawn -- this is exactly the untied-fold "
            f"regression this check exists to catch: F-018's own arrays "
            f"shipped with honest, but disjoint, per-row G<r>/S<r>/D<r> "
            f"labels instead of one shared net per bus)"
        )

    return {
        "passed": not failures,
        "failures": failures,
        "device_count": len(devices),
        "expected_device_count": expected_fingers,
        "net_names": dict(net_names),
    }


def check_fold_connectivity(
    gds_path: str,
    pdk: str,
    cell_name: str,
    net_names: dict,
    expected_fingers: int,
    deck: str = "gf180mcu",
) -> dict:
    """Run ``klt extract`` on ``gds_path`` and rule with :func:`fold_connectivity_verdict`.

    Only meaningful against a ``rows=2`` :func:`generate` result: a ``rows=1``
    GDS draws no net labels at all (see that function's own docstring), so
    every extracted net there is anonymous and this always reports a failure
    -- expected, not a bug, and the module CLI skips this check automatically
    for a ``rows=1`` run.
    """
    extraction = _klt(
        "extract",
        gds_path,
        "--deck",
        deck,
        "--pdk",
        pdk,
        "--top",
        cell_name,
    )
    return fold_connectivity_verdict(extraction, net_names, expected_fingers)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--w-um", type=float, required=True)
    parser.add_argument("--l-um", type=float, required=True)
    parser.add_argument("--fingers", type=int, required=True)
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--flavor", default="nfet", choices=("nfet", "pfet"))
    parser.add_argument("--voltage-flavor", default="")
    parser.add_argument("--gap-um", type=float, default=GAP_UM_DEFAULT)
    parser.add_argument("--trunk-margin-um", type=float, default=TRUNK_MARGIN_UM_DEFAULT)
    parser.add_argument("--pdk", default=DEFAULT_PDK)
    parser.add_argument("--cell-name", default="power_array_folded")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--skip-check", action="store_true", help="skip the connectivity check")
    args = parser.parse_args(argv)

    try:
        report = generate(
            w_um=args.w_um,
            l_um=args.l_um,
            fingers=args.fingers,
            rows=args.rows,
            flavor=args.flavor,
            voltage_flavor=args.voltage_flavor,
            gap_um=args.gap_um,
            trunk_margin_um=args.trunk_margin_um,
            pdk=args.pdk,
            out_dir=args.out_dir,
            cell_name=args.cell_name,
        )
    except GenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {report['gds_path']} (bbox_um={report['bbox_um']})")

    if args.skip_check:
        return 0

    if report["rows"] == 1:
        print(
            "note: rows=1 draws no net labels (see generate()'s own "
            "docstring) -- skipping the connectivity check, which is only "
            "meaningful for a rows=2 fold"
        )
        return 0

    try:
        verdict = check_fold_connectivity(
            report["gds_path"],
            args.pdk,
            args.cell_name,
            report["net_names"],
            args.fingers,
        )
    except GenError as exc:
        print(f"error: connectivity check could not run: {exc}", file=sys.stderr)
        return 1

    if verdict["passed"]:
        print(
            f"PASS: fold_connectivity -- {verdict['device_count']} fingers, "
            f"one shared (s, g, d) net triple"
        )
        return 0

    print("FAIL: fold_connectivity", file=sys.stderr)
    for failure in verdict["failures"]:
        print(f"  - {failure}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
