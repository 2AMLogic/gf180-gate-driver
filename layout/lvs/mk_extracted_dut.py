#!/usr/bin/env python3
"""Turn a ``klt extract --parasitics`` report into a simulatable, flat DUT.

    python3 layout/lvs/mk_extracted_dut.py \
        --extract layout/lvs/reports/gate_driver_core/<rid>.pex.json \
        -o        layout/lvs/gate_driver_core.extracted.spice

``klt extract``'s own SPICE output is a *topology* netlist, not directly what
this repo's testbenches expect: device cards carry the extraction deck's
generic class tokens (``nfet``/``pfet``) rather than callable gf180mcu
subcircuits, MOS body terminals sit on a layer the deck's connectivity stack
does not model (floating on a synthesized substrate net or an anonymous,
un-merged well island -- see ``layout/README.md``), and the whole cell is
wrapped in a ``.SUBCKT``, whereas every existing testbench in this repo
``.include``s its DUT as a **flat** top-level fragment (``design/README.md``,
``sim/gate-driver-core-drive/testbench/gate_driver_core_tb.spice``'s own
comment on why -- the schematic DUT's own top ``.subckt`` line is commented
out for the same reason).

This script performs that conversion **explicitly and auditably**, mirroring
``2AMLogic/gf180-bandgap``'s ``layout/netlist/mk_extracted_dut.py`` (CLAUDE.md:
"Harness bootstrap: copy the sim-harness pattern from 2AMLogic/gf180-bandgap
rather than reinventing it") adapted for this design's two-flavor (3.3 V /
5 V-6 V) device set. Every transform is one of the numbered ``TRANSFORMS``
entries below, echoed into the generated file's header, so the resulting
netlist's every departure from what the extractor literally measured is
written down where a reader of the evidence records can audit it.

**What is measured** (carried through unchanged from the layout): every
device's existence, drawn W/L, and per-terminal drain/gate/source
connectivity on the deck's Poly2/COMP/Contact/Metal1..2/Via1 stack --
including the drawn finger decomposition (959 discrete transistors, not the
schematic's ``nf``/``m`` multipliers) and, when the extraction was run with
``--parasitics``, the per-net first-order lumped RC parasitics on every
*named* net.

**What is back-annotated** (asserted from the schematic + drawn L, because
the deck cannot see it) is listed in ``BACK_ANNOTATIONS`` and reproduced in
the generated header. Nothing else is invented.

**What is NOT modeled** (documented, not silently dropped): net-to-net
coupling capacitance (the extractor's ``parasitics.nets[].coupled`` field) --
this script emits only each net's own ground-referenced R/C, not the
crossover/sidewall coupling terms. See TRANSFORMS T5.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: (device class, drawn L in um, rounded to 2 decimals) -> (gf180mcu subckt,
#: the real rail this design ties that flavor's body to). L cleanly
#: disjoint-identifies flavor in this netlist: every 3.3V device (nfet_03v3/
#: pfet_03v3) draws L=0.28um, every 6V nfet draws L=0.70um, every 6V pfet
#: draws L=0.55um (design/netlist/gate_driver_core.spice) -- confirmed
#: against a real `klt extract` run (exactly these four (class, L) pairs,
#: no ambiguity). See TRANSFORMS T2/BA1/BA2.
MODEL_AND_BODY_BY_CLASS_L = {
    ("nfet", 0.28): ("nfet_03v3", "GND_LOGIC"),
    ("nfet", 0.70): ("nfet_06v0", "GND_DRV"),
    ("pfet", 0.28): ("pfet_03v3", "VDD_LOGIC"),
    ("pfet", 0.55): ("pfet_06v0", "VDD_DRV"),
}

#: Extraction-deck device classes with no `_model_and_body` entry above and no
#: body terminal at all -- issue #166's `XCCOMP` MiM series stack extracts as
#: four two-terminal ``cap_mim_2f0_m4m5_noshield`` devices (``a``/``b``, no
#: ``d``/``g``/``s``/``b``). Named explicitly, rather than "anything
#: `_model_and_body` does not recognise", so an unexpected new device class
#: still fails loudly through `_model_and_body` instead of silently being
#: treated as a capacitor. See T7.
CAP_CLASSES = {"cap_mim_2f0_m4m5_noshield"}

#: Ground reference every net's parasitic ground capacitor ties to, replacing
#: the deck's synthesized `vsubs` substrate net (`klt extract`'s single
#: global body/ground-plane node -- there is no drawn p-substrate tap layer
#: to derive a real target from). GND_LOGIC and GND_DRV are two pins but one
#: electrical reference node by design intent (design/netlist/
#: gate_driver_core.spice's header comment, decision record 0001 Decision 1)
#: -- GND_LOGIC is the arbitrary (but documented) choice of the two. See
#: TRANSFORMS T4/BA3.
GROUND_REF = "GND_LOGIC"

#: Issue #132's own body-tie geometry ties both grounds' Pplus substrate taps
#: to the deck's one global substrate identity (klayout-tools #1128), so a
#: real `klt extract` of this layout also merges every *ordinary* NMOS
#: terminal (not just body) that is directly wired to GND_LOGIC or GND_DRV
#: metal into one synthesized joined net name -- confirmed against a real
#: extraction: `"|".join(sorted(("GND_DRV", "GND_LOGIC")))`. Folding every
#: occurrence of that merged label to one fixed name (an earlier version of
#: this script did exactly that) is wrong, not just imprecise: this design's
#: two ground domains are drawn -- and this repo's own postlayout testbench
#: (`sim/gate-driver-core-drive-postlayout/testbench/gate_driver_core_tb.spice`)
#: deliberately *simulates* -- as two nodes bridged by a milliohm-scale tie
#: resistor (decision record 0001 Decision 1's "tied together with minimal
#: impedance close to the device (star point)"), not one node outright. A
#: substantial fraction of this design's NMOS terminals are ordinary d/s
#: connections *to* a ground rail (e.g. the output stage's pull-down stack,
#: `M<n> ... GND_DRV GND_DRV nfet_06v0 ...`) -- folding all of those to one
#: fixed name would silently reroute that stack's real sink-current path
#: through the testbench's tie resistor instead of straight to the load
#: capacitor's own return node, injecting a fabricated ground-bounce path a
#: real, unmerged silicon net would not have (confirmed by a full-PVT-grid
#: regression: the fixed-fold version measured *worse* undershoot at nearly
#: every corner, not just the one pre-existing marginal corner this repo's
#: schematic-side record already carries).
#:
#: Every one of this design's NMOS devices belongs to exactly one ground
#: domain, disjointly, by (class, L) -- the same fact `MODEL_AND_BODY_BY_CLASS_L`
#: already encodes for the body terminal, and confirmed for every other
#: terminal too (`design/netlist/gate_driver_core.spice`: no 3.3V-flavor
#: device ever names `gnd_drv`, no 6V-flavor device ever names `gnd_logic`,
#: and no PMOS device ever names either). So the correct rebind for *any*
#: terminal (body or otherwise) that lands on the merged raw identity is that
#: same device's own `_model_and_body`-derived ground -- not a single fixed
#: name -- which is exactly what `leg_of` below does.
MERGED_GROUND_RAW = "|".join(sorted(("GND_DRV", "GND_LOGIC")))

#: The two real rails behind `MERGED_GROUND_RAW`, in the merged label's own
#: order -- derived from the merged identity itself rather than hardcoded, so
#: it cannot drift from it. Used by T5 to place the merged net's own measured
#: ground capacitance between the two rails it actually spans.
MERGED_GROUND_RAILS = tuple(MERGED_GROUND_RAW.split("|"))

#: SPICE-legal node form of the merged identity. `|` is not a legal character
#: in an ngspice node name, and once T5 emits the merged net's per-terminal
#: parasitic legs (`GND_DRV|GND_LOGIC__t42`) those names reach the netlist as
#: real nodes, so the separator is rewritten. Purely a rename: `__t<n>` leg
#: suffixes, and therefore the extractor's own per-terminal identity, are
#: preserved verbatim.
MERGED_GROUND_NODE = MERGED_GROUND_RAW.replace("|", "_")

TRANSFORMS = [
    (
        "T1",
        "Flattening: the extractor's `.SUBCKT gate_driver_core ... .ENDS` "
        "wrapper is dropped -- every device/parasitic card is emitted at deck "
        "level, matching this repo's existing DUT-fragment convention "
        "(design/netlist/gate_driver_core.spice's own top .subckt line is "
        "commented out for the identical reason -- design/README.md).",
    ),
    (
        "T2",
        "MOS cards: the extractor's `M<n> d g s b nfet|pfet L=..U W=..U` is "
        "rebound to the real gf180mcu `nfet_03v3`/`nfet_06v0`/`pfet_03v3`/"
        "`pfet_06v0` subcircuit, selected by (device class, drawn L) -- the "
        "extraction deck's generic `nfet`/`pfet` device class does not "
        "distinguish voltage flavor (gate_driver_core.checks.json's "
        "voltage_domain_warnings; also layout/lvs/make_reference.py's "
        "transform 2), but this design's drawn L cleanly disjoint-identifies "
        "it. `nf=1 m=1`: each extracted device is one drawn finger, so the "
        "schematic's `nf`/`m` multipliers are already spent as real, "
        "separately-extracted geometry. Emitted as an `X<n>` subcircuit call, "
        "matching design/netlist/gate_driver_core.spice's own device cards, "
        "because those PDK models ARE .subckts: ngspice will resolve an `M` "
        "card against a subcircuit of that name, but then expands `m=<n>` "
        "into n separate subcircuit instances instead of passing m down to "
        "the model -- measured at 3.32 s of CPU for the `X` form of this "
        "netlist versus ~2200 s for the `M` form, at bit-identical measured "
        "results.",
    ),
    (
        "T3",
        "MOS junction geometry: AS/AD/PS/PD are carried through verbatim "
        "from the extractor's own measured `as_um2`/`ad_um2`/`ps_um`/`pd_um` "
        "(unlike gf180-bandgap's deck, this deck's gf180mcu extractor "
        "reports these directly -- no recomputation needed).",
    ),
    (
        "T4",
        "MOS body terminal: rebound to the real rail this design's schematic "
        "ties that flavor to -- GND_LOGIC/GND_DRV for NMOS, VDD_LOGIC/VDD_DRV "
        "for PMOS, selected by the same (class, L) binning as T2. Issue #132 "
        "drew real per-device body-tie geometry for every device (both "
        "flavors), and a real `klt extract` of that geometry now measures "
        "exactly this assignment on its own (PMOS: each device's own real "
        "Nwell-tie net; NMOS: the deck's global substrate identity, which is "
        "itself now wired to real labeled GND_LOGIC/GND_DRV metal instead of "
        "floating -- klayout-tools #1128, layout/lvs/make_reference.py's "
        "transform 3/5) -- so this transform is now a redundant assertion of "
        "an already-measured fact, not a fabrication filling a gap the deck "
        "cannot see. It stays a rebind (rather than reading `dev['nets']['b']` "
        "directly) so GND_LOGIC and GND_DRV keep their own separate names "
        "here -- the deck's own raw extraction merges both grounds into one "
        "synthesized joined label (`GND_DRV|GND_LOGIC`) it has no equivalent "
        "synthesized label for on the supply side, and T5's per-net parasitic "
        "stars are keyed by the schematic's own real net names, not that "
        "merged one. See BA1/BA2 and layout/README.md.",
    ),
    (
        "T5",
        "Parasitics (only when `klt extract --parasitics` was used): each "
        "named net's own per-terminal star (device leg -> resistor -> hub) "
        "and hub -> capacitor -> ground-reference are carried through "
        "verbatim from `parasitics.nets[]`, renaming only the ground "
        "reference itself (`vsubs` -> GND_LOGIC, T4/BA3, since the deck "
        "reports no parasitics entry for `vsubs` as a net in its own right). "
        "Net-to-net coupling capacitance (`parasitics.nets[].coupled`) is "
        "NOT emitted -- a documented scope reduction, not a silent drop; "
        "every ground-referenced term is measured, every coupling term is "
        "omitted, stated once here rather than per-record. Since issue #132 "
        "the extraction deck reports BOTH ground rails as one merged net "
        "(klayout-tools #1128), which has no single hub of its own here: "
        "every terminal on it belongs to exactly one real ground domain by "
        "(class, L) (T4/BA1), so each of its legs is emitted with the leg's "
        "OWN device's real GND_LOGIC/GND_DRV as that leg's hub -- the same "
        "per-device rebind the leg net itself gets, never one shared hub "
        "(which would reroute one domain's return current through the "
        "testbench's inter-rail tie; see MERGED_GROUND_RAW). That reproduces "
        "exactly the pre-#132 topology, where each rail's own star hub WAS "
        "that rail's node: 297 ground-rail R legs (issue #184). The merged "
        "net's own measured ground capacitance is emitted once between the "
        "two real rails it spans (GND_DRV<->GND_LOGIC), the same place the "
        "pre-#132 GND_DRV star's cap landed -- the deck reports one lumped "
        "value for the merged metal and resolves no per-domain split, so it "
        "is carried whole rather than apportioned by assertion.",
    ),
    (
        "T6",
        "(only with --combine, and only on a non-parasitic extraction) "
        "Device folding: parallel-identical fingers of one schematic device "
        "(exactly matching (model, d, g, s, body, L, W, AD, AS, PD, PS) after "
        "T2/T4) are folded back into one `m=<n>` card. This is a simulation- "
        "cost optimization, not a fidelity change -- an ideal parallel "
        "combination of n identical devices *is* `m=n` in SPICE -- needed "
        "because 959 individually-instantiated fingers (one per drawn finger, "
        "this script's default) cost roughly three orders of magnitude more "
        "simulation time than the same circuit as `m=`-scaled instances, to "
        "the point of being PVT-grid-infeasible within a bounded evidence "
        "run.",
    ),
    (
        "T7",
        "(issue #166/#201) Passive cards: a CAP_CLASSES device (this design's "
        "only case: the four-deep XCCOMP MiM series stack) has no d/g/s/b "
        "terminals and no gf180mcu subcircuit to rebind to -- it is emitted "
        "directly as an ngspice `C<n> a b <value>` card, `value` carried "
        "through verbatim from the extractor's own measured `params.c_f` "
        "(the same two-term area+perimeter model make_reference.py's "
        "transform 6 restates over the schematic geometry). Never grouped by "
        "--combine: with only four instances there is no simulation-cost "
        "case for folding them, and each occupies a distinct position in the "
        "series chain (distinct nets), so no two are ever combine-eligible "
        "anyway. Its two terminals still route through T5's per-net leg "
        "resistor the same as any MOS terminal when --parasitics is present "
        "-- the merged-ground body-terminal skip below is scoped to MOS "
        "devices only so it cannot mistake a capacitor's `b` terminal for a "
        "MOS body leg.",
    ),
    (
        "T8",
        "(issue #201) Anonymous-net rename: any net the extractor names "
        "`$N` (its own convention for a net with no schematic label -- this "
        "design's first real case is T7's XCCOMP inter-cap nodes) is "
        "rewritten to `ANON<N>` wherever it would otherwise appear as a "
        "bare SPICE node token. `$` starting a token is an inline-comment "
        "marker to ngspice, so left as-is these nets silently truncate "
        "every card that names them -- no simulator error, just a per-card "
        "`... is not a valid ... line, ignored!` warning outside this "
        "script's or run_corners.py's own PASS/FAIL summary. Applied at "
        "every point a raw extractor net name reaches a bare node position "
        "(`leg_of()`'s return, and T5's per-net star loop); never applied "
        "to a name only ever embedded inside a longer instance name (e.g. "
        "an R-leg card's own `R$18__t0` name field), since a `$` that is "
        "not a token's first character does not trigger this.",
    ),
]

BACK_ANNOTATIONS = [
    "BA1  NMOS body -> GND_LOGIC (3.3V flavor) / GND_DRV (6V flavor)",
    "     (issue #132: real substrate-tie geometry now measures this same",
    "      assignment directly -- klt lvs reports zero device.body_unverified",
    "      mismatches for either flavor. Kept as a rebind, not a fabrication,",
    "      so GND_LOGIC/GND_DRV keep separate names here -- see T4)",
    "BA2  PMOS body -> VDD_LOGIC (3.3V flavor) / VDD_DRV (6V flavor)",
    "     (issue #132: real well-tie geometry now measures this same",
    "      assignment directly, per device -- redundant with T4, not a gap)",
    "BA3  parasitic ground-cap reference `vsubs` -> GND_LOGIC",
    "     (GND_LOGIC/GND_DRV are one electrical node by design intent;",
    "      GND_LOGIC is the documented, arbitrary choice of the two. `vsubs`",
    "      itself no longer appears in a real extraction of this layout --",
    "      see make_reference.py transform 3 -- but a --parasitics run's",
    "      own per-net table is still keyed by the schematic's pre-merge",
    "      net names, so this rename is still the correct lookup key)",
]


def _fmt(value: float) -> str:
    return f"{value:.6g}"


#: `klt extract` names an internal net with no schematic label `$N` (its own
#: anonymous-net numbering) -- this design's first real case is #166's XCCOMP
#: series stack, whose three inter-cap nodes (schematic `nccomp1..3`) carry no
#: label anywhere in the layout. A `$`-prefixed net is not just an odd
#: spelling: a SPICE token that *starts* with `$` is an inline-comment marker
#: to ngspice (confirmed directly -- `$18` mid-token, e.g. embedded in an
#: instance name like `R$18__t0`, is fine; `$18` as its own bare
#: whitespace-delimited token is not), so emitting one as a bare node
#: silently truncates the rest of that card: no simulator error, just a
#: `<card> is not a valid ... line, ignored!` warning `run_corners.py`'s own
#: PASS/FAIL summary never surfaces (issue #201 -- caught only by manually
#: reading ngspice's own log after the XCCOMP caps it should have added
#: measured *zero* effect on every corner, bit-for-bit). See T8.
def _spice_node(name: str) -> str:
    return "ANON" + name[1:] if name.startswith("$") else name


def _model_and_body(device_class: str, l_um: float) -> tuple[str, str]:
    key = (device_class, round(l_um, 2))
    try:
        return MODEL_AND_BODY_BY_CLASS_L[key]
    except KeyError as exc:
        raise SystemExit(
            f"no gf180mcu model bound for extracted device class={device_class!r} "
            f"L={l_um!r}um -- MODEL_AND_BODY_BY_CLASS_L does not cover this "
            "(class, L) pair; a new device flavor was added to the design "
            "netlist without updating this script"
        ) from exc


def _leg_lookup(parasitics: dict | None) -> dict[tuple[str, str], str]:
    """``(device_name, terminal_letter) -> leg_net`` from ``parasitics.nets[]``.

    A device terminal on a net the extractor did not compute parasitics for
    has no entry here; :func:`emit` falls back to the net's own name for
    those (no star, a direct connection). Issue #132's real body-tie geometry
    means body terminals *do* now get a real entry here (the deck measures a
    genuine leg resistance for them, same as any other terminal) -- but
    :func:`emit` never looks one up for the body slot (T4 rebinds it directly
    to a real rail with no series R instead, see that transform's docstring),
    so this lookup is only ever consulted for d/g/s.
    """
    lookup: dict[tuple[str, str], str] = {}
    if parasitics is None:
        return lookup
    for net in parasitics["nets"]:
        for terminal in net["terminals"]:
            lookup[(terminal["device"], terminal["terminal"].lower())] = terminal["leg_net"]
    return lookup


def emit(extract: dict, combine: bool = False) -> tuple[list[str], dict]:
    parasitics = extract.get("parasitics")
    legs = _leg_lookup(parasitics)

    lines: list[str] = [
        "* FLAT form: device/parasitic cards at deck level, no `.SUBCKT` wrapper --",
        "* matches this repo's existing DUT-fragment convention (T1).",
        "",
    ]
    counts: dict[str, int] = {}

    # T6 (only with --combine): fold parallel-identical fingers back into one
    # `m=<n>` card. `klt gen mos_array` draws each schematic device's `nf*m`
    # fingers sharing one source/drain/gate strap (layout/gen_gate_driver_core.py),
    # so after T4's body back-annotation every finger of one schematic device
    # has an *exactly* identical (model, d, g, s, body, L, W, AD, AS, PD, PS) --
    # this groups on that exact tuple, never an approximation, so it changes
    # nothing about the extracted electrical topology (an ideal parallel
    # combination of N identical devices *is* `m=N` in SPICE). What it does
    # change is simulation cost: 959 individually-instantiated BSIM fingers
    # (one per drawn finger, T2's default) converges/steps far slower than the
    # schematic's own `m=`-scaled instances, to the point of being
    # PVT-grid-infeasible within a bounded evidence run (see layout/README.md
    # / the postlayout sim record's own note) -- `--combine` restores
    # simulation-feasible device counts by construction, not by relaxing
    # fidelity. Not compatible with `--parasitics` cards (T5): a combined
    # device's per-finger parasitic legs are NOT identical (each finger's own
    # physical position gives it its own leg resistance), so `--combine`
    # refuses a parasitics-bearing extraction rather than silently dropping
    # per-finger leg fidelity -- see `main()`.
    def _is_merged_ground(raw: str) -> bool:
        return raw == MERGED_GROUND_RAW or raw.startswith(MERGED_GROUND_RAW + "__")

    def _assert_nmos_ground(dev: dict, terminal: str, raw: str) -> None:
        """Only an NMOS terminal is expected to ever land on the deck's merged
        ground identity (confirmed against the schematic: no PMOS device names
        either ground net). A PMOS terminal landing there would mean this
        design grew a real PMOS-to-ground connection this script's (class, L)
        body table was never taught about, so that case raises rather than
        silently rebinding to that flavor's *supply* rail.
        """
        if dev["class"] != "nfet":
            raise SystemExit(
                f"device {dev['name']!r} ({dev['class']}) terminal {terminal!r} landed on "
                f"the deck's merged ground identity ({raw!r}) -- only NMOS terminals are "
                "expected to; MODEL_AND_BODY_BY_CLASS_L / this rebind needs a new case"
            )

    def leg_of(dev: dict, terminal: str, own_ground: str) -> str:
        """This terminal's net (or its per-terminal parasitic leg), with the
        deck's merged ground identity resolved *per device* -- see
        ``MERGED_GROUND_RAW``'s own docstring for why a device-specific
        resolution, not a fixed one, is required here. Every other terminal's
        real, measured net passes through unchanged.

        Two merged-ground cases, and the difference matters:

        * The terminal has a **measured parasitic leg** on the merged net
          (``GND_DRV|GND_LOGIC__t<n>``, a ``--parasitics`` run): keep that leg
          as this terminal's node, only renamed to a SPICE-legal form. T5
          emits its series R down to this same device's own real rail, so the
          rail IR drop the extractor measured stays in the model (issue #184).
        * The terminal has **no measured leg** (a non-``--parasitics``
          extraction): there is nothing to route through, so bind straight to
          this device's own real rail.
        """
        raw = legs.get((dev["name"], terminal), dev["nets"][terminal])
        if not _is_merged_ground(raw):
            return _spice_node(raw)  # T8: e.g. XCCOMP's anonymous inter-cap nodes
        _assert_nmos_ground(dev, terminal, raw)
        if raw == MERGED_GROUND_RAW:
            return own_ground
        return MERGED_GROUND_NODE + raw[len(MERGED_GROUND_RAW) :]

    # T7: CAP_CLASSES devices (this design's only case: the four `XCCOMP*` MiM
    # caps) have no d/g/s/b terminals, so they are pulled out of the MOS
    # loops below entirely rather than forced through `_model_and_body`.
    mos_devices = [dev for dev in extract["devices"] if dev["class"] not in CAP_CLASSES]
    cap_devices = [dev for dev in extract["devices"] if dev["class"] in CAP_CLASSES]

    if not combine:
        for dev in sorted(mos_devices, key=lambda d: (d["class"], d["name"])):
            cls, name, params = dev["class"], dev["name"], dev["params"]
            model, body = _model_and_body(cls, params["l_um"])
            counts[model] = counts.get(model, 0) + 1
            inst = name.lstrip("$")
            lines.append(
                f"X{inst} {leg_of(dev, 'd', body)} {leg_of(dev, 'g', body)} "
                f"{leg_of(dev, 's', body)} {body} {model} "
                f"L={_fmt(params['l_um'])}U W={_fmt(params['w_um'])}U nf=1 "
                f"ad={_fmt(params['ad_um2'])}P as={_fmt(params['as_um2'])}P "
                f"pd={_fmt(params['pd_um'])}U ps={_fmt(params['ps_um'])}U m=1"
            )
    else:
        grouped: dict[tuple, list[dict]] = {}
        for dev in mos_devices:
            cls, params = dev["class"], dev["params"]
            model, body = _model_and_body(cls, params["l_um"])
            key = (
                model, leg_of(dev, "d", body), leg_of(dev, "g", body), leg_of(dev, "s", body), body,
                round(params["l_um"], 6), round(params["w_um"], 6),
                round(params["ad_um2"], 6), round(params["as_um2"], 6),
                round(params["pd_um"], 6), round(params["ps_um"], 6),
            )
            grouped.setdefault(key, []).append(dev)

        for index, (key, members) in enumerate(sorted(grouped.items()), start=1):
            model, d, g, s, body, l_um, w_um, ad, as_, pd, ps = key
            counts[model] = counts.get(model, 0) + len(members)
            lines.append(
                f"X{index} {d} {g} {s} {body} {model} "
                f"L={_fmt(l_um)}U W={_fmt(w_um)}U nf=1 "
                f"ad={_fmt(ad)}P as={_fmt(as_)}P "
                f"pd={_fmt(pd)}U ps={_fmt(ps)}U m={len(members)}"
            )

    if cap_devices:
        lines += ["", "* T7: passive cards (CAP_CLASSES devices -- issue #166's XCCOMP stack)"]
        for dev in sorted(cap_devices, key=lambda d: d["name"]):
            cls, name, params = dev["class"], dev["name"], dev["params"]
            counts[cls] = counts.get(cls, 0) + 1
            inst = name.lstrip("$")
            lines.append(
                f"C{inst} {leg_of(dev, 'a', dev['nets']['a'])} "
                f"{leg_of(dev, 'b', dev['nets']['b'])} {_fmt(params['c_f'])}"
            )

    par_count = {"r": 0, "c": 0}
    if parasitics is not None:
        lines += ["", "* T5: per-net parasitic star (klt extract --parasitics), coupling excluded"]
        # The deck's merged ground identity (MERGED_GROUND_RAW) is the one net
        # whose star is NOT a single hub: since issue #132 the extractor
        # reports both drawn ground rails under one label (klayout-tools
        # #1128), and this design's two ground domains are two nodes bridged by
        # a milliohm-scale tie, not one node (decision record 0001 Decision 1;
        # the postlayout testbench simulates exactly that). So its star is
        # emitted with each leg's HUB rebound per-device, the same way
        # `leg_of()` rebinds the leg net itself: leg -> R -> that leg's own
        # device's real GND_LOGIC/GND_DRV, keyed by the same disjoint
        # (class, L) binning as T4/BA1.
        #
        # A single shared hub here -- whatever it is named -- is known wrong,
        # not merely imprecise: it would put every 6 V device's return current
        # on the same node as the 3.3 V devices', i.e. route the output
        # stage's sink current through the testbench's inter-rail tie resistor
        # instead of straight to the load's own return (see
        # MERGED_GROUND_RAW's docstring, and the full-PVT regression cited
        # there). The per-device form has no such node: it reproduces exactly
        # the pre-#132 topology, where each ground net's own `hub_net` WAS
        # that rail's node, at the same 297 legs (issue #184).
        #
        # MOS body terminals stay excluded on every net, merged or not
        # (`terminal["terminal"] == "B"` -- they do carry a real measured
        # resistance now that issue #132 draws real tap geometry): `emit()`
        # never calls `leg_of()` for the body slot, T4 binds it directly to a
        # real rail with no series R, so a body leg node would be referenced
        # by its R card alone. Scoped to non-CAP_CLASSES (MOS) devices so a
        # CAP_CLASSES device's own `b` terminal -- a real capacitor plate,
        # not a body -- is never mistaken for one and dropped (issue
        # #166/#201's T7).
        devices_by_name = {dev["name"]: dev for dev in extract["devices"]}
        for net in sorted(parasitics["nets"], key=lambda n: n["net"]):
            merged = net["net"] == MERGED_GROUND_RAW
            hub = _spice_node(net["hub_net"])  # T8: e.g. an XCCOMP inter-cap net's own hub
            for terminal in net["terminals"]:
                term_dev = devices_by_name[terminal["device"]]
                if term_dev["class"] not in CAP_CLASSES and terminal["terminal"].upper() == "B":
                    continue
                leg = terminal["leg_net"]
                leg_hub = hub
                if merged:
                    dev = devices_by_name[terminal["device"]]
                    _assert_nmos_ground(dev, terminal["terminal"].lower(), leg)
                    leg_hub = _model_and_body(dev["class"], dev["params"]["l_um"])[1]
                    leg = MERGED_GROUND_NODE + leg[len(MERGED_GROUND_RAW) :]
                else:
                    leg = _spice_node(leg)  # T8: e.g. an XCCOMP inter-cap net's own leg
                lines.append(f"R{leg} {leg} {leg_hub} {_fmt(terminal['resistance_ohm'])}")
                par_count["r"] += 1
            if merged:
                # One measured lumped ground capacitance for metal that spans
                # both rails, and no per-domain split reported to apportion it
                # by. Emitted whole between the two real rails the merged
                # identity names -- which is where the pre-#132 GND_DRV star's
                # own cap landed too (its reference, GROUND_REF/BA3, is the
                # other rail), so nothing measured is dropped and nothing is
                # invented. The pre-#132 GND_LOGIC star's cap had no such
                # place: referenced to GROUND_REF it was a cap from GND_LOGIC
                # to itself, a degenerate no-op card, which is why this is 17
                # C where pre-#132 was 18.
                lines.append(
                    f"C{MERGED_GROUND_NODE} {MERGED_GROUND_RAILS[0]} {MERGED_GROUND_RAILS[1]} "
                    f"{_fmt(net['capacitance_ff'] * 1e-15)}"
                )
            else:
                lines.append(
                    f"C{_spice_node(net['net'])} {hub} {GROUND_REF} "
                    f"{_fmt(net['capacitance_ff'] * 1e-15)}"
                )
            par_count["c"] += 1

    return lines, {"devices": counts, "parasitics": par_count}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", type=Path, required=True, help="<rid>.extract.json")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument(
        "--combine",
        action="store_true",
        help="fold parallel-identical fingers back into one m=<n> card (T6) -- "
        "restores simulation-feasible device counts for a PVT-grid re-run; "
        "refuses an extraction that carries --parasitics cards (T5), since a "
        "combined device's per-finger parasitic legs are not identical",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; fail if the committed output has drifted",
    )
    args = parser.parse_args()
    args.extract = args.extract.resolve()
    args.output = args.output.resolve()

    extract = json.loads(args.extract.read_text())
    if args.combine and extract.get("parasitics"):
        print(
            "error: --combine is not compatible with a --parasitics extraction "
            "(T5's per-finger leg resistances are not identical across a "
            "combined device's members) -- re-run `klt extract` without "
            "--parasitics for a --combine build",
            file=sys.stderr,
        )
        return 1
    lines, info = emit(extract, combine=args.combine)

    header = [
        "* Post-layout EXTRACTED DUT netlist -- GENERATED, do not edit by hand.",
        "*",
        f"* extract report : {args.extract.relative_to(REPO_ROOT)}",
        f"* layout gds     : {extract['file']}",
        f"* extraction deck: {extract['deck']} "
        f"({extract['provenance']['deck']['content_hash']})"
        f"  (klt extract{' --parasitics' if extract.get('parasitics') else ''})",
        f"* klt/klayout    : {extract['provenance']['klt_version']} / "
        f"{extract['provenance']['klayout_version']}",
        f"* devices        : {extract['device_count']} {extract['device_counts']} -> {info['devices']}",
    ]
    if extract.get("parasitics"):
        header.append(
            f"*   parasitics    : {info['parasitics']['r']} R / {info['parasitics']['c']} C "
            "(per-net ground star only; net-to-net coupling NOT modeled, see T5)"
        )
    header += [
        "* regenerate     : python3 layout/lvs/mk_extracted_dut.py"
        f" --extract {args.extract.relative_to(REPO_ROOT)}"
        f"{' --combine' if args.combine else ''}"
        f" -o {args.output.relative_to(REPO_ROOT)}",
        "*",
        "* ------------------------------------------------------------------",
        "* Mechanical transforms applied to the extractor's own output",
        "* ------------------------------------------------------------------",
    ]
    for key, text in TRANSFORMS:
        wrapped = _wrap(text, 74)
        header.append(f"* {key}. {wrapped[0]}")
        header += [f"*     {line}" for line in wrapped[1:]]
    header += [
        "*",
        "* ------------------------------------------------------------------",
        "* Back-annotated: terminals/nets the extraction deck cannot resolve",
        "* ------------------------------------------------------------------",
    ]
    header += [f"* {line}" for line in BACK_ANNOTATIONS]
    header += [
        "*",
        "* Everything else -- device existence, drawn W/L/AS/AD/PS/PD,",
        "* drain/gate/source connectivity, and (when present) the per-net",
        "* ground-referenced RC parasitics -- is measured, not asserted.",
        "",
    ]

    body = "\n".join(header + lines) + "\n"
    digest = hashlib.sha256(body.encode()).hexdigest()
    body = body.replace(
        "* Everything else",
        f"* sha256 (this file, sans this line): {digest[:32]}\n* Everything else",
        1,
    )

    if args.check:
        if not args.output.exists() or args.output.read_text() != body:
            print(f"error: {args.output} is stale; re-run without --check")
            return 1
        print(f"ok: {args.output} matches the committed extraction report")
        return 0

    args.output.write_text(body)
    print(f"wrote {args.output.relative_to(REPO_ROOT)}")
    print(f"  devices: {sum(info['devices'].values())} {info['devices']}")
    if extract.get("parasitics"):
        print(f"  parasitics: {info['parasitics']['r']} R / {info['parasitics']['c']} C")
    return 0


def _wrap(text: str, width: int) -> list[str]:
    words, out, cur = text.split(), [], ""
    for word in words:
        if cur and len(cur) + 1 + len(word) > width:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        out.append(cur)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
