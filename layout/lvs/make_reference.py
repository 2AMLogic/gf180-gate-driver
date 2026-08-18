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
3. **NMOS body terminal -> the schematic's own GND_LOGIC/GND_DRV assignment,
   canonicalized by transform 5 below (issue #132, revised).** gf180mcu's
   curated extraction deck draws no distinct p-substrate tap layer and --
   confirmed by reading `klayout-tools`' own `extract.py` -- ties *every*
   NMOS body, in every layout, to one hardcoded global identity
   (``ExtractionDeck.substrate_net``, internal name ``vsubs``, via KLayout's
   ``connect_global``) regardless of which DNWELL/LVPWELL region a device's
   diffusion sits in (klayout-tools #1128, filed upstream -- there is no way
   to scope a drawn substrate tap to only one of this design's two domains).
   That part of the limitation is real and permanent. But once real Pplus tie
   geometry is drawn for *both* grounds (`body_ties()`), that global identity
   stops being an anonymous placeholder: it becomes directly, physically
   wired to real labeled Metal1 (both `GND_LOGIC` and `GND_DRV`), so `klt
   extract` names the merged node after that real metal instead of falling
   back to its own synthesized `vsubs` label -- confirmed against a real
   extraction, `vsubs` does not appear anywhere in the extracted netlist's
   pin list once both taps are drawn. The two domains are still merged (see
   transform 5), but the merged identity is now a *real* net the schematic
   also names (transform 5's `GND_DRV|GND_LOGIC`), not a synthesized
   placeholder -- so the reference uses the device's own real body net here,
   exactly like transform 4 already does for PMOS. This turned out to fully
   resolve `klt lvs`'s ``device.body_unverified`` finding for NMOS too (not
   only reduce its severity): a real `klt lvs` run against this geometry
   reports zero ``device.body_unverified`` mismatches, on either flavor.
4. **PMOS body terminal -> the schematic's own VDD_LOGIC/VDD_DRV assignment
   (issue #132).** Unlike #3, this *is* achievable: `klt`'s gf180mcu deck
   derives a genuine per-Nwell-island well tie from an Nplus-covered Comp
   shape inside Nwell (`decks/gf180mcu.py`'s `tap_nplus` field, klayout-tools
   issue #1084) -- confirmed by drawing exactly that
   (``gen_gate_driver_core.py``'s ``Interconnect.body_ties()``: a per-device
   Comp+Nplus+Contact+Metal1 tap inside a redundant Nwell rectangle sized to
   merge with `klt gen mos_array`'s own internal Nwell, wired to the
   device's own ``VDD_LOGIC``/``VDD_DRV`` rail) and re-running `klt extract`:
   `unbiased_pmos_body_nets` drops from 660 entries to zero. Because each
   PMOS device's Nwell island is geometrically independent (11 separate,
   non-touching islands, one per schematic instance -- no well-merge
   geometry across devices), each ties to its *own* device's real body net
   with no cross-device or cross-domain merge risk, unlike #3. So this
   transform now uses ``device.b`` directly instead of a per-instance
   anonymous placeholder.
5. **GND_LOGIC/GND_DRV -> one merged net, everywhere they appear (not only
   as a body terminal) (issue #132).** Transform 3's global substrate
   identity is not scoped to the body terminal alone: once real Pplus tie
   geometry is drawn for *both* grounds (`body_ties()`), `connect_global`
   ties every net that Metal1-contacts either domain's substrate tap into
   that one identity -- which, transitively, is every net-terminal
   (source/drain, not just body) that is directly wired to `GND_LOGIC` or
   `GND_DRV` metal. Confirmed against a real extraction: the layout-side
   netlist reports one merged pin, literally named ``GND_DRV|GND_LOGIC``
   (`klt`'s own join of the two original labels, alphabetical order), and
   drops from 18 to 17 named nets. `VDD_LOGIC`/`VDD_DRV` are unaffected --
   each PMOS well island is its own geometrically independent net (transform
   4), so there is no equivalent global identity on the supply side. This is
   the same real electrical fact transform 3 already documents (Decision 1:
   one electrical reference node, split into two pins only at the pad ring),
   now surfacing on ordinary device terminals instead of only body
   terminals, so the reference must merge the two net *names* -- not just
   the body assignment -- to match.

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

#: The gf180mcu extraction deck's internal name for its single synthesized
#: global substrate identity (no drawn p-sub tap layer to key on -- see
#: transform 3 above). Not used as a body net by this script any more: once
#: real tie geometry wires that identity to real labeled metal (both
#: grounds), `klt extract` names it after that metal instead, and this
#: literal string does not appear anywhere in a real extraction of this
#: layout. Kept only so a reader tracing an older evidence record (or the
#: docstring above) back to this module finds the name defined somewhere.
SUBSTRATE_NET = "vsubs"

#: The two schematic grounds that real body-tie geometry (issue #132's
#: `body_ties()`) merges into one net at extraction time -- transform 5
#: above. Matches `klt extract`'s own synthesized joined pin name exactly
#: (`"|".join(sorted(...))`, confirmed against a real extraction).
_MERGED_GROUND_NETS = ("GND_DRV", "GND_LOGIC")
MERGED_GROUND_NET = "|".join(sorted(_MERGED_GROUND_NETS))

TOP = "gate_driver_core"


def _canon(net: str) -> str:
    """Apply transform 5: fold ``GND_LOGIC``/``GND_DRV`` to one merged net."""
    return MERGED_GROUND_NET if net in _MERGED_GROUND_NETS else net


def build_reference() -> tuple[str, dict]:
    _top_ports, devices = generator.parse_netlist(generator.NETLIST_PATH)

    lines: list[str] = []
    counts = {"nfet": 0, "pfet": 0}
    used_nets: set[str] = set()

    for device in devices:
        # PMOS: the schematic's own body net (transform 4). NMOS: the
        # schematic's own body net too, canonicalized by transform 5 -- see
        # that transform's docstring entry for why the deck's *global*
        # substrate identity (SUBSTRATE_NET) is no longer the right model
        # once real tie geometry exists for both grounds: that identity is
        # now itself directly, physically wired to real labeled metal
        # (GND_LOGIC and GND_DRV), so `klt extract` names it after that real
        # metal instead of falling back to its own synthesized `vsubs`
        # placeholder -- confirmed against a real extraction (`vsubs` no
        # longer appears anywhere in the extracted netlist's pin list).
        body = device.b
        # Transform 5: GND_LOGIC/GND_DRV merge on every terminal, not just
        # body, once real tie geometry is drawn for both.
        d, g, s, body = (_canon(n) for n in (device.d, device.g, device.s, body))
        used_nets.update((d, g, s, body))
        counts[device.flavor] += device.fingers
        for finger in range(device.fingers):
            lines.append(
                f"M{device.name}_{finger} {d} {g} {s} {body} "
                f"{device.flavor} L={device.l_um:g}U W={device.w_um:g}U"
            )

    # Pins: every net named directly on a device terminal (`klt extract`
    # promotes every such labeled net to a top-level pin when the layout is
    # flat with no sub-cell instances left to demote them -- confirmed
    # against a real extraction: 17 named nets (18 schematic net names, minus
    # one for the GND_LOGIC/GND_DRV merge, transform 5). No separate
    # synthesized `vsubs` pin: both PMOS body (transform 4) and NMOS body
    # (transform 3, revised) now resolve into this same named-net set, since
    # real tie geometry wires the deck's global substrate identity directly
    # to real labeled metal instead of leaving it an anonymous placeholder --
    # `vsubs` does not appear anywhere in a real extraction of this layout
    # any more.
    named_nets = {d.d for d in devices} | {d.g for d in devices} | {d.s for d in devices}
    named_nets |= {d.b for d in devices}
    pins = sorted({_canon(n) for n in named_nets})

    header = [
        "* LVS reference netlist for gate_driver_core -- GENERATED, do not edit.",
        "*",
        "* Produced by layout/lvs/make_reference.py from",
        "* design/netlist/gate_driver_core.spice via",
        "* layout/gen_gate_driver_core.py's own parse_netlist(), applying the five",
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
