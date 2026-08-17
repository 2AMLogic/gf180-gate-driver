#!/usr/bin/env python3
"""Check ``layout/gate_driver_core.gds`` against its source schematic netlist.

Three checks, all run against the *committed* GDS through `klt` -- none of
them reads the generator's internal state, so this is an independent audit of
the stream, not a replay of how it was built:

``devices``
    ``klt extract --deck gf180mcu`` the layout and compare every extracted
    transistor against ``design/netlist/gate_driver_core.spice``, flattened.
    A netlist device with ``m=M`` must appear as exactly ``M`` extracted
    transistors with the same width/length whose gate net and (unordered)
    source/drain net pair match the schematic's.  This is the issue's
    "connectivity/device-count check against the source netlist" -- it is
    deliberately *not* a full LVS run (that is issue #105's scope).

``dnwell_partition``
    ``klt components`` with ``DNWELL`` (12/0) declared both as a conductor and
    as the via that joins it to ``Comp`` (22/0).  Every active region a DNWELL
    polygon overlaps therefore lands in the DNWELL's own component; every
    active region outside it does not.  The check asserts that component holds
    exactly the 5V/6V (``*_06v0``) devices' active regions and that every
    3.3V (``*_03v3``) device's active region is outside it -- DRM 7.2 /
    spec/gate-driver.md 2.4, the "no shared DNWELL" acceptance criterion.

``voltage_domain``
    ``klt layers --flattened`` for the marker layers, plus the
    ``voltage_domain_warnings`` block ``klt extract`` returns.  gf180mcu's
    curated klt deck does not model ``Dualgate`` scoping (klayout-tools #552),
    so every thick-oxide device extracts against the 3.3V model; this check
    records that the marker is drawn and that klt reports the gap, rather than
    pretending the extracted model names mean anything.

Usage::

    python3 layout/check_gate_driver_core.py                 # check the committed GDS
    python3 layout/check_gate_driver_core.py --gds /tmp/x.gds --report /tmp/r.json

Exit code 0 if every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gen_gate_driver_core import (  # noqa: E402  (path set above)
    HERE,
    LV_MODELS,
    MV_MODELS,
    NETLIST_PATH,
    REPO_ROOT,
    TOP_CELL,
    Device,
    GenError,
    _klt,
    _spice_number,
    parse_netlist,
)

L_DNWELL = (12, 0)
L_COMP = (22, 0)
DEFAULT_GDS = os.path.join(HERE, f"{TOP_CELL}.gds")
DEFAULT_PDK = "gf180mcuD"


# --------------------------------------------------------------------------- #
# Extracted-netlist parsing
# --------------------------------------------------------------------------- #

_PARAM_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\S+)")


def _device_key(flavor: str, w_um: float, l_um: float, gate: str, ds: frozenset) -> tuple:
    return (flavor, round(w_um, 3), round(l_um, 3), gate, ds)


def expected_devices(devices: list[Device]) -> collections.Counter:
    """Multiset of transistors the schematic calls for (``m`` expanded)."""
    expected: collections.Counter = collections.Counter()
    for device in devices:
        expected[
            _device_key(
                device.flavor, device.w_um, device.l_um, device.g, frozenset({device.d, device.s})
            )
        ] += device.fingers
    return expected


def extracted_devices(spice_path: str) -> collections.Counter:
    """Multiset of transistors ``klt extract`` found in the layout.

    KLayout writes a 4-terminal MOS as ``X<id> <t1> <gate> <t3> <bulk>
    <model>``; ``t1``/``t3`` are the drain/source pair, whose order is not
    meaningful for a symmetric MOS (a folded device alternates them finger to
    finger), so they are compared as an unordered pair.
    """
    lines: list[str] = []
    with open(spice_path, encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.strip()
            if not stripped or stripped.startswith("*"):
                continue
            if stripped.startswith("+"):
                if lines:
                    lines[-1] += " " + stripped[1:].strip()
                continue
            lines.append(stripped)

    found: collections.Counter = collections.Counter()
    for line in lines:
        if not line.upper().startswith("X"):
            continue
        tokens = line.split()
        if len(tokens) < 6:
            continue
        nets = [token.replace("\\", "") for token in tokens[1:5]]
        model = tokens[5]
        if not (model.startswith("nfet") or model.startswith("pfet")):
            continue
        params = dict(_PARAM_RE.findall(" ".join(tokens[6:])))
        flavor = "pfet" if model.startswith("pfet") else "nfet"
        found[
            _device_key(
                flavor,
                _spice_number(params["W"]) * 1e6,
                _spice_number(params["L"]) * 1e6,
                nets[1],
                frozenset({nets[0], nets[2]}),
            )
        ] += 1
    return found


def _describe(key: tuple) -> str:
    flavor, w_um, l_um, gate, ds = key
    return f"{flavor} W={w_um}u L={l_um}u g={gate} d/s={{{', '.join(sorted(ds))}}}"


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #


def check_devices(gds: str, pdk: str, devices: list[Device], work_dir: str) -> dict:
    spice_path = os.path.join(work_dir, f"{TOP_CELL}.extracted.spice")
    report = _klt(
        "extract",
        gds,
        "--deck",
        "gf180mcu",
        "--pdk",
        pdk,
        "--top",
        TOP_CELL,
        "-o",
        spice_path,
    )
    expected = expected_devices(devices)
    found = extracted_devices(spice_path)
    missing = expected - found
    extra = found - expected
    return {
        "name": "devices",
        "passed": not missing and not extra,
        "netlist_devices": len(devices),
        "expected_transistors": sum(expected.values()),
        "extracted_transistors": sum(found.values()),
        "extracted_device_counts": report.get("device_counts"),
        "extracted_net_count": report.get("net_count"),
        "extracted_netlist": os.path.relpath(spice_path, REPO_ROOT)
        if spice_path.startswith(REPO_ROOT)
        else spice_path,
        "missing": [{"device": _describe(k), "count": v} for k, v in missing.items()],
        "unexpected": [{"device": _describe(k), "count": v} for k, v in extra.items()],
        "extract_report": report,
    }


def check_dnwell_partition(gds: str, devices: list[Device]) -> dict:
    """Assert the 3.3V and 5V/6V devices never share a DNWELL (DRM 7.2)."""
    response = _klt(
        "components",
        gds,
        "--top",
        TOP_CELL,
        "--conductors",
        json.dumps(
            [
                {"name": "dnwell", "layer": list(L_DNWELL)},
                {"name": "active", "layer": list(L_COMP)},
            ]
        ),
        "--vias",
        json.dumps(
            [
                {
                    "name": "active_in_dnwell",
                    "layer": list(L_DNWELL),
                    "between": ["dnwell", "active"],
                }
            ]
        ),
    )

    def counts(component: dict) -> dict[str, int]:
        return {
            conductor["name"]: conductor.get("shape_count", 0)
            for conductor in component.get("conductors", [])
        }

    components = response.get("components", [])
    in_dnwell = [c for c in components if counts(c).get("dnwell", 0) > 0]
    outside = [c for c in components if counts(c).get("dnwell", 0) == 0]

    mv_devices = [d for d in devices if d.model in MV_MODELS]
    lv_devices = [d for d in devices if d.model in LV_MODELS]
    unknown = [d.model for d in devices if d.model not in MV_MODELS | LV_MODELS]

    active_in_dnwell = sum(counts(c).get("active", 0) for c in in_dnwell)
    active_outside = sum(counts(c).get("active", 0) for c in outside)

    failures: list[str] = []
    if unknown:
        failures.append(f"device model(s) not classified as 3.3V or 5V/6V: {sorted(set(unknown))}")
    if len(in_dnwell) != 1:
        failures.append(f"expected exactly one DNWELL region, found {len(in_dnwell)}")
    if active_in_dnwell != len(mv_devices):
        failures.append(
            f"{active_in_dnwell} active region(s) inside DNWELL, expected "
            f"{len(mv_devices)} (one per 5V/6V device)"
        )
    if active_outside != len(lv_devices):
        failures.append(
            f"{active_outside} active region(s) outside every DNWELL, expected "
            f"{len(lv_devices)} (one per 3.3V device)"
        )
    return {
        "name": "dnwell_partition",
        "passed": not failures,
        "dnwell_regions": len(in_dnwell),
        "mv_devices": len(mv_devices),
        "lv_devices": len(lv_devices),
        "active_regions_in_dnwell": active_in_dnwell,
        "active_regions_outside_dnwell": active_outside,
        "dnwell_bbox_um": in_dnwell[0]["bbox_um"] if in_dnwell else None,
        "failures": failures,
    }


def check_voltage_domain(gds: str, extract_report: dict) -> dict:
    response = _klt("layers", gds, "--top", TOP_CELL, "--flattened")
    by_layer = {
        (layer["layer"], layer["datatype"]): layer for layer in response.get("layers", [])
    }
    marker_layers = {
        "DNWELL": (12, 0),
        "LVPWELL": (204, 0),
        "Dualgate": (55, 0),
    }
    drawn = {
        name: by_layer.get(key, {}).get("flattened_shapes")
        or by_layer.get(key, {}).get("shapes")
        for name, key in marker_layers.items()
    }
    failures = [name for name, count in drawn.items() if not count]
    return {
        "name": "voltage_domain",
        "passed": not failures,
        "marker_shape_counts": drawn,
        "klt_voltage_domain_warnings": extract_report.get("voltage_domain_warnings", []),
        "failures": [f"voltage-domain marker layer {name} carries no geometry" for name in failures],
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def _redact_local_paths(value):
    """Drop machine-local PDK install paths from a committed report.

    The same rule design/README.md applies to xschem's ``sch_path`` header: an
    absolute path from whichever machine ran the tool is meaningless (and
    sometimes misleading) to every other reader, so it does not get committed.
    """
    if isinstance(value, dict):
        return {
            key: _redact_local_paths(item)
            for key, item in value.items()
            if key not in ("root", "source")
        }
    if isinstance(value, list):
        return [_redact_local_paths(item) for item in value]
    return value


def run(gds: str, pdk: str, work_dir: str) -> dict:
    _, devices = parse_netlist(NETLIST_PATH)
    device_check = check_devices(gds, pdk, devices, work_dir)
    extract_report = device_check.pop("extract_report")
    checks = [
        device_check,
        check_dnwell_partition(gds, devices),
        check_voltage_domain(gds, extract_report),
    ]
    return {
        "layout": os.path.relpath(gds, REPO_ROOT) if gds.startswith(REPO_ROOT) else gds,
        "source_netlist": os.path.relpath(NETLIST_PATH, REPO_ROOT),
        "top_cell": TOP_CELL,
        "pdk": _redact_local_paths(extract_report.get("pdk")),
        "provenance": _redact_local_paths(extract_report.get("provenance")),
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gds", default=DEFAULT_GDS, help="layout to check (default: %(default)s)")
    parser.add_argument("--pdk", default=DEFAULT_PDK, help="PDK variant (default: %(default)s)")
    parser.add_argument(
        "--work-dir",
        default=None,
        help="where to write the extracted netlist (default: alongside --gds)",
    )
    parser.add_argument("--report", default=None, help="also write the JSON report here")
    args = parser.parse_args(argv)

    gds = os.path.abspath(args.gds)
    if not os.path.exists(gds):
        print(f"error: {gds} does not exist -- run layout/gen_gate_driver_core.py first", file=sys.stderr)
        return 1
    work_dir = os.path.abspath(args.work_dir) if args.work_dir else os.path.dirname(gds)
    os.makedirs(work_dir, exist_ok=True)

    try:
        result = run(gds, args.pdk, work_dir)
    except (GenError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for check in result["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"[{status}] {check['name']}")
        for key, value in check.items():
            if key in ("name", "passed", "failures", "missing", "unexpected"):
                continue
            print(f"         {key}: {value}")
        for failure in check.get("failures", []):
            print(f"         ! {failure}")
        for entry in check.get("missing", []):
            print(f"         ! missing {entry['count']}x {entry['device']}")
        for entry in check.get("unexpected", []):
            print(f"         ! unexpected {entry['count']}x {entry['device']}")

    if args.report:
        with open(os.path.abspath(args.report), "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
            handle.write("\n")
        print(f"report: {args.report}")

    print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
