#!/usr/bin/env python3
"""Run the standalone UVLO comparator/reference PVT trip-voltage sweep (issue #220).

Measures design/uvlo.sch's rising/falling trip voltage, hysteresis, and
lockout response time against spec/decision-records/0001-block-interface-
and-uvlo-parameters.md Decisions 4-5, across the full -40/27/125 degC x
process PVT axis (this cell has no two-rail supply of its own to sweep --
its only supply IS VDD_DRV, the quantity under test -- so the "supply" axis
of CLAUDE.md's PVT matrix is this script's own internal transient ramp of
VDD_DRV, not the harness's +/-10% tied-supply grid; see sim/README.md's
`nosupply` convention).

Like sim/device-mv-fet/run_device_mv_fet.py (the precedent for a campaign
that does not fit sim/harness/runner.compose_deck's single `op`-measurement-
per-PVT-point grid), this experiment drives sim/harness's library (pdk.py,
corners.py, report.py) directly instead of going through sim/run_corners.py.
testbench/tb.json still documents this experiment for harness discovery
(`python3 sim/run_corners.py --list`) and runs a representative op-point
subset for a generic-CLI sanity check
(`python3 sim/run_corners.py uvlo-trip-verification`); it is not what
produces the record below.

Why a transient ramp, not a `.dc` sweep: design/uvlo.sch's comparator is a
regenerative (Schmitt-trigger-style) positive-feedback circuit by design --
that is what creates decision record 0001 Decision 4's hysteresis. A raw
`.dc` sweep asks ngspice to find a *single* nonlinear DC operating point at
each swept value via Newton continuation from the previous point; near a
bistable circuit's actual flip point that continuation becomes numerically
close to singular and requires repeated gmin-stepping recovery at nearly
every point in the transition region, observed directly while developing
this script to take several minutes (or longer) per corner and once
required manual intervention to abort. A slow transient triangle-wave ramp
of VDD_DRV (this script's `_hysteresis_deck`) sidesteps this entirely: the
circuit's own (small, on-die) parasitic capacitances provide the transient
continuity a real hysteretic circuit needs, and the sweep rate (0V -> 6V
over 20us, then back) is many orders of magnitude slower than the
comparator's own bandwidth, so it is quasi-static in every sense that
matters for a trip-voltage measurement. This is standard practice for
characterizing hysteretic comparators and is *not* a shortcut against
decision record 0001's <500ns response-time target, which is measured
separately (`_response_deck`) with a fast (1ns) VDD_DRV step.

Usage:
    PDK_ROOT=... PDK=gf180mcuD sim/uvlo-trip-verification/run_uvlo_trip.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from harness import pdk as harness_pdk  # noqa: E402
from harness import report as harness_report  # noqa: E402
from harness.runner import ngspice_version  # noqa: E402

# gf180mcu top-level MOS `.LIB` sections in sm141064.ngspice -- same five
# names sim/harness/corners.py's module docstring confirms already bundle
# the thick-oxide nfet_06v0/pfet_06v0 corner overlay this cell's devices use.
SECTIONS = ["typical", "ff", "ss", "fs", "sf"]
TEMPS = [-40.0, 27.0, 125.0]

DUT = HERE.parent.parent / "design" / "netlist" / "uvlo.spice"

# decision record 0001 Decision 4/5 targets.
FALLING_TYP = 3.6
FALLING_RANGE = (3.3, 3.9)
RISING_TYP = 3.9
RISING_RANGE = (3.6, 4.2)
HYST_TYP = 0.3
RESPONSE_MAX_S = 500e-9

# Response-time step deck: from a voltage guaranteed above every measured
# corner's rising threshold (issue #220's own PVT sweep found a worst case
# of ~5.11V at ss/-40C) down to one guaranteed below every measured corner's
# falling threshold (worst case ~2.23V at ff/125C), with margin on both ends.
STEP_HIGH_V = 6.0
STEP_LOW_V = 1.8
STEP_EDGE_START_S = 500e-9
STEP_EDGE_END_S = 501e-9
STEP_STOP_S = 2000e-9
OUT_LOW_PROXY_V = 0.5
LOCKOUT_ABS_THRESHOLD_V = 1.5  # see module docstring: well below every
# measured corner's rising/falling voltage (2.2V..5.5V), safely above 0V.


# --------------------------------------------------------------------------
# Deck composition
# --------------------------------------------------------------------------


def _corner_shim(pdk: harness_pdk.Pdk, section: str, temp_c: float) -> str:
    return (
        "* Generated per corner point by run_uvlo_trip.py from\n"
        "* $PDK_ROOT/$PDK (via sim/harness/pdk.py) -- do not edit by hand, "
        "and do not commit.\n"
        f'.include "{pdk.design_include}"\n'
        f'.lib "{pdk.model_lib}" {section}\n'
        f".temp {temp_c:g}\n"
        ".options reltol=1e-4\n"  # sim/README.md's harness-wide transient
        # tolerance convention (issue #156) -- this script bypasses
        # runner.compose_deck so it must apply the same default by hand.
    )


def _dut_fragment() -> str:
    return DUT.read_text(encoding="utf-8")


def _boundary_stimulus() -> str:
    return (
        "* Minimal OUT boundary condition (see testbench/uvlo_trip_tb.spice's\n"
        "* header for why): a weak attempt to hold OUT high, plus a small\n"
        "* gate-load-scale capacitance.\n"
        "rpu VDD_DRV OUT 100k\n"
        "cload OUT GND_DRV 6f\n"
    )


def _hysteresis_deck() -> str:
    return (
        "* Triangle-wave VDD_DRV ramp: 0V -> 6V over 20us, then back to 0V\n"
        "* over another 20us -- quasi-static relative to the comparator's own\n"
        "* bandwidth (see module docstring for why a transient ramp, not a\n"
        "* .dc sweep).\n"
        "vsup VDD_DRV 0 pwl(0 0 20u 6 40u 0)\n"
        "vgnd GND_DRV 0 dc 0\n"
        + _boundary_stimulus()
        + _dut_fragment()
        + "\n.control\n"
        "set num_threads=1\n"
        "tran 10n 40u\n"
        "print v(VDD_DRV) v(ndiv) v(nref)\n"
        "print v(lockout) v(uvlo_ok) v(OUT)\n"
        "quit\n"
        ".endc\n"
    )


def _response_deck() -> str:
    return (
        f"* Fast VDD_DRV step: {STEP_HIGH_V}V (released at every measured\n"
        f"* corner) held until {STEP_EDGE_START_S * 1e9:g}ns, then a "
        f"{(STEP_EDGE_END_S - STEP_EDGE_START_S) * 1e9:g}ns edge down to\n"
        f"* {STEP_LOW_V}V (locked out at every measured corner) -- decision\n"
        "* record 0001 Decision 5's <500ns response-time target.\n"
        f"vsup VDD_DRV 0 pwl(0 {STEP_HIGH_V:g} {STEP_EDGE_START_S:g} {STEP_HIGH_V:g}"
        f" {STEP_EDGE_END_S:g} {STEP_LOW_V:g} {STEP_STOP_S:g} {STEP_LOW_V:g})\n"
        "vgnd GND_DRV 0 dc 0\n"
        + _boundary_stimulus()
        + _dut_fragment()
        + "\n.control\n"
        "set num_threads=1\n"
        "tran 0.05n 2000n\n"
        "print v(VDD_DRV) v(lockout) v(OUT)\n"
        "quit\n"
        ".endc\n"
    )


def _run_corner(body: str, pdk: harness_pdk.Pdk, section: str, temp_c: float, tag: str) -> str:
    """Run `body` (a full deck minus the corner shim) through ngspice."""
    with tempfile.TemporaryDirectory(prefix=f"uvlo-trip-{tag}-") as tmp:
        work = Path(tmp)
        deck = work / f"{tag}.spice"
        deck.write_text(
            f"* uvlo-trip-verification -- {tag} deck\n"
            + _corner_shim(pdk, section, temp_c)
            + body
            + ".end\n",
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
            f"ngspice exited {proc.returncode} for {tag} [{section} @ {temp_c} C]\n{log}"
        )
    if re.search(r"^\s*(Error|ERROR|fatal)", log, re.MULTILINE):
        raise RuntimeError(f"ngspice reported an error for {tag}:\n{log}")
    return log


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def _parse_tables(log: str) -> list[tuple[tuple[str, ...], list[list[float]]]]:
    """Every ``Index <cols...>`` table in a control-block's printed output."""
    lines = log.splitlines()
    tables: list[tuple[tuple[str, ...], list[list[float]]]] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("Index"):
            header = tuple(lines[i].split()[1:])
            rows: list[list[float]] = []
            j = i + 2  # skip header + '---' rule
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


def _merged_series(log: str) -> dict[tuple[str, ...], list[list[float]]]:
    """Merge same-header table chunks (ngspice re-prints the header every
    ``height`` rows in batch-mode ASCII output) into one continuous series
    per distinct header."""
    series: dict[tuple[str, ...], list[list[float]]] = {}
    for header, rows in _parse_tables(log):
        series.setdefault(header, []).extend(rows)
    return series


def _find_cross(xs: list[float], ys: list[float], thresh: float, rising: bool) -> float | None:
    for i in range(1, len(ys)):
        if rising and ys[i - 1] < thresh <= ys[i]:
            x0, x1 = xs[i - 1], xs[i]
            y0, y1 = ys[i - 1], ys[i]
            return x0 if y1 == y0 else x0 + (x1 - x0) * (thresh - y0) / (y1 - y0)
        if not rising and ys[i - 1] > thresh >= ys[i]:
            x0, x1 = xs[i - 1], xs[i]
            y0, y1 = ys[i - 1], ys[i]
            return x0 if y1 == y0 else x0 + (x1 - x0) * (thresh - y0) / (y1 - y0)
    return None


def _interp(xs: list[float], ys: list[float], x: float | None) -> float | None:
    if x is None:
        return None
    for i in range(1, len(xs)):
        if xs[i - 1] <= x <= xs[i]:
            x0, x1 = xs[i - 1], xs[i]
            y0, y1 = ys[i - 1], ys[i]
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return None


def extract_hysteresis(log: str) -> dict:
    series = _merged_series(log)
    t1 = series[("time", "v(vdd_drv)", "v(ndiv)", "v(nref)")]
    t2 = series[("time", "v(lockout)", "v(uvlo_ok)", "v(out)")]
    time1 = [r[0] for r in t1]
    vdd = [r[1] for r in t1]
    time2 = [r[0] for r in t2]
    lockout = [r[1] for r in t2]
    if time1 != time2:
        raise RuntimeError("hysteresis deck: mismatched time axes between print blocks")

    imax = vdd.index(max(vdd))
    lock_up, time_up = lockout[: imax + 1], time1[: imax + 1]
    lock_dn, time_dn = lockout[imax:], time1[imax:]

    # Rising half: lockout starts HIGH (locked out) and falls through the
    # absolute threshold as VDD_DRV climbs past the RISING trip point.
    t_rise = _find_cross(time_up, lock_up, LOCKOUT_ABS_THRESHOLD_V, rising=False)
    # Falling half: lockout starts LOW (released) and rises back through the
    # threshold as VDD_DRV drops past the FALLING trip point.
    t_fall = _find_cross(time_dn, lock_dn, LOCKOUT_ABS_THRESHOLD_V, rising=True)

    v_rise = _interp(time1, vdd, t_rise)
    v_fall = _interp(time1, vdd, t_fall)
    hyst = (v_rise - v_fall) if (v_rise is not None and v_fall is not None) else None
    return {"rising_v": v_rise, "falling_v": v_fall, "hysteresis_v": hyst}


def extract_response(log: str, falling_v: float | None) -> dict:
    if falling_v is None:
        return {"response_s": None, "note": "no falling threshold measured this corner"}
    series = _merged_series(log)
    t = series[("time", "v(vdd_drv)", "v(lockout)", "v(out)")]
    time = [r[0] for r in t]
    vdd = [r[1] for r in t]
    outv = [r[3] for r in t]

    t_vdrv_cross = _find_cross(time, vdd, falling_v, rising=False)
    if t_vdrv_cross is None:
        return {
            "response_s": None,
            "note": f"VDD_DRV step never crossed the measured falling threshold "
            f"({falling_v:.4f}V) -- outside this deck's {STEP_HIGH_V}V..{STEP_LOW_V}V step range",
        }
    # Only look for the OUT crossing after the VDD_DRV edge.
    idx0 = next(i for i, tt in enumerate(time) if tt >= t_vdrv_cross)
    t_out_cross = _find_cross(time[idx0:], outv[idx0:], OUT_LOW_PROXY_V, rising=False)
    if t_out_cross is None:
        return {"response_s": None, "note": "OUT never reached the low proxy level in this deck's window"}
    return {"response_s": t_out_cross - t_vdrv_cross, "note": ""}


# --------------------------------------------------------------------------
# Pass/fail
# --------------------------------------------------------------------------


def _in_range(value: float | None, lo: float, hi: float) -> str:
    if value is None:
        return "ERROR (no crossing found)"
    return "PASS" if lo <= value <= hi else "FAIL"


def _under(value: float | None, limit: float) -> str:
    if value is None:
        return "ERROR (no crossing found)"
    return "PASS" if value <= limit else "FAIL"


def _fmt(value, digits=4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


# --------------------------------------------------------------------------
# Record rendering
# --------------------------------------------------------------------------


def build_record(record, stamp, pdk, ngspice, results) -> tuple[str, dict]:
    lines: list[str] = []
    add = lines.append
    verdicts: dict[tuple[str, float], dict[str, str]] = {}

    add(f"# Record {record}")
    add("")
    add(f"- **Record ID**: {record}")
    add(
        "- **Claim**: Substantiates spec/gate-driver.md Sec.5 (drive-rail UVLO, "
        "in scope for this increment) against the numeric targets ratified by "
        "spec/decision-records/0001-block-interface-and-uvlo-parameters.md "
        "Decisions 4 (trip thresholds/hysteresis) and 5 (response time) -- the "
        "first PVT verification of design/uvlo.sch since it was captured "
        "(issue #220). Every threshold/hysteresis/response-time number in "
        "decision record 0001 was a **design target**, not yet a verified "
        "result, before this record."
    )
    add(
        "- **Extraction method**: **Rising/falling trip voltage and "
        "hysteresis** -- a transient triangle-wave ramp of VDD_DRV (0V -> 6V "
        "over 20us, then back to 0V over another 20us; quasi-static relative "
        "to the comparator's own bandwidth) with `design/netlist/uvlo.spice`'s "
        "internal `lockout` node (the active-high OUT-pulldown-enable signal) "
        f"crossing a fixed {LOCKOUT_ABS_THRESHOLD_V}V absolute level -- well "
        "below every measured corner's trip voltage and safely above 0V, so a "
        "single fixed threshold is valid across the whole grid. A raw `.dc` "
        "sweep was tried first and rejected: this comparator is a regenerative "
        "positive-feedback (Schmitt-trigger) circuit by design (decision record "
        "0001 Decision 4's hysteresis), and a `.dc` sweep's nonlinear-operating-"
        "point continuation becomes numerically close to singular near the "
        "flip point, requiring repeated gmin-stepping recovery at nearly every "
        "point in the transition region -- observed directly while developing "
        "this script to take minutes or longer per corner. See "
        "`run_uvlo_trip.py`'s module docstring for the full account. "
        "**Response time** -- a fast (1ns) VDD_DRV step "
        f"({STEP_HIGH_V}V -> {STEP_LOW_V}V at "
        f"{STEP_EDGE_START_S * 1e9:g}ns), measuring the delay from VDD_DRV "
        "crossing *that corner's own measured falling threshold* (from the "
        f"hysteresis sweep above) to OUT reaching a {OUT_LOW_PROXY_V}V low "
        "proxy level, with a weak (100k) pull-up plus a small (6fF) load "
        "capacitance on OUT standing in for \"something external trying to "
        "hold OUT high\" -- output_stage's own specific drive strength is "
        "arbitrated separately by "
        "`sim/gate-driver-core-drive-with-uvlo/` (issue #220 deliverable 4), "
        "not by this standalone cell."
    )
    add(
        "- **Netlist provenance**: schematic (`design/netlist/uvlo.spice`, "
        "from `design/uvlo.sch`) -- pre-layout, no extracted parasitics."
    )
    add("- **Corner matrix run**:")
    add(
        f"  - Process: {', '.join(SECTIONS)} (the top-level MOS `.LIB` "
        "sections, same five names sim/harness/corners.py's module docstring "
        "confirms already skew the thick-oxide nfet_06v0/pfet_06v0 family "
        "this cell is built from entirely)"
    )
    add("  - Temperature: " + ", ".join(f"{t:g} C" for t in TEMPS))
    add(
        "  - Supply: **VDD_DRV itself is the swept quantity** (0V -> 6V "
        "internal transient ramp per corner point), not a +/-10% tied-supply "
        "grid -- this cell has no independent supply rail to hold at a fixed "
        "tolerance point while VDD_DRV is what is under test. Per "
        "`sim/README.md`'s `nosupply` convention (inherited from "
        "2AMLogic/gf180-bandgap's device-characterization scripts), the "
        "corner-log filenames carry `nosupply` in the supply field. This is "
        "the explicit subset justification `sim/README.md` requires."
    )
    add(
        f"  - {len(SECTIONS) * len(TEMPS)} corner points "
        f"({len(SECTIONS)} process x {len(TEMPS)} temperature) -- full "
        "process/temperature axes of the CLAUDE.md PVT matrix, each "
        "internally sweeping the full VDD_DRV range."
    )
    add("- **Statistical convention**: N/A -- corner matrix, not a Monte Carlo/mismatch claim.")
    add("- **Result**: see the per-corner table below; overall verdict at the end.")
    add("")

    add("### Rising / falling trip voltage, hysteresis, response time")
    add("")
    add(
        "Decision record 0001 Decision 4: falling typ 3.6V / worst-case corner "
        "range 3.3-3.9V; rising typ 3.9V / worst-case corner range 3.6-4.2V; "
        "hysteresis typ 300mV (no stated worst-case *range* for hysteresis, so "
        "it is reported but not scored, matching the convention "
        "`sim/device-mv-fet/run_device_mv_fet.py` uses for Cgg/Cgd/Ron). "
        "Decision 5: response time < 500ns, scored at every corner. Each "
        "point's verdict is **PASS** only if falling AND rising both land "
        "inside their stated worst-case range AND response time is under "
        "500ns; a single measurement outside its bound fails that corner."
    )
    add("")
    add(
        "| corner | falling (V) | rising (V) | hysteresis (V) | response (ns) "
        "| falling verdict | rising verdict | response verdict | corner overall |"
    )
    add("|---|---|---|---|---|---|---|---|---|")
    n_pass = 0
    n_total = 0
    for section in SECTIONS:
        for temp in TEMPS:
            r = results[(section, temp)]
            hv = r["hysteresis"]
            resp = r["response"]
            fv, rv, hy = hv["falling_v"], hv["rising_v"], hv["hysteresis_v"]
            rs = resp["response_s"]
            v_f = _in_range(fv, *FALLING_RANGE)
            v_r = _in_range(rv, *RISING_RANGE)
            v_t = _under(rs, RESPONSE_MAX_S)
            overall = "PASS" if "PASS" == v_f == v_r == v_t else "FAIL"
            verdicts[(section, temp)] = {
                "falling": v_f,
                "rising": v_r,
                "response": v_t,
                "overall": overall,
            }
            n_total += 1
            if overall == "PASS":
                n_pass += 1
            cid = f"{section}_{temp:g}c_nosupply"
            resp_ns = _fmt(rs * 1e9 if rs is not None else None, 1)
            add(
                f"| `{cid}` | {_fmt(fv)} | {_fmt(rv)} | {_fmt(hy)} | {resp_ns} "
                f"| {v_f} | {v_r} | {v_t} | {overall} |"
            )
    add("")
    add(
        f"**{n_pass}/{n_total} corners PASS** all three checks (falling range, "
        "rising range, response time) against decision record 0001 Decisions "
        "4-5's stated worst-case bounds."
    )
    add("")
    add(
        "**Finding (recorded honestly, per CLAUDE.md -- \"agents do not relax "
        "the ratified spec to make results pass\")**: the measured PVT spread "
        "of both thresholds is substantially wider than decision record 0001 "
        "Decision 4's targets, driven primarily by temperature -- the "
        "reference is a single diode-connected `nfet_06v0`'s Vgs (no bandgap, "
        "decision record 0001 Decision 5's own explicit tradeoff), and the "
        "divider's ~5x gain (needed to scale that ~0.7-0.8V reference up into "
        "the 3.3-4.2V trip-voltage range) amplifies the reference's own "
        "temperature/process spread by the same ~5x. See "
        "spec/decision-records/0018-uvlo-comparator-pvt-measurement.md for "
        "the full analysis, the specific corners that violate decision "
        "record 0001's stated worst-case bounds, and the safety implication "
        "(a false-trip risk at the slow/cold corner, where the rising "
        "threshold measured above the drive rail's -10% low-line floor)."
    )
    add("")

    overall_all = "PASS" if n_pass == n_total else "FAIL"
    add(
        f"- **Overall: {overall_all}** ({n_pass}/{n_total} corners pass all "
        "three checks; see spec/decision-records/0018-uvlo-comparator-pvt-"
        "measurement.md for the honest disposition of the failing corners -- "
        "this is not silently relaxed to a passing result)"
    )
    add("")
    add("- **Links**:")
    add("  - Testbench: `sim/uvlo-trip-verification/testbench/tb.json`, `sim/uvlo-trip-verification/testbench/uvlo_trip_tb.spice`")
    add("  - Run script: `sim/uvlo-trip-verification/run_uvlo_trip.py`")
    add(f"  - DUT: `design/netlist/uvlo.spice`")
    add(f"  - Netlist snapshot: `sim/uvlo-trip-verification/netlist-snapshots/{record}.spice`")
    add(f"  - Raw logs: `sim/uvlo-trip-verification/corners/{record}/`")
    add(f"  - PDK: {pdk.variant} ({pdk.path}), ngspice {ngspice}")
    add(f"  - Transient tolerance: reltol=1e-4 (harness default, applied by hand -- see module docstring)")
    add(f"- **Timestamp / author**: {stamp:%Y-%m-%dT%H:%M:%SZ}, agent-builder (issue #220)")
    add("- **Supersedes**: (none -- first record for this claim)")
    add("")
    return "\n".join(lines), verdicts


def main() -> int:
    pdk = harness_pdk.find_pdk()
    root = harness_pdk.REPO_ROOT
    ngspice = ngspice_version()
    git = harness_report.git_provenance(root)
    record = harness_report.allocate_record_id(root, HERE / "records", git=git)
    stamp = datetime.strptime(record[:15], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)

    print(f"record {record}: {len(SECTIONS) * len(TEMPS)} corner points")
    results: dict[tuple[str, float], dict] = {}
    for section in SECTIONS:
        for temp in TEMPS:
            cid = f"{section}_{temp:g}c_nosupply"

            hyst_log = _run_corner(_hysteresis_deck(), pdk, section, temp, "hysteresis")
            hyst = extract_hysteresis(hyst_log)

            resp_log = _run_corner(_response_deck(), pdk, section, temp, "response")
            resp = extract_response(resp_log, hyst["falling_v"])

            combined_log = (
                "==== hysteresis (triangle-wave) deck ====\n"
                + hyst_log
                + "\n\n==== response-time (step) deck ====\n"
                + resp_log
            )
            harness_report.write_device_corner_log(
                HERE / "corners",
                record,
                cid,
                harness_report.device_log_header(pdk, DUT, section, temp, record, stamp, ngspice),
                combined_log,
            )
            results[(section, temp)] = {"hysteresis": hyst, "response": resp}
            print(
                f"  {cid}: falling={_fmt(hyst['falling_v'])} rising={_fmt(hyst['rising_v'])} "
                f"hyst={_fmt(hyst['hysteresis_v'])} "
                f"response={_fmt(resp['response_s'] * 1e9 if resp['response_s'] is not None else None, 1)}ns"
            )

    harness_report.write_device_netlist_snapshot(HERE / "netlist-snapshots", record, DUT)
    body, verdicts = build_record(record, stamp, pdk, ngspice, results)
    path = harness_report.device_write_record(HERE / "records", record, body)
    print(f"wrote {path}")
    n_fail = sum(1 for v in verdicts.values() if v["overall"] != "PASS")
    print(f"verdicts: {n_fail}/{len(verdicts)} corners failing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
