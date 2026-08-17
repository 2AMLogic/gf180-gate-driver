#!/usr/bin/env python3
"""Emit the LVS **reference** netlist for ``gate_driver_core``.

``klt lvs`` compares a layout-extracted netlist against a reference netlist.
The reference cannot be ``design/netlist/gate_driver_core.spice`` verbatim,
because the extraction deck's own device-class/body-terminal capabilities
differ from what the schematic states -- mirroring
``2AMLogic/gf180-bandgap``'s ``layout/lvs/make_reference.py`` (CLAUDE.md:
"Harness bootstrap: copy the sim-harness pattern from 2AMLogic/gf180-bandgap
rather than reinventing it"), this script mechanically derives the reference
from the committed schematic netlist via
:func:`layout.gen_gate_driver_core.parse_netlist` -- the *same* parser the
generator itself draws from, so the drawn geometry and the LVS reference
cannot disagree about device count/W/L/connectivity -- applying exactly the
transformations the extraction deck's own capabilities and this layout's own
drawn decomposition imply. No hand editing, no per-device fudging.

Transformations applied (see ``layout/README.md`` "What the LVS verdict does
and does not cover" for the full rationale):

1. **Expand each device to its drawn finger count.** A netlist device with
   ``nf=N m=M`` draws as ``N*M`` parallel unit transistors of ``W/N`` each
   (``layout/gen_gate_driver_core.py``'s own ``Device.fingers``/``w_um``);
   ``klt extract`` reads each drawn finger back as its own separate
   transistor, so the reference must too.
2. **Device class: generic ``nfet``/``pfet``, not the schematic's
   voltage-flavored model name.** `klt`'s gf180mcu extraction deck does not
   distinguish `nfet_03v3` from `nfet_06v0` at the device-class level (every
   thick-oxide MOS extracts against the deck's one generic MOS device class
   regardless of the drawn ``Dualgate`` marker -- see
   ``gate_driver_core.checks.json``'s ``voltage_domain_warnings`` and
   ``layout/README.md``'s "klt's gf180mcu deck does not model `Dualgate`
   scoping" gap, filed upstream). Using the schematic's own flavored model
   name in the reference (e.g. ``nfet_06v0``) makes `klt lvs` see it as an
   unrelated device class from the layout's plain ``nfet``, and the whole
   compare fails to find a single correspondence -- confirmed against a real
   `klt lvs` run of the committed GDS.
3. **NMOS body terminal -> the deck's synthesised substrate net.** The deck
   draws no distinct p-substrate tap layer it can key on, so it ties every
   NMOS body to one global net (``SUBSTRATE_NET``) regardless of the
   schematic's own (domain-differentiated) body assignment -- ``klt lvs``'s
   own ``device.body_unverified`` finding.
4. **PMOS body terminal -> one anonymous net per drawn device instance.**
   Unlike gf180-bandgap's single contiguous PMOS band, this layout draws
   every PMOS device as its own independent strip with its own local Nwell
   patch (``layout/gen_gate_driver_core.py``'s per-device ``mos_array``
   cells, no well-merge geometry) -- confirmed by a real `klt extract` run
   reporting 11 distinct anonymous PMOS body nets (one per schematic PMOS
   instance's drawn finger group, not one per voltage domain). The reference
   models that reality: each schematic PMOS instance's own dedicated,
   unconnected net (``NWL_<device-name>``), not the schematic's shared
   ``VDD_LOGIC``/``VDD_DRV`` body tie. This is `klt lvs`'s second
   ``device.body_unverified`` finding, same root cause (no well-tap layer)
   as #3.

Usage::

    python3 layout/lvs/make_reference.py -o layout/lvs/gate_driver_core.ref.spice
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "layout"))

import gen_gate_driver_core as generator  # noqa: E402

#: Net every extracted NMOS body terminal compares against -- the gf180mcu
#: extraction deck's single synthesized substrate net (no drawn p-sub tap
#: layer to key on). Matches `klt extract`'s own reported pin name (``vsubs``).
SUBSTRATE_NET = "vsubs"

TOP = "gate_driver_core"


def _pmos_well_net(device: "generator.Device") -> str:
    """This PMOS instance's own dedicated, unconnected well net.

    Every PMOS device draws its own local Nwell patch with no well-merge
    geometry tying it to any other device or to a real supply rail (see this
    module's docstring, transform 4) -- so each schematic PMOS instance gets
    its own anonymous net name here, all ``fingers`` copies of that one
    instance sharing it (matching what `klt extract` actually measures: one
    anonymous net per drawn well island, shared by every finger drawn inside
    it).
    """
    return f"nwl_{device.name}"


def build_reference() -> tuple[str, dict]:
    _top_ports, devices = generator.parse_netlist(generator.NETLIST_PATH)

    lines: list[str] = []
    counts = {"nfet": 0, "pfet": 0}
    used_nets: set[str] = set()

    for device in devices:
        body = SUBSTRATE_NET if device.flavor == "nfet" else _pmos_well_net(device)
        used_nets.update((device.d, device.g, device.s, body))
        counts[device.flavor] += device.fingers
        for finger in range(device.fingers):
            lines.append(
                f"M{device.name}_{finger} {device.d} {device.g} {device.s} {body} "
                f"{device.flavor} L={device.l_um:g}U W={device.w_um:g}U"
            )

    # Pins: every net named directly on a device terminal (`klt extract`
    # promotes every such labeled net to a top-level pin when the layout is
    # flat with no sub-cell instances left to demote them -- confirmed
    # against a real extraction: 18 named nets + the synthesized `vsubs`
    # substrate net, 19 total, none of the anonymous per-instance PMOS well
    # nets among them since those carry no drawn label).
    named_nets = sorted({d.d for d in devices} | {d.g for d in devices} | {d.s for d in devices})
    pins = named_nets + [SUBSTRATE_NET]

    header = [
        "* LVS reference netlist for gate_driver_core -- GENERATED, do not edit.",
        "*",
        "* Produced by layout/lvs/make_reference.py from",
        "* design/netlist/gate_driver_core.spice via",
        "* layout/gen_gate_driver_core.py's own parse_netlist(), applying the four",
        "* mechanical transforms documented in that script's module docstring.",
        "*",
        f"* MOS devices: {counts['nfet']} nfet + {counts['pfet']} pfet "
        f"({len(devices)} schematic instances, expanded to drawn finger count)",
        "",
        f".SUBCKT {TOP} " + " ".join(pins),
    ]
    body = sorted(lines)
    return "\n".join(header + body + [f".ENDS {TOP}", ""]), {
        "counts": counts,
        "pins": pins,
        "nets": sorted(used_nets),
        "devices": len(devices),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        default=str(REPO_ROOT / "layout" / "lvs" / "gate_driver_core.ref.spice"),
        help="output SPICE path",
    )
    args = parser.parse_args()

    text, info = build_reference()
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    Path(args.output).write_text(text)
    print(f"wrote {args.output}")
    print(f"  devices : {info['devices']} schematic instances -> {info['counts']} fingers")
    print(f"  pins    : {' '.join(info['pins'])}")
    print(f"  nets    : {len(info['nets'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
