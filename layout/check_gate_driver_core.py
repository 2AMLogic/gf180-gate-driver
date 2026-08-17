#!/usr/bin/env python3
"""Check ``layout/gate_driver_core.gds`` against its source schematic netlist.

Three checks, all run against the *committed* GDS through `klt` -- none of
them reads the generator's internal state, so this is an independent audit of
the stream, not a replay of how it was built:

``devices``
    ``klt extract --deck gf180mcu`` the layout and compare every extracted
    transistor against ``design/netlist/gate_driver_core.spice``, flattened.
    A netlist device with ``nf=N m=M`` must appear as exactly ``N*M``
    extracted transistors of width ``W/N`` and the same length, whose gate net
    and (unordered) source/drain net pair match the schematic's (every device
    in the committed netlist has ``nf=1``, so today that is ``M`` transistors
    of width ``W``).  This is the issue's "connectivity/device-count check
    against the source netlist" -- it is deliberately *not* a full LVS run
    (that is issue #105's scope).

    Note what this check can and cannot see: it re-derives the expected list
    through the generator's own ``parse_netlist``, so it audits the *stream*
    against that interpretation but cannot audit the interpretation itself.
    ``layout/test_gen_gate_driver_core.py`` is the independent half of that
    (issue #129).

``dnwell_partition``
    ``klt components`` with ``DNWELL`` (12/0) declared both as a conductor and
    as the via that joins it to ``Comp`` (22/0).  Every active region a DNWELL
    polygon overlaps therefore lands in the DNWELL's own component; every
    active region outside it does not.  The check asserts that component holds
    exactly the 5V/6V (``*_06v0``) devices' active regions and that every
    3.3V (``*_03v3``) device's active region is outside it -- DRM 7.2 /
    spec/gate-driver.md 2.4, the "no shared DNWELL" acceptance criterion.

    Issue #132's per-device body-tie taps
    (``gen_gate_driver_core.Interconnect.body_ties()``) also draw Comp shapes
    -- one per device (both flavors: an Nplus well tie for every PMOS, a
    Pplus substrate/LVPWELL tie for every NMOS), deliberately on the *same*
    Comp layer this check inspects, since gf180mcu's curated deck derives
    both kinds of tie from ordinary active diffusion (see that method's
    docstring) -- so the raw Comp shape count in/outside DNWELL is no longer
    "one per device"; the expected counts below add exactly one tap per
    device (of either flavor) on each side of the boundary. The guard ring
    (``Interconnect.guard_ring()``) is positioned with a real, non-touching
    gap outside DNWELL_DRV specifically so it never joins either component
    and needs no such adjustment.

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
    GUARD_RING_STROKE_COUNT,
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

#: GND_LOGIC (3.3V group) and GND_DRV (5V/6V group) -- two drawn Metal2 nets,
#: two schematic pins, but the one electrical reference node
#: spec/decision-records/0001 Decision 1 ratifies. See `_canon_net` below.
_GROUND_NETS = frozenset({"GND_LOGIC", "GND_DRV"})


def _canon_net(net: str) -> str:
    """Collapse ``GND_LOGIC``/``GND_DRV`` (and klt's own merged label for the
    two, e.g. ``"GND_DRV|GND_LOGIC"``) to one canonical token, for comparison
    purposes only.

    Issue #132 draws real substrate-tie geometry for *both* of this design's
    grounds (``GND_LOGIC`` for the 3.3V group, ``GND_DRV`` for the 5V/6V
    group -- ``Interconnect.body_ties()``). gf180mcu's curated `klt`
    extraction deck ties every NMOS body to one hardcoded global substrate
    identity regardless of DNWELL/LVPWELL enclosure (klayout-tools #1128,
    confirmed by reading `extract.py`'s own `connect_global` handling) -- so
    once both grounds carry a real tie, `klt extract` also reports every
    device terminal actually wired to either rail as one merged net (its own
    synthesized ``"GND_DRV|GND_LOGIC"``-style label), not the two separate
    rails the schematic and the drawn metal both keep distinct. That merge is
    the *extractor's* model, not a real short in the drawn interconnect (see
    `body_ties()`'s docstring and `layout/README.md`'s "Known gaps"), so it
    is normalized away here for this check's device-connectivity comparison
    the same way `layout/lvs/make_reference.py` normalizes it for `klt lvs`.
    Every other net name is returned unchanged.
    """
    if set(net.split("|")) & _GROUND_NETS:
        return "|".join(sorted(_GROUND_NETS))
    return net


def _device_key(flavor: str, w_um: float, l_um: float, gate: str, ds: frozenset) -> tuple:
    return (flavor, round(w_um, 3), round(l_um, 3), _canon_net(gate), frozenset(_canon_net(n) for n in ds))


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

    # Issue #132: body_ties() draws one Comp tap per *every* device (both
    # flavors), not just PMOS -- an nfet tap (Pplus implant) and a pfet tap
    # (Nplus implant) both land on this same Comp layer this check inspects,
    # so the raw Comp shape count in/outside DNWELL gains one extra shape per
    # device, regardless of flavor -- see this function's module-docstring
    # entry above.
    mv_pfet_taps = sum(1 for d in mv_devices if d.flavor == "pfet")
    lv_pfet_taps = sum(1 for d in lv_devices if d.flavor == "pfet")
    mv_nfet_taps = sum(1 for d in mv_devices if d.flavor == "nfet")
    lv_nfet_taps = sum(1 for d in lv_devices if d.flavor == "nfet")
    # guard_ring() draws GUARD_RING_STROKE_COUNT more Comp shapes, positioned
    # with a real, non-touching gap outside DNWELL_DRV (see that method's
    # docstring) -- so they land in the "outside" bucket too, but only when
    # there is an MV group for it to enclose (guard_ring() itself no-ops
    # otherwise).
    guard_ring_shapes = GUARD_RING_STROKE_COUNT if mv_devices else 0
    expected_in_dnwell = len(mv_devices) + mv_pfet_taps + mv_nfet_taps
    expected_outside = len(lv_devices) + lv_pfet_taps + lv_nfet_taps + guard_ring_shapes

    active_in_dnwell = sum(counts(c).get("active", 0) for c in in_dnwell)
    active_outside = sum(counts(c).get("active", 0) for c in outside)

    failures: list[str] = []
    if unknown:
        failures.append(f"device model(s) not classified as 3.3V or 5V/6V: {sorted(set(unknown))}")
    if len(in_dnwell) != 1:
        failures.append(f"expected exactly one DNWELL region, found {len(in_dnwell)}")
    if active_in_dnwell != expected_in_dnwell:
        failures.append(
            f"{active_in_dnwell} active region(s) inside DNWELL, expected "
            f"{expected_in_dnwell} ({len(mv_devices)} 5V/6V device(s) + "
            f"{mv_pfet_taps} PMOS well-tie tap(s) + {mv_nfet_taps} NMOS "
            "substrate-tie tap(s))"
        )
    if active_outside != expected_outside:
        failures.append(
            f"{active_outside} active region(s) outside every DNWELL, expected "
            f"{expected_outside} ({len(lv_devices)} 3.3V device(s) + "
            f"{lv_pfet_taps} PMOS well-tie tap(s) + {lv_nfet_taps} NMOS "
            f"substrate-tie tap(s) + {guard_ring_shapes} guard-ring stroke(s))"
        )
    return {
        "name": "dnwell_partition",
        "passed": not failures,
        "dnwell_regions": len(in_dnwell),
        "mv_devices": len(mv_devices),
        "lv_devices": len(lv_devices),
        "mv_pfet_taps": mv_pfet_taps,
        "lv_pfet_taps": lv_pfet_taps,
        "mv_nfet_taps": mv_nfet_taps,
        "lv_nfet_taps": lv_nfet_taps,
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
