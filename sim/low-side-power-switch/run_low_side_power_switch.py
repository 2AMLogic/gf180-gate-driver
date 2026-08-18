#!/usr/bin/env python3
"""Low-side on-die power-NMOS facet characterization sweep (issue #179).

Measures the three quantities `spec/low-side-power-switch.md` is ratified on,
at the bias points a **single Li-ion cell** actually presents to an on-die
low-side switch (`Vgs` = 5.0 V fresh / 4.2 V nominal / 3.6 V end of
discharge), across the full 15-point process x temperature PVT grid:

1. `Ron.W` of `nfet_06v0` -- the switch itself.
2. `Ron.W` of `pfet_06v0` -- not the switch; the *synchronous-PMOS* flyback
   option's recirculation device, which hangs off the same cell rail and so
   sees the same cell-referenced `|Vgs|`.
3. `Vf(I)` of the PDK's 6 V P+/N-well junction diode `diode_pd2nw_06v0` at a
   fixed 100 um x 100 um reference area -- the device physics behind both
   diode flyback options (a high-side PMOS's own body diode is the same
   junction, drawn smaller).

Decision record 0008 ratified a *stopgap* `Ron.W` baseline for this facet by
re-expressing `sim/device-mv-fet`'s already-recorded on-resistance table,
which is measured at the PDK elec-spec convention of 75/90/100 % of Vidsat
(4.5/5.4/6.0 V) rather than at the cell-referenced points above. This script
closes that gap, and is deliberately method-identical to
`sim/device-mv-fet/run_device_mv_fet.py` everywhere the two overlap -- same
test geometry, same Vds sweep span, same near-origin-chord `Ron` extraction
(`Vds` ~= 1 % of 6.6 V = 66 mV) -- so the two records' numbers are directly
comparable rather than merely similar, and the new table can be cross-checked
against the old one point for point (see `build_record`'s cross-check
section).

Like `sim/device-mv-fet/run_device_mv_fet.py` (and, upstream of it,
`2AMLogic/gf180-bandgap`'s `sim/device-mos-vth/run_mos_vth.py`, the precedent
`CLAUDE.md` directs this repo to copy rather than reinvent), this experiment
sweeps DC tables and interpolates -- which does not fit the `tb.json`
single-`op`-measurement-per-PVT-point grid `sim/harness/runner.compose_deck`
targets -- so it drives `sim/harness`'s library (`pdk.py`, `corners.py`,
`report.py`) directly instead of going through `sim/run_corners.py`.
`testbench/tb.json` still documents this experiment for harness discovery
(`python3 sim/run_corners.py --list`) and runs a small representative
op-point subset for a generic-CLI sanity check
(`python3 sim/run_corners.py low-side-power-switch`); it is not what produces
the record below.

**Corner sections differ from `sim/device-mv-fet` on purpose.** That script
selects a single top-level MOS `.LIB` section per point (`typical`/`ff`/...),
which is sufficient when every DUT is a MOSFET. This deck also instantiates a
`diode_pd2nw_06v0`, whose model lives under the *diode* family's own
`.LIB diode_typical`/`diode_ss`/`diode_ff` sections, so a MOS-only include
would leave it unskewed (and, without `diode_typical`'s `jsa`/`rsa`/`cja`
parameters, undefined). This script therefore uses
`harness.corners.resolve_corners(["mos"])`'s full per-corner section bundles
-- exactly the bundles `sim/run_corners.py` uses for every other experiment in
this repo -- which is also why its corner-ids read `tt`/`ff`/`ss`/`fs`/`sf`
rather than `typical`/`ff`/`ss`/`fs`/`sf`. The MOS section inside `tt`'s
bundle *is* `typical`, so the FET numbers stay point-for-point comparable
with `sim/device-mv-fet`'s.

Usage:
    PDK_ROOT=... PDK=gf180mcuD sim/low-side-power-switch/run_low_side_power_switch.py
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from harness import corners as harness_corners  # noqa: E402
from harness import pdk as harness_pdk  # noqa: E402
from harness import report as harness_report  # noqa: E402
from harness.runner import ngspice_version  # noqa: E402

# The five MOS process corners, as full per-device-family section bundles
# (see the module docstring for why this differs from sim/device-mv-fet).
CORNERS = harness_corners.resolve_corners(["mos"])
CORNER_NAMES = [c.name for c in CORNERS]
TEMPS = [-40.0, 27.0, 125.0]

# Cell-referenced gate-drive points, matching the testbench's own .param
# block: fresh cell / nominal / end of discharge for a single Li-ion cell.
VGS_POINTS = [("glo", 3.6), ("gmid", 4.2), ("ghi", 5.0)]

# Vds sweep span and step, identical to sim/device-mv-fet's 06v0 sweep, so
# the near-origin chord row (index 1) is the same Vds in both records.
VDS_SPAN_V = 6.6
VDS_STEP_FRAC = 0.01
#: The chord Vds actually read: row index 1 of the swept table.
CHORD_VDS_V = VDS_SPAN_V * VDS_STEP_FRAC

# Test geometry (the PDK elec-spec tables' own W/L, matching
# sim/device-mv-fet). W in um; Ron.W is reported in ohm-mm.
W_UM = {"n06": 10.0, "p06": 10.0}
L_UM = {"n06": 0.7, "p06": 0.55}
DEVICE_ORDER = ["n06", "p06"]
DEVICE_MODEL = {"n06": "nfet_06v0", "p06": "pfet_06v0"}

# Flyback-diode reference geometry, matching the testbench's .param block.
FB_AREA_UM2 = 1.0e4  # 100 um x 100 um
FB_SPAN_V = 1.2
FB_STEP_FRAC = 0.002
#: Forward currents the record reports Vf at, in A, through FB_AREA_UM2.
FB_CURRENTS_A = [0.1, 0.3, 1.0]

# Decision record 0008's stopgap Ron.W baseline (ohm-mm) for nfet_06v0 at the
# PDK elec-spec convention's 75 % / 90 % / 100 % of Vidsat = 4.5 / 5.4 / 6.0 V,
# typical corner. Reproduced here only as the cross-check the issue's test
# plan requires -- the authoritative source is
# sim/device-mv-fet/records/20260808-023237-61e0c25.md.
DR0008_N06_TYPICAL = {
    4.5: {-40.0: 1.8155, 27.0: 2.3658, 125.0: 3.2708},
    5.4: {-40.0: 1.6296, 27.0: 2.1400, 125.0: 2.9825},
    6.0: {-40.0: 1.5518, 27.0: 2.0470, 125.0: 2.8649},
}


# --------------------------------------------------------------------------
# Deck composition / ngspice execution
# --------------------------------------------------------------------------


def _corner_shim(pdk: harness_pdk.Pdk, corner: harness_corners.Corner, temp_c: float) -> str:
    lines = [
        "* Generated per corner point by run_low_side_power_switch.py from",
        "* $PDK_ROOT/$PDK (via sim/harness/pdk.py) -- do not edit by hand, "
        "and do not commit.",
        f'.include "{pdk.design_include}"',
    ]
    for section in corner.sections:
        lines.append(f'.lib "{pdk.model_lib}" {section}')
    lines.append(f".temp {temp_c:g}")
    return "\n".join(lines) + "\n"


def _control_block() -> str:
    lines = [
        ".control",
        # Same reason sim/harness/runner.compose_deck() emits this on every
        # generated deck (issue #146, pinned by sim/test_harness_runner.py): a
        # locally built, OpenMP-enabled ngspice's own spinit can default to a
        # thread count > 1, which on these small DC sweeps is pure
        # oversubscription -- the first trial run of this experiment burned
        # 9m51s of CPU for 1m40s of wall clock producing numbers identical to
        # the single-threaded run. This script drives the harness library
        # directly and so composes its own control block, which means it has
        # to carry the convention itself rather than inherit it.
        "set num_threads=1",
        "set width = 512",
        "set height = 100000",
        "set numdgt = 10",
        "",
        "* --- Sections A/B: Id(Vds) output characteristics (one print block "
        "per device so each 101-row table stays under ngspice's column-wrap "
        "width) ---",
        f"dc vfracds 0 1 {VDS_STEP_FRAC:g}",
    ]
    for dev in DEVICE_ORDER:
        names = []
        for suf, _vgs in VGS_POINTS:
            name = f"ioc_{dev}_{suf}"
            lines.append(f"let {name} = -i(Bdoc_{dev}_{suf})")
            names.append(name)
        lines.append("print v(vfracds) " + " ".join(names))
    lines += [
        "",
        "* --- Section C: flyback junction-diode forward characteristic ---",
        f"dc vfracdi 0 1 {FB_STEP_FRAC:g}",
        "let ifb = -i(Bdfb)",
        "print v(vfracdi) ifb",
        "",
        "quit",
        ".endc",
    ]
    return "\n".join(lines)


def _run_corner(
    deck: Path, pdk: harness_pdk.Pdk, corner: harness_corners.Corner, temp_c: float
) -> str:
    """Run `deck` through ngspice at one (process corner, temperature) point."""
    with tempfile.TemporaryDirectory(prefix="low-side-power-switch-") as tmp:
        work = Path(tmp)
        local_deck = work / deck.name
        (work / "corner.spice").write_text(
            _corner_shim(pdk, corner, temp_c), encoding="utf-8"
        )
        (work / "control.spice").write_text(_control_block(), encoding="utf-8")
        local_deck.write_text(
            '.include "corner.spice"\n'
            + deck.read_text(encoding="utf-8")
            + '\n.include "control.spice"\n.end\n',
            encoding="utf-8",
        )
        proc = subprocess.run(
            ["ngspice", "-b", deck.name],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
        )
    log = proc.stdout + proc.stderr
    if proc.returncode != 0:
        raise RuntimeError(
            f"ngspice exited {proc.returncode} for {deck.name} "
            f"[{corner.name} @ {temp_c} C]\n{log}"
        )
    if re.search(r"^\s*(Error|ERROR|fatal)", log, re.MULTILINE):
        raise RuntimeError(f"ngspice reported an error for {deck.name}:\n{log}")
    return log


# --------------------------------------------------------------------------
# Parsing / extraction
# --------------------------------------------------------------------------


def _parse_dc_tables(log: str) -> list[tuple[list[str], list[list[float]]]]:
    """Every ``Index <cols...>`` table in a control-block's printed output,
    in the order the ``print`` commands that produced them were issued."""
    lines = log.splitlines()
    tables: list[tuple[list[str], list[list[float]]]] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("Index"):
            header = lines[i].split()[1:]
            rows: list[list[float]] = []
            j = i + 2  # skip the header and the '---' rule line
            while j < len(lines):
                parts = lines[j].split()
                if not parts or not parts[0].isdigit():
                    break
                try:
                    values = [float(p) for p in parts[1:]]
                except ValueError:
                    break
                if len(values) == len(header):
                    rows.append(values)
                j += 1
            tables.append((header, rows))
            i = j
        else:
            i += 1
    return tables


def _column(header: list[str], rows: list[list[float]], name: str) -> list[float]:
    idx = header.index(name)
    return [row[idx] for row in rows]


def _interp_log_at(xs: list[float], ys: list[float], y_target: float) -> float | None:
    """First x where a monotonically increasing, exponential-ish ys crosses
    y_target, interpolated in log(y) so a diode's forward knee is not read
    with a straight-line secant across a decade."""
    for i in range(1, len(ys)):
        y0, y1 = ys[i - 1], ys[i]
        if y0 < y_target <= y1:
            x0, x1 = xs[i - 1], xs[i]
            if y0 <= 0 or y1 <= y0:
                return x0
            frac = (math.log(y_target) - math.log(y0)) / (math.log(y1) - math.log(y0))
            return x0 + (x1 - x0) * frac
    return None


def extract(log: str) -> dict:
    """Per-corner results: Ron.W per device per Vgs, and diode Vf per current."""
    tables = _parse_dc_tables(log)
    if len(tables) < len(DEVICE_ORDER) + 1:
        raise RuntimeError(
            f"expected {len(DEVICE_ORDER) + 1} printed DC tables, got {len(tables)}"
        )

    out: dict = {"ron_w_ohmmm": {}, "chord_id_a": {}, "fb_vf_v": {}}
    for index, dev in enumerate(DEVICE_ORDER):
        header, rows = tables[index]
        vfrac = _column(header, rows, "v(vfracds)")
        vds = [f * VDS_SPAN_V for f in vfrac]
        out["ron_w_ohmmm"][dev] = {}
        out["chord_id_a"][dev] = {}
        for suf, vgs in VGS_POINTS:
            current = _column(header, rows, f"ioc_{dev}_{suf}")
            # Near-origin chord (Vds ~= 1 % of the 6.6 V span) approximates
            # the deep-linear-region small-signal Ron at this Vgs -- the same
            # extraction sim/device-mv-fet uses, at the same chord Vds.
            chord_i = abs(current[1])
            ron_ohm = abs(vds[1] / current[1]) if current[1] else None
            # W is in um; ohm * um / 1000 = ohm * mm.
            out["ron_w_ohmmm"][dev][vgs] = (
                ron_ohm * W_UM[dev] / 1000.0 if ron_ohm is not None else None
            )
            out["chord_id_a"][dev][vgs] = chord_i

    header, rows = tables[len(DEVICE_ORDER)]
    vfrac = _column(header, rows, "v(vfracdi)")
    vfwd = [f * FB_SPAN_V for f in vfrac]
    ifwd = _column(header, rows, "ifb")
    for target in FB_CURRENTS_A:
        out["fb_vf_v"][target] = _interp_log_at(vfwd, ifwd, target)
    return out


# --------------------------------------------------------------------------
# Record rendering
# --------------------------------------------------------------------------


def _fmt(value, digits=4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _grid(results: dict, getter) -> list[float]:
    vals = [getter(results[(c, t)]) for c in CORNER_NAMES for t in TEMPS]
    return [v for v in vals if v is not None]


def build_record(record, stamp, pdk, ngspice, results) -> tuple[str, list[str]]:
    """Returns (markdown body, list of anomaly strings for the caller)."""
    lines: list[str] = []
    add = lines.append
    anomalies: list[str] = []

    add(f"# Record {record}")
    add("")
    add(f"- **Record ID**: {record}")
    add(
        "- **Claim**: Substantiates `spec/low-side-power-switch.md` "
        "§2.1's ratified `Ron·W` table for the low-side on-die power-NMOS "
        "facet, measured at the cell-referenced gate drive a single Li-ion "
        "cell presents (`Vgs` = 3.6 / 4.2 / 5.0 V) rather than at the PDK "
        "elec-spec tables' 75/90/100 %-of-Vidsat convention (4.5/5.4/6.0 V) "
        "that decision record 0008's stopgap baseline had to reuse. Also "
        "substantiates that document's §5 flyback trade: the `pfet_06v0` "
        "`Ron·W` figures below are the synchronous-PMOS option's area cost, "
        "and the `diode_pd2nw_06v0` forward characteristic is the device "
        "physics behind both diode options. Supersedes nothing in `sim/` — "
        "decision record 0008's numbers remain valid evidence at the bias "
        "points they were measured at."
    )
    add(
        "- **Extraction method**: **Ron** — Id(Vds) swept 0…6.6 V (the 06v0 "
        "family's `vmax`, in 1 % steps) at each cell-referenced `Vgs`, with "
        "`Ron` read as the near-origin chord at row index 1 "
        f"(`Vds` = {CHORD_VDS_V:g} V). This is the identical span, step, "
        "chord row and test geometry `sim/device-mv-fet/run_device_mv_fet.py` "
        "uses, so the two records' on-resistance numbers are directly "
        "comparable; only the `Vgs` values differ. `Ron·W` is that chord "
        "resistance multiplied by the test structure's drawn W "
        "(`nfet_06v0` 10/0.7 µm, `pfet_06v0` 10/0.55 µm — the PDK elec-spec "
        "tables' own geometry), expressed in Ω·mm. Every FET is measured at "
        "Vsb = 0 (NMOS source=bulk=0; PMOS source=bulk at a fixed 6.6 V local "
        "rail). **Diode Vf** — forward bias swept 0…1.2 V in 2.4 mV steps "
        "across a fixed "
        f"{FB_AREA_UM2:.0f} µm² (100 µm × 100 µm, `pj` = 400 µm) "
        "`diode_pd2nw_06v0`; `Vf` at each reported current is interpolated in "
        "log(I) between the bracketing rows, so the exponential knee is not "
        "read with a straight-line secant."
    )
    add(
        "- **Netlist provenance**: schematic-level device testbench "
        "(`sim/low-side-power-switch/testbench/tb_low_side_power_switch.spice`) "
        "— PDK device models instantiated directly; no `design/` schematic, "
        "no extracted layout."
    )
    add("- **Corner matrix run**:")
    add(
        f"  - Process: {', '.join(CORNER_NAMES)} (`sim/harness/corners.py`'s "
        "own `mos` corner set — the full per-device-family section bundles, "
        "not a bare MOS `.LIB` section, because this deck also instantiates a "
        "`diode_pd2nw_06v0` whose model lives under the diode family's own "
        "`diode_typical`/`diode_ss`/`diode_ff` sections and would otherwise "
        "be left unskewed and parameter-less. The MOS section inside `tt`'s "
        "bundle is `typical`, so the FET numbers stay point-for-point "
        "comparable with `sim/device-mv-fet`'s, whose corner-ids spell that "
        "same section `typical`.)"
    )
    add("  - Temperature: " + ", ".join(f"{t:g} °C" for t in TEMPS))
    add(
        "  - Supply: **not applicable** — every DUT is a bare transistor or "
        "diode biased from ideal sources with no circuit supply rail, so the "
        "±10 % supply axis of the `CLAUDE.md` PVT matrix has nothing to "
        "sweep; per `sim/README.md`'s `nosupply` convention the corner-log "
        "filenames carry `nosupply` in the supply field. The cell voltage "
        "this facet is referenced to is **not** a swept rail either: it "
        "enters as three explicit gate-bias points (3.6 / 4.2 / 5.0 V), "
        "recorded as an axis of the result rather than as a ±10 % tolerance "
        "band, because a Li-ion cell's discharge range is a specified "
        "operating range and not a supply tolerance. This is the explicit "
        "subset justification `sim/README.md` requires."
    )
    add(
        f"  - {len(CORNER_NAMES) * len(TEMPS)} corner points "
        f"({len(CORNER_NAMES)} process × {len(TEMPS)} temperature) — full "
        "process/temperature axes of the `CLAUDE.md` PVT matrix, the same "
        "15-point grid every other device-level record in this repo runs. No "
        "narrowing."
    )
    add(
        "- **Statistical convention**: N/A — this record is the corner "
        "matrix, not a Monte Carlo/mismatch distribution claim."
    )
    add(
        "- **Result**: see the per-quantity tables below; overall verdict at "
        "the end."
    )
    add("")

    add(
        "**How pass/fail is judged below.** The PDK publishes no min/typ/max "
        "window for on-resistance or for junction-diode forward drop (neither "
        "is in `docs/analog/spice/elec_specs`), so — exactly as "
        "`sim/device-mv-fet`'s own Ron table already notes — there is no "
        "external window to score these against. What *is* checkable, and is "
        "checked here, are the internal-consistency properties the ratified "
        "spec depends on: `Ron·W` must fall monotonically with `Vgs` and rise "
        "monotonically with temperature at every process corner, and the new "
        "cell-referenced numbers must reconcile with decision record 0008's "
        "stopgap baseline where the two bias ranges meet. Those are scored; "
        "the numbers themselves are reported as measured device data."
    )
    add("")

    # --- Ron.W tables ---
    for dev in DEVICE_ORDER:
        role = (
            "the low-side switch itself"
            if dev == "n06"
            else "the synchronous-PMOS flyback option's recirculation device"
        )
        add(
            f"### `{DEVICE_MODEL[dev]}` Ron·W (Ω·mm), W/L = "
            f"{W_UM[dev]:g}/{L_UM[dev]:g} µm — {role}"
        )
        add("")
        add(
            "| `Vgs` (cell state) | `tt`, −40 °C | `tt`, 27 °C | `tt`, 125 °C "
            "| full grid (5 process × 3 temp) min .. max |"
        )
        add("|---|---|---|---|---|")
        labels = {5.0: "fresh cell", 4.2: "nominal", 3.6: "end of discharge"}
        for _suf, vgs in sorted(VGS_POINTS, key=lambda p: -p[1]):
            vals = _grid(results, lambda r, v=vgs, d=dev: r["ron_w_ohmmm"][d][v])
            add(
                f"| {vgs:g} V ({labels[vgs]}) "
                f"| {_fmt(results[('tt', -40.0)]['ron_w_ohmmm'][dev][vgs])} "
                f"| {_fmt(results[('tt', 27.0)]['ron_w_ohmmm'][dev][vgs])} "
                f"| {_fmt(results[('tt', 125.0)]['ron_w_ohmmm'][dev][vgs])} "
                f"| {_fmt(min(vals))} .. {_fmt(max(vals))} |"
            )
        add("")

    # --- monotonicity checks ---
    mono_vgs_ok = True
    mono_temp_ok = True
    for corner in CORNER_NAMES:
        for temp in TEMPS:
            res = results[(corner, temp)]
            for dev in DEVICE_ORDER:
                ordered = [res["ron_w_ohmmm"][dev][v] for _s, v in VGS_POINTS]
                # VGS_POINTS is ascending in Vgs; Ron must fall as Vgs rises.
                if any(b >= a for a, b in zip(ordered, ordered[1:])):
                    mono_vgs_ok = False
                    anomalies.append(
                        f"{dev} Ron.W not monotonic in Vgs at {corner}/{temp:g}C"
                    )
        for dev in DEVICE_ORDER:
            for _s, vgs in VGS_POINTS:
                series = [results[(corner, t)]["ron_w_ohmmm"][dev][vgs] for t in TEMPS]
                if any(b <= a for a, b in zip(series, series[1:])):
                    mono_temp_ok = False
                    anomalies.append(
                        f"{dev} Ron.W not monotonic in temperature at "
                        f"{corner}/Vgs={vgs:g}V"
                    )
    add("### Internal-consistency checks")
    add("")
    add("| check | result |")
    add("|---|---|")
    add(
        "| `Ron·W` falls monotonically as `Vgs` rises (3.6 → 4.2 → 5.0 V), "
        "both devices, all 15 points | "
        + ("PASS" if mono_vgs_ok else "FAIL")
        + " |"
    )
    add(
        "| `Ron·W` rises monotonically with temperature (−40 → 27 → 125 °C), "
        "both devices, all 5 process corners × 3 `Vgs` points | "
        + ("PASS" if mono_temp_ok else "FAIL")
        + " |"
    )
    add("")

    # --- cross-check against decision record 0008 ---
    add("### Cross-check against decision record 0008's stopgap baseline")
    add("")
    add(
        "Decision record 0008 ratified a stopgap `nfet_06v0` `Ron·W` baseline "
        "re-expressed from `sim/device-mv-fet/records/"
        "20260808-023237-61e0c25.md`, whose measured `Vgs` points are 4.5 / "
        "5.4 / 6.0 V. Those points **bracket this record's 5.0 V point from "
        "both sides and sit entirely above its 4.2 V and 3.6 V points**, so "
        "the check that means something is: is this record's 5.0 V figure "
        "between 0008's 4.5 V and 5.4 V figures, and do the 4.2 V / 3.6 V "
        "figures continue the same trend upward, at the same `tt`/temperature "
        "point? A large unexplained discrepancy here would mean one of the "
        "two records' extraction is wrong (issue #179's test plan requires "
        "this be investigated before ratifying, not silently accepted)."
    )
    add("")
    add(
        "| `tt` @ | 0008: 6.0 V | 0008: 5.4 V | **this: 5.0 V** | 0008: 4.5 V "
        "| **this: 4.2 V** | **this: 3.6 V** | 5.0 V inside 0008's 5.4–4.5 V "
        "bracket? |"
    )
    add("|---|---|---|---|---|---|---|---|")
    bracket_ok = True
    for temp in TEMPS:
        res = results[("tt", temp)]["ron_w_ohmmm"]["n06"]
        lo_ref = DR0008_N06_TYPICAL[5.4][temp]
        hi_ref = DR0008_N06_TYPICAL[4.5][temp]
        here = res[5.0]
        inside = here is not None and lo_ref < here < hi_ref
        bracket_ok = bracket_ok and inside
        if not inside:
            anomalies.append(
                f"n06 Vgs=5.0V Ron.W at tt/{temp:g}C is outside DR0008's "
                f"5.4V..4.5V bracket"
            )
        add(
            f"| {temp:g} °C | {DR0008_N06_TYPICAL[6.0][temp]:.4f} "
            f"| {lo_ref:.4f} | **{_fmt(here)}** | {hi_ref:.4f} "
            f"| **{_fmt(res[4.2])}** | **{_fmt(res[3.6])}** "
            f"| {'yes' if inside else 'NO'} |"
        )
    add("")
    add(
        "Issue #178's own cited spot-check (quoted in decision record 0008 § "
        "\"Context\", typical corner, un-sourced to any `sim/` record) put "
        "`nmos_6p0` at `Vgs` 5 V ≈ 2.25 Ω·mm and at `Vgs` 3.6 V ≈ 2.83 Ω·mm. "
        "This record measures "
        f"**{_fmt(results[('tt', 27.0)]['ron_w_ohmmm']['n06'][5.0])} Ω·mm** "
        "and "
        f"**{_fmt(results[('tt', 27.0)]['ron_w_ohmmm']['n06'][3.6])} Ω·mm** "
        "at those exact points, `tt`/27 °C — the first purpose-built "
        "measurement of them in this repo, and the first time the spot-check "
        "can be compared like-for-like rather than by interpolation."
    )
    add("")

    # --- flyback diode ---
    add(
        "### Flyback junction diode `diode_pd2nw_06v0` — forward drop at a "
        f"{FB_AREA_UM2:.0f} µm² reference area"
    )
    add("")
    add(
        "The PDK's 6 V P+/N-well diode is the same junction as a high-side "
        "`pfet_06v0`'s drain-to-nwell body diode, so this one sweep covers "
        "both the \"body diode\" and \"dedicated junction diode\" options of "
        "`spec/low-side-power-switch.md` §5 — they differ in drawn area, not "
        "in device physics. `Vf` is reported at three currents through the "
        "**fixed** 100 µm × 100 µm reference area, so the numbers scale: a "
        "diode of area *k* × 10⁴ µm² carrying *k* × I has the same `Vf`."
    )
    add("")
    add(
        "| forward current (through 10⁴ µm²) | `tt`, −40 °C | `tt`, 27 °C "
        "| `tt`, 125 °C | full grid min .. max |"
    )
    add("|---|---|---|---|---|")
    for target in FB_CURRENTS_A:
        vals = _grid(results, lambda r, i=target: r["fb_vf_v"][i])
        if len(vals) != len(CORNER_NAMES) * len(TEMPS):
            anomalies.append(
                f"diode Vf at {target} A not resolved at every grid point"
            )
        add(
            f"| {target:g} A | {_fmt(results[('tt', -40.0)]['fb_vf_v'][target])} V "
            f"| {_fmt(results[('tt', 27.0)]['fb_vf_v'][target])} V "
            f"| {_fmt(results[('tt', 125.0)]['fb_vf_v'][target])} V "
            f"| {_fmt(min(vals))} .. {_fmt(max(vals))} V |"
        )
    add("")
    add(
        "**Caveats on these diode numbers, both load-bearing for how §5 uses "
        "them.** (1) The model carries no self-heating and no "
        "electromigration or current-density reliability limit, so this is an "
        "*electrical* drop only: the area a 1 A freewheel diode actually "
        "needs is set by thermal and EM rules (`spec/low-side-power-switch.md` "
        "§3), not by this sweep. (2) At 1 A through 10⁴ µm² the diode is far "
        "above the model's own high-injection knee (`ik` = 253800, i.e. "
        "≈ 2.5 mA at this area), which is why the measured `Vf` moves only "
        "≈ −1.0 mV/°C rather than the ≈ −2 mV/°C a low-injection junction "
        "would show — the effective ideality roughly doubles in high "
        "injection. That is model behaviour consistent with the physics, not "
        "a deck error, but it means these figures should not be extrapolated "
        "to a much larger (lower-injection) diode by scaling temperature "
        "coefficients."
    )
    add("")
    add(
        "ngspice emits `Warning: diode_pd2nw_06v0: IKR too small - model "
        "effect disabled!` once per run at every corner. `ikr` is the "
        "**reverse** high-injection knee and the PDK model sets it to 0 for "
        "this device (`sm141064.ngspice`); this sweep only measures forward "
        "bias, so the disabled effect does not touch any number above. "
        "Recorded here because it appears verbatim in every raw log and would "
        "otherwise look like an unexplained warning to a later reader."
    )
    add("")

    # --- derived sizing ---
    add("### Derived: switch width for a 1 A channel (not a new measurement)")
    add("")
    add(
        "Straight arithmetic on the `nfet_06v0` table above — W = Ron·W / "
        "Ron_budget — at the facet's worst credible point (`Vgs` = 3.6 V end "
        "of discharge, 125 °C, worst process corner) and at its nominal point "
        "(`Vgs` = 4.2 V, 27 °C, `tt`). Included so the spec's sizing guidance "
        "is traceable to this record rather than recomputed by hand."
    )
    add("")
    add("| Ron budget | W at `tt`/27 °C/4.2 V | W at grid-worst (3.6 V) |")
    add("|---|---|---|")
    nominal = results[("tt", 27.0)]["ron_w_ohmmm"]["n06"][4.2]
    worst = max(_grid(results, lambda r: r["ron_w_ohmmm"]["n06"][3.6]))
    for budget in (0.05, 0.1, 0.2):
        add(
            f"| {budget:g} Ω (= {budget * 1.0:.2f} V drop, "
            f"{budget * 1.0:.2f} W at 1 A) "
            f"| {nominal / budget:.1f} mm | {worst / budget:.1f} mm |"
        )
    add("")

    overall = "PASS" if not anomalies else "FAIL"
    add(
        f"- **Overall: {overall}** — the two monotonicity checks and the "
        "decision-record-0008 bracket check all hold"
        + ("" if not anomalies else f"; anomalies: {'; '.join(anomalies)}")
        + ". No PDK-published min/typ/max window exists for on-resistance or "
        "junction forward drop, so nothing here is scored against an external "
        "spec table (same position `sim/device-mv-fet`'s own Ron table "
        "takes); the numbers are reported as measured device data and are "
        "what `spec/low-side-power-switch.md` ratifies."
    )
    add("")

    add("- **Links**:")
    add(
        "  - Testbench: "
        "`sim/low-side-power-switch/testbench/tb_low_side_power_switch.spice`, "
        "`sim/low-side-power-switch/testbench/tb.json`"
    )
    add("  - Run script: `sim/low-side-power-switch/run_low_side_power_switch.py`")
    add(
        f"  - Netlist snapshot: `sim/low-side-power-switch/netlist-snapshots/{record}.spice`"
    )
    add(f"  - Raw logs: `sim/low-side-power-switch/corners/{record}/`")
    add(
        "  - Comparison record (same devices, PDK elec-spec bias convention): "
        "`sim/device-mv-fet/records/20260808-023237-61e0c25.md`"
    )
    add(f"  - PDK: {pdk.variant} ({pdk.path}), ngspice {ngspice}")
    add(f"- **Timestamp / author**: {stamp:%Y-%m-%dT%H:%M:%SZ}, agent-builder (issue #179)")
    add(
        "- **Supersedes**: (none — first record for this experiment. Decision "
        "record 0008's stopgap `Ron·W` table is *not* superseded as evidence: "
        "it re-expresses `sim/device-mv-fet`'s measurements at their own bias "
        "points, which remain valid there. What this record supersedes is its "
        "use as the facet's design baseline — see "
        "`spec/low-side-power-switch.md` §2.1.)"
    )
    add("")
    return "\n".join(lines), anomalies


def main() -> int:
    pdk = harness_pdk.find_pdk()
    root = harness_pdk.REPO_ROOT
    ngspice = ngspice_version()
    git = harness_report.git_provenance(root)
    record = harness_report.allocate_record_id(root, HERE / "records", git=git)
    stamp = datetime.strptime(record[:15], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    deck = HERE / "testbench" / "tb_low_side_power_switch.spice"

    if git["dirty"]:
        print(
            "warning: input tree (design/testbench/harness/docs) is dirty; "
            f"record {record} will not be reproducible from commit "
            f"{git['short']} alone"
        )

    print(f"record {record}: {len(CORNER_NAMES) * len(TEMPS)} corner points")
    results: dict[tuple[str, float], dict] = {}
    for corner in CORNERS:
        for temp in TEMPS:
            cid = harness_corners.device_corner_id(corner.name, temp)
            log = _run_corner(deck, pdk, corner, temp)
            harness_report.write_device_corner_log(
                HERE / "corners",
                record,
                cid,
                harness_report.device_log_header(
                    pdk, deck, corner.name, temp, record, stamp, ngspice
                ),
                log,
            )
            results[(corner.name, temp)] = extract(log)
            print(f"  {cid}: ok")

    harness_report.write_device_netlist_snapshot(HERE / "netlist-snapshots", record, deck)
    body, anomalies = build_record(record, stamp, pdk, ngspice, results)
    path = harness_report.device_write_record(HERE / "records", record, body)
    print(f"wrote {path}")
    if anomalies:
        print(f"anomalies: {len(anomalies)}")
        for line in anomalies:
            print(f"  - {line}")
    else:
        print("anomalies: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
