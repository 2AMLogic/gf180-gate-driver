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

#: Ground reference every net's parasitic ground capacitor ties to, replacing
#: the deck's synthesized `vsubs` substrate net (`klt extract`'s single
#: global body/ground-plane node -- there is no drawn p-substrate tap layer
#: to derive a real target from). GND_LOGIC and GND_DRV are two pins but one
#: electrical reference node by design intent (design/netlist/
#: gate_driver_core.spice's header comment, decision record 0001 Decision 1)
#: -- GND_LOGIC is the arbitrary (but documented) choice of the two. See
#: TRANSFORMS T4/BA3.
GROUND_REF = "GND_LOGIC"

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
        "MOS body terminal: rebound from the deck-synthesized floating net "
        "(a single global `vsubs` for every NMOS, one anonymous, "
        "un-merged-per-instance well island for every PMOS -- "
        "layout/README.md's \"no well or substrate taps drawn\" gap) to the "
        "real rail this design's schematic ties that flavor to -- GND_LOGIC/"
        "GND_DRV for NMOS, VDD_LOGIC/VDD_DRV for PMOS, selected by the same "
        "(class, L) binning as T2. This asserts the *intended* body bias; it "
        "does not model the drawn (absent) tap geometry that would carry it "
        "in real silicon -- see BA1/BA2 and layout/README.md.",
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
        "omitted, stated once here rather than per-record.",
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
]

BACK_ANNOTATIONS = [
    "BA1  NMOS body -> GND_LOGIC (3.3V flavor) / GND_DRV (6V flavor)",
    "     (deck has no p-substrate tap layer to key on)",
    "BA2  PMOS body -> VDD_LOGIC (3.3V flavor) / VDD_DRV (6V flavor)",
    "     (deck has no well-tap layer to key on)",
    "BA3  parasitic ground-cap reference `vsubs` -> GND_LOGIC",
    "     (GND_LOGIC/GND_DRV are one electrical node by design intent;",
    "      GND_LOGIC is the documented, arbitrary choice of the two)",
]


def _fmt(value: float) -> str:
    return f"{value:.6g}"


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
    (only named/pin nets get an entry -- confirmed against a real
    ``--parasitics`` run: exactly the 18 named nets, never the synthesized
    `vsubs` substrate net or an anonymous PMOS well island) has no entry
    here; :func:`emit` falls back to the net's own name for those (no star,
    a direct connection) -- which is exactly every body terminal, since T4
    replaces those with a real rail before this lookup would ever be
    consulted for them.
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
    def leg_of(dev: dict, terminal: str) -> str:
        return legs.get((dev["name"], terminal), dev["nets"][terminal])

    if not combine:
        for dev in sorted(extract["devices"], key=lambda d: (d["class"], d["name"])):
            cls, name, params = dev["class"], dev["name"], dev["params"]
            model, body = _model_and_body(cls, params["l_um"])
            counts[model] = counts.get(model, 0) + 1
            inst = name.lstrip("$")
            lines.append(
                f"X{inst} {leg_of(dev, 'd')} {leg_of(dev, 'g')} {leg_of(dev, 's')} {body} {model} "
                f"L={_fmt(params['l_um'])}U W={_fmt(params['w_um'])}U nf=1 "
                f"ad={_fmt(params['ad_um2'])}P as={_fmt(params['as_um2'])}P "
                f"pd={_fmt(params['pd_um'])}U ps={_fmt(params['ps_um'])}U m=1"
            )
    else:
        grouped: dict[tuple, list[dict]] = {}
        for dev in extract["devices"]:
            cls, params = dev["class"], dev["params"]
            model, body = _model_and_body(cls, params["l_um"])
            key = (
                model, leg_of(dev, "d"), leg_of(dev, "g"), leg_of(dev, "s"), body,
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

    par_count = {"r": 0, "c": 0}
    if parasitics is not None:
        lines += ["", "* T5: per-net parasitic star (klt extract --parasitics), coupling excluded"]
        for net in sorted(parasitics["nets"], key=lambda n: n["net"]):
            hub = net["hub_net"]
            for terminal in net["terminals"]:
                lines.append(
                    f"R{terminal['leg_net']} {terminal['leg_net']} {hub} "
                    f"{_fmt(terminal['resistance_ohm'])}"
                )
                par_count["r"] += 1
            lines.append(f"C{net['net']} {hub} {GROUND_REF} {_fmt(net['capacitance_ff'] * 1e-15)}")
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
