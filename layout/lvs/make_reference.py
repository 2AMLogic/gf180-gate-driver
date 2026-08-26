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
3. **NMOS body terminal -> the deck's one global substrate identity, which
   this design's own drawn tie geometry happens to name ``GND_LOGIC``
   (issue #132, revised again for issue #221).** gf180mcu's curated
   extraction deck draws no distinct p-substrate tap layer and -- confirmed
   by reading `klayout-tools`' own `extract.py` -- ties *every* NMOS body,
   in every layout, to one hardcoded global identity
   (``ExtractionDeck.substrate_net``, internal name ``vsubs``, via KLayout's
   ``connect_global``) regardless of which DNWELL/LVPWELL region a device's
   diffusion sits in (klayout-tools #1128, filed upstream -- there is no way
   to scope a drawn substrate tap to only one of this design's two domains).
   That part of the limitation is real and permanent, and the body terminal
   of every one of this layout's 1105 drawn NMOS devices (both domains)
   still resolves to exactly one net, confirmed against a real extraction of
   the issue #221-extended GDS.

   **What changed (issue #221): that merged identity no longer also absorbs
   `GND_DRV`.** An earlier revision of this transform (and of transform 5
   below) additionally claimed the merged identity gets *named* after
   whichever real metal directly straps a tap into it, and that both
   `GND_LOGIC`'s (native-substrate) and `GND_DRV`'s (isolated-LVPWELL)
   taps do so once `body_ties()` draws both -- producing one joined pin
   `GND_DRV|GND_LOGIC`, confirmed at the time against a real extraction on
   `klt` 0.2.0. Re-running that *exact, byte-identical, previously-clean*
   GDS (``git show ec34094:layout/gate_driver_core.gds``) through the `klt`
   now installed (0.3.0, a different `provenance.deck.content_hash`)
   reproduces neither claim: the merged identity now surfaces under the
   literal name ``GND_LOGIC`` alone, and ``GND_DRV`` extracts as its own,
   separate, unmerged net on every terminal -- on both the pre-#221 GDS
   *and* this issue's UVLO-extended one. This is exactly the generic
   tool-gap `klayout-tools` issue #1149 already tracks upstream ("gf180mcu
   deck: substrate/well-tap recognition behavior changed between deck
   builds, silently invalidating previously-passing LVS evidence") -- filed
   the same day the old evidence was recorded, and already closed there, so
   this script adapts to the deck's current, real behavior rather than
   re-filing a duplicate. Net effect for this transform: the reference
   canonicalizes an NMOS body terminal to the literal string ``"GND_LOGIC"``
   (:data:`BODY_NET`) regardless of which of the two the schematic names,
   and no longer folds `GND_DRV` into it anywhere else (see transform 5,
   removed). This still fully resolves `klt lvs`'s ``device.body_unverified``
   finding for NMOS (a real `klt lvs` run against the current geometry
   reports zero, on either flavor) -- only the *ordinary* d/g/s use of
   `GND_DRV` stops being folded into that same identity.
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
5. **(Removed by issue #221.) `GND_LOGIC` and `GND_DRV` are two genuinely
   separate nets on every *ordinary* (non-body) terminal, and the reference
   now states them as such.** An earlier revision of this transform folded
   both names together everywhere a device used either one, reasoning that
   real substrate-tie geometry for both domains made `connect_global` merge
   them transitively on ordinary source/drain terminals too, not just on
   body. Transform 3 above records why that no longer reproduces under the
   currently-installed deck build (klayout-tools issue #1149): `GND_DRV`
   does not merge with the body-terminal identity (or with `GND_LOGIC`) on
   any terminal any more. Removing this transform is not just chasing the
   tool's current behavior, though -- it also matches this block's own
   ratified architecture better than the old assumption did:
   `spec/decision-records/0001` (Decision 1) states the two grounds are "one
   electrical reference node, split into two pins **only at the pad
   ring**." This layout is the bare core block, with no pad ring drawn --
   so at *this* level, `GND_LOGIC` and `GND_DRV` are correctly two distinct,
   unconnected nets, and a body-tie side effect that happened to merge them
   anyway (on the old deck build) was standing in for a tie this block does
   not itself draw, not confirming one that exists. `VDD_LOGIC`/`VDD_DRV`
   were never subject to this transform (each PMOS well island is its own
   geometrically independent net, transform 4) and are unaffected either
   way.
6. **MiM capacitors carry an extracted capacitance, not a schematic one
   (issue #166).** The schematic states the ``XCCOMP*`` stack as geometry
   (``c_width``/``c_length``), because that is what a layout can draw and
   what ``spec/decision-records/0014`` ratified; the layout side of the
   compare carries whatever `klt extract` *measures*, and
   ``kdb.NetlistComparer`` compares a matched device pair's parameters
   directly. So the reference restates the same geometry through the
   extraction deck's own published two-term MiM model
   (:data:`MIM_AREA_CAP_F_UM2` / :data:`MIM_PERIM_CAP_F_UM`, below), which is
   a *derivation* from the netlist's own numbers -- not a value copied back
   out of an extraction, which would make the compare circular.
7. **Bare-``R`` resistors -> a 3-terminal ``ppolyf_u`` device, at the
   schematic's own ohms value (issue #221).** ``uvlo.spice``'s
   ``Rref``/``R1``/``R2``/``Rfb`` state only an ideal resistance, no drawn
   geometry (``design/uvlo-comparator-sizing.md``: a physical realization is
   this issue's own scope). ``layout/gen_gate_driver_core.py``'s
   :func:`~gen_gate_driver_core.resistor_array_params` sizes a
   ``klt gen res_array`` block (gf180mcu's ``ppolyf_u``, 350 ohm/sq) to draw
   that exact ohms value, confirmed against a real ``klt extract`` run:
   ``r_ohm == 350 * l_um / w_um`` exactly, device class ``ppolyf_u``, three
   terminals ``a``/``b``/``w`` -- the third (``w``) is the same deck-global
   substrate identity every NMOS body ties to (transform 3, :data:`BODY_NET`
   under the currently-installed deck), which a resistor's own ideal
   two-terminal schematic model was never otherwise going to name.
   `kdb.NetlistComparer`'s resistor
   value comparison is tight (confirmed empirically: matches at a ~4e-7
   relative difference, mismatches at ~4e-6), so the reference states
   *exactly* the same ``value_ohm`` the netlist itself carries -- the
   generator's own :func:`~gen_gate_driver_core.resistor_array_params`/
   :func:`~gen_gate_driver_core.resistor_ohms` pair guarantees the drawn
   geometry reproduces it, not a value copied back out of an extraction.

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

#: The two schematic net names that can appear as an NMOS body/resistor-
#: substrate terminal, both of which canonicalize to :data:`BODY_NET`
#: (transform 3) -- `body_ties()` draws real Pplus tie geometry for each,
#: and the deck's global substrate identity (`connect_global`) ties every
#: NMOS body to one node regardless of which of the two a given device's
#: own tap happens to be strapped to.
_BODY_NET_ALIASES = ("GND_DRV", "GND_LOGIC")

#: The literal name the deck's merged global substrate identity currently
#: surfaces under (issue #221 revision -- see transform 3's docstring entry
#: for why this is `"GND_LOGIC"` alone rather than a `GND_DRV`-joined
#: string, and klayout-tools issue #1149 for the upstream deck-behavior-
#: drift this adapts to). Confirmed against a real extraction of this
#: layout: every one of its 1105 drawn NMOS devices' body terminal reads
#: exactly this, on both this issue's UVLO-extended GDS and the pre-#221
#: one. **Not** used for `GND_DRV`/`GND_LOGIC` on any *other* (non-body)
#: terminal -- those keep their own schematic name unchanged (transform 5,
#: removed).
BODY_NET = "GND_LOGIC"

TOP = "gate_driver_core"

#: The two coefficients of gf180mcu's 2.0 fF/um^2 MiM model, as `klt`'s own
#: gf180mcu extraction deck publishes them
#: (``decks/gf180mcu.py``'s ``EXTRACTION_DECK.capacitors`` ->
#: ``cap_mim_2f0_m4m5_noshield``: ``area_cap_f_um2=1.99e-15``,
#: ``perim_cap_f_um=2.383e-16``), which that deck in turn transcribes from the
#: PDK's own ``libs.tech/ngspice/sm141064.ngspice`` ``.subckt cap_mim_2f0fF``
#: (``c_cox = 1.99e-3 F/m^2``, ``c_capsw = 2.383e-10 F/m``).
#:
#: Hard-coded rather than imported, deliberately: this script runs in CI
#: (``lvs/test_make_reference.py``) on a runner with neither `klt` nor the PDK
#: installed, and the whole point of the reference netlist is to be derivable
#: from the *schematic* without the layout toolchain. A drift between these
#: numbers and the deck's own would surface immediately as a
#: ``device.property`` LVS mismatch on all four capacitors, not silently.
MIM_AREA_CAP_F_UM2 = 1.99e-15
MIM_PERIM_CAP_F_UM = 2.383e-16


def mim_capacitance_f(width_um: float, length_um: float) -> float:
    """The two-term MiM capacitance of a ``width_um`` x ``length_um`` plate.

    ``C = area_cap * A + perim_cap * P`` -- the same expression `klt extract`
    evaluates over the *drawn* plate overlap (KLayout's own
    ``DeviceExtractorCapacitor`` contributes the area term; the deck's
    ``perim_cap_f_um`` post-correction adds the fringe term). Here it is
    evaluated over the plate the *netlist* asks for, so the two agree only if
    the layout actually drew the geometry the schematic specified -- which is
    exactly the thing LVS is supposed to be checking.
    """
    return (
        MIM_AREA_CAP_F_UM2 * width_um * length_um
        + MIM_PERIM_CAP_F_UM * 2.0 * (width_um + length_um)
    )


def _body_net(net: str) -> str:
    """Apply transform 3: canonicalize an NMOS/resistor body terminal.

    Only ever called on a *body* (or resistor-substrate) terminal -- an
    ordinary d/g/s or resistor plus/minus terminal keeps its own schematic
    name unchanged (transform 5, removed; see the module docstring).
    """
    return BODY_NET if net in _BODY_NET_ALIASES else net


def build_reference() -> tuple[str, dict]:
    _top_ports, devices, passives, resistors = generator.parse_netlist_full(
        generator.NETLIST_PATH
    )

    lines: list[str] = []
    counts = {"nfet": 0, "pfet": 0, "cap": 0, "res": 0}
    used_nets: set[str] = set()

    for device in devices:
        # d/g/s keep their own schematic name unchanged -- `GND_DRV` and
        # `GND_LOGIC` are two genuinely separate nets on these terminals
        # (transform 5, removed). Only the body terminal canonicalizes
        # (transform 3): PMOS to its own real per-device Nwell-tie net
        # (transform 4, already device.b -- `_body_net` is a no-op for a
        # VDD_LOGIC/VDD_DRV value), NMOS to the deck's one global substrate
        # identity, `BODY_NET`.
        d, g, s = device.d, device.g, device.s
        body = _body_net(device.b)
        used_nets.update((d, g, s, body))
        counts[device.flavor] += device.fingers
        for finger in range(device.fingers):
            lines.append(
                f"M{device.name}_{finger} {d} {g} {s} {body} "
                f"{device.flavor} L={device.l_um:g}U W={device.w_um:g}U"
            )

    # Transform 6: the MiM stack. Written in the plain-element form
    # `NetlistSpiceReader` turns into a device class named after the model
    # (`C<name> <a> <b> <model> C=<value>` -- the *only* C-card spelling that
    # names a class rather than falling back to the generic `CAP`, or reading
    # the model token as a third, bulk terminal). The class name is what pairs
    # this side with `klt extract`'s own `cap_mim_2f0_m4m5_noshield` devices;
    # KLayout matches device-class names case-insensitively, so the reader's
    # up-casing is harmless. Neither terminal is ever `GND_DRV`/`GND_LOGIC`
    # (the chain lives entirely on the level shifter's own internal/IN_DRV
    # nets), so no canonicalization applies here.
    for passive in passives:
        plus, minus = passive.plus, passive.minus
        used_nets.update((plus, minus))
        counts["cap"] += 1
        lines.append(
            f"C{passive.name} {plus} {minus} {passive.model} "
            f"C={mim_capacitance_f(passive.w_um, passive.l_um):.6g}"
        )

    # Transform 7: the uvlo bias resistor network (issue #221). A netlist `R`
    # element is *folded* by the generator into `num` series unit resistors
    # (`resistor_array_params`, `Interconnect.resistors`) -- so, exactly like
    # transform 6's MiM series chain, the reference must state each drawn
    # unit device and its real interior series node, not one lumped device at
    # the netlist's ohms value: `klt lvs` compares devices one-for-one, and a
    # single-device reference against `num` drawn units is a device-count
    # mismatch even though the two are electrically equivalent (confirmed
    # against a real `klt lvs` run -- a lumped reference reported 0/1777
    # devices matched). Every unit is written
    # `R<name>_<i> <a> <b> <w> ppolyf_u R=<value>` -- confirmed against a real
    # `klt lvs` run that this is the spelling `NetlistSpiceReader` reads as a
    # 3-terminal device of class `ppolyf_u` with an `R=` parameter, pairing
    # with `klt extract`'s own `ppolyf_u` devices. `plus`/`minus` are ordinary
    # two-terminal connections (one of R2's two is literally `GND_DRV`) and
    # keep their own schematic name unchanged, exactly like a MOS d/g/s
    # terminal; only the synthesized third terminal is the deck's global
    # substrate identity every NMOS body also ties to, so it canonicalizes
    # through `_body_net`. The `num - 1` interior nodes are synthesized here
    # (the schematic states one ideal resistor, no internal nodes) but stay
    # unpromoted (never added to `named_nets`/pins, same as the MiM stack's
    # interior nodes) -- `klt extract` leaves the layout's own matching
    # jumpers unlabeled too, so both sides resolve them structurally rather
    # than by name.
    for resistor in resistors:
        plus, minus = resistor.plus, resistor.minus
        num, _rows, length_um = generator.resistor_array_params(resistor.value_ohm)
        unit_ohm = generator.resistor_ohms(1, length_um)
        nodes = [plus] + [f"{resistor.name}_n{i}" for i in range(1, num)] + [minus]
        used_nets.update(nodes)
        used_nets.add(BODY_NET)
        counts["res"] += num
        for i in range(num):
            lines.append(
                f"R{resistor.name}_{i} {nodes[i]} {nodes[i + 1]} "
                f"{BODY_NET} ppolyf_u R={unit_ohm:.9g}"
            )

    # Pins: every net named directly on a device terminal (`klt extract`
    # promotes every such labeled net to a top-level pin when the layout is
    # flat with no sub-cell instances left to demote them). `GND_LOGIC` and
    # `GND_DRV` are now both real, separate pins (transform 5 removed) --
    # confirmed against a real extraction of the issue #221-extended GDS: 18
    # named nets, no merge. No separate synthesized `vsubs` pin: both PMOS
    # body (transform 4) and NMOS body (transform 3) resolve into a named net
    # this set already carries, since real tie geometry wires the deck's
    # global substrate identity directly to real labeled metal instead of
    # leaving it an anonymous placeholder -- `vsubs` does not appear anywhere
    # in a real extraction of this layout.
    #
    # The MiM stack's own interior nodes (``x1_nccomp1``..``3``) are
    # deliberately *not* pins and deliberately not labeled in the layout
    # either: each is one floating plate-to-plate metal polygon with two
    # capacitor terminals on it and nothing else (issue #166 /
    # ``gen_gate_driver_core.Interconnect.mim_caps``), so `klt extract` leaves
    # them as internal, unnamed nets. They still have to *match*, which is the
    # point -- the comparer has to find the four-deep series chain
    # topologically, anchored at the two named ends.
    named_nets = {d.d for d in devices} | {d.g for d in devices} | {d.s for d in devices}
    named_nets |= {_body_net(d.b) for d in devices}
    pins = sorted(named_nets)

    header = [
        "* LVS reference netlist for gate_driver_core -- GENERATED, do not edit.",
        "*",
        "* Produced by layout/lvs/make_reference.py from",
        "* design/netlist/gate_driver_core.spice via",
        "* layout/gen_gate_driver_core.py's own parse_netlist_full(), applying the",
        "* seven mechanical transforms documented in that script's module docstring.",
        "*",
        f"* MOS devices: {counts['nfet']} nfet + {counts['pfet']} pfet "
        f"({len(devices)} schematic instances, expanded to drawn finger count)",
        f"* MiM caps  : {counts['cap']} ({len(passives)} schematic instances, "
        "1:1 -- one drawn plate pair each)",
        f"* Resistors : {counts['res']} ppolyf_u ({len(resistors)} schematic "
        "instances, 1:1 -- one folded res_array block each)",
        "",
        f".SUBCKT {TOP} " + " ".join(pins),
    ]
    body = sorted(lines)
    return "\n".join(header + body + [f".ENDS {TOP}", ""]), {
        "counts": counts,
        "pins": pins,
        "nets": sorted(used_nets),
        "devices": len(devices),
        "passives": len(passives),
        "resistors": len(resistors),
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
    print(f"  passives: {info['passives']} MiM cap(s)")
    print(f"  resistors: {info['resistors']} ppolyf_u")
    print(f"  pins    : {' '.join(info['pins'])}")
    print(f"  nets    : {len(info['nets'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
