#!/usr/bin/env python3
"""Generate the ``gate_driver_core`` physical layout from its committed netlist.

This is the *reproducible provenance* for ``layout/gate_driver_core.gds``: the
GDS in this directory is not hand-drawn, it is the output of running this
script against ``design/netlist/gate_driver_core.spice`` and the gf180mcu PDK.

    python3 layout/gen_gate_driver_core.py            # writes layout/gate_driver_core.gds
    python3 layout/gen_gate_driver_core.py --out-dir /tmp/x   # scratch run

Flow (all geometry is produced by `klt`, per the repo's stated tooling -- this
script never links klayout itself and needs nothing but the standard library):

1.  Parse ``design/netlist/gate_driver_core.spice`` and flatten the three
    sub-cells (``level_shifter`` x1, ``output_stage`` x2, ``uvlo`` x3, issue
    #221) into one MOS device list, one MiM-capacitor list and one bare-``R``
    resistor list, all with top-level net names.
2.  ``klt gen mos_array`` once per netlist device. A netlist device with
    ``W=W nf=N m=M`` is drawn as a single ``1x1`` unit device folded into
    ``N*M`` parallel gate fingers of ``W/N`` each (``finger_topology:
    "parallel"``), which is exactly what those parameters mean in SPICE: ``M``
    parallel copies of one ``W``-wide transistor whose width is itself split
    across ``N`` fingers, all sharing one source/drain/gate strap. The total
    drawn width is ``W*M`` whatever ``N`` is, and that is what ``klt extract``
    reads back. Every device in the committed netlist has ``nf=1``, where this
    is ``M`` fingers of width ``W``.
3.  ``klt draw`` once for the interconnect/marker cell: the Metal2 net rails,
    the Metal1 device stubs and gate routes, the Via1 stack between them, the
    net-name labels, the two voltage-domain marker regions
    (``DNWELL``/``LVPWELL`` over the 5V/6V group, ``Dualgate`` over the same),
    and the ``XCCOMP*`` MiM capacitor stack -- Metal4 bottom plates, FuseTop
    top plates with their ``CAP_MK``/``MIM_L_MK`` recognition markers, the
    Metal5 straps over their Via4s, and the Via3/Metal3/Via2 escape down to
    the two Metal2 rails the series chain terminates on
    (:meth:`Interconnect.mim_caps`).
4.  ``klt gen-compose`` (``placement.strategy: "explicit"``) merges every
    device cell, every resistor cell and the interconnect cell into one
    ``gate_driver_core`` top cell at the origins this script computed.
5.  ``klt gen res_array`` once per netlist ``R`` element -- ``uvlo``'s
    ``Rref``/``R1``/``R2``/``Rfb`` (issue #221), folded into ``num`` series
    unit resistors and chained by :meth:`Interconnect.resistors`. See
    :func:`resistor_array_params`.

Floorplan
---------

Every device is a left-aligned horizontal strip; strips stack upward in
netlist order, thin-oxide (3.3V logic) group first, then a domain gap, then
the thick-oxide (5V/6V drive) group.  ``klt gen``'s ``mos_array`` reports the
source pad on a strip's left edge (facing 180), the drain pad on its right
edge (facing 0) and the gate pad on its top edge (facing 90), so:

* net rails run vertically on **Metal2**, in a channel to the left of the
  strips (sources + gates) and a channel to their right (drains);
* a **Metal1** stub runs horizontally out of each pad to its rail and drops a
  **Via1** there; a gate route goes up out of the strip, then horizontally
  through the empty channel above it to the left rail;
* each net's left and right rail are tied together by one horizontal Metal1
  jumper in a cross-over band above the whole stack.

Metal1 stubs therefore cross *under* unrelated Metal2 rails with no via, which
is what keeps a purely orthogonal, no-router wiring scheme short-free.

The ``XCCOMP*`` MiM series stack sits in its own single row of four plates,
placed north of every drawn shape in the block (above the guard ring's own
north stroke, over bare substrate), so nothing at all -- least of all anything
matching-sensitive, per DRM 10.4.2 -- sits underneath it.  It reaches the two
Metal2 rails its chain terminates on through Metal3, on a layer stack that
crosses over the whole interconnect without a single via into it.  See
:meth:`Interconnect.mim_caps`.

Known limitations of this first-cut layout (deliberately not fixed here -- see
``layout/README.md`` and issue #105, which owns DRC/LVS closure):

* No well/substrate taps, no guard ring around ``DNWELL_DRV``.  A closed tap
  ring around the drive domain has to be cut for every signal crossing the
  domain boundary, which is a routing plan, not a marker rectangle.
* Device aspect ratios are whatever ``m`` folds into a single row.
* Not DRC-clean and not LVS-clean; ``klt drc`` has never been run on it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys

# --------------------------------------------------------------------------- #
# Repo layout
# --------------------------------------------------------------------------- #

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
NETLIST_PATH = os.path.join(REPO_ROOT, "design", "netlist", "gate_driver_core.spice")

TOP_CELL = "gate_driver_core"
DEFAULT_PDK = "gf180mcuD"

# --------------------------------------------------------------------------- #
# gf180mcu drawing layers used by the interconnect cell.
#
# Every number below is the gf180mcu PDK's own, cross-checked against
# $PDK_ROOT/$PDK/libs.tech/klayout/{drc,lvs}/rule_decks/layers_def*.
# The Metal1/Metal2/Via1 triple matches the roles `klt gen`'s own generators
# draw on (`metal`/`metal2`/`via1`), so a stub lands on the same layer as the
# device pad it starts from.
# --------------------------------------------------------------------------- #

L_DNWELL = (12, 0)
L_LVPWELL = (204, 0)
L_DUALGATE = (55, 0)
L_COMP = (22, 0)  # Comp -- gf180mcu's single diffusion/active/tap layer; klt's
# curated deck resolves both "active" and "tap" roles to this same number, so
# a body-tie tap is drawn on it exactly like ordinary MOS active (see
# body_ties()'s docstring for why that single-layer choice matters for LVS).
L_CONTACT = (33, 0)  # Contact -- Comp/Poly2 <-> Metal1
L_NWELL = (21, 0)  # Nwell -- pfet body / well-tap layer
L_PPLUS = (31, 0)  # Pplus -- substrate/p-well tie implant
L_NPLUS = (32, 0)  # Nplus -- gf180mcu's `tap_nplus` derivation input (klt
# issue #1084): `tap_nplus & active & nwell` is what `klt extract` recognises
# as a genuine well tie for this deck (it has no distinct tap mask -- see
# body_ties()'s docstring). Without this layer, an ordinary Comp+Contact+
# Metal tap inside Nwell reads as indistinguishable from ordinary PMOS
# source/drain diffusion and is *not* derived into a tap at all -- confirmed
# empirically (a first pass of this generator without L_NPLUS still extracted
# every PMOS body onto its own anonymous net, unchanged).
L_METAL1 = (34, 0)
L_METAL1_LABEL = (34, 10)
L_VIA1 = (35, 0)
L_METAL2 = (36, 0)
L_METAL2_LABEL = (36, 10)

# Upper routing stack + the MiM capacitor's own layers (issue #166).  Numbers
# are `klt`'s own gf180mcu deck (`decks/gf180mcu.py`'s `LAYER_NAMES` and
# `EXTRACTION_DECK.metals`/`vias`), which transcribes them from the PDK's
# `main.drc` via-layer derivations -- the same table the Metal1/Via1/Metal2
# triple above comes from.  `metals` is the full Metal1..Metal5 stack and
# `vias[i]` joins `metals[i]` to `metals[i+1]`, so Via2/Metal3/Via3 is the
# only escape path from a Metal4 bottom plate down to this layout's Metal2
# rails.
L_VIA2 = (38, 0)  # Via2  -- Metal2 <-> Metal3
L_METAL3 = (42, 0)
L_VIA3 = (40, 0)  # Via3  -- Metal3 <-> Metal4
L_METAL4 = (46, 0)  # MiM bottom plate ("topmin1_metal" for the 5LM stack)
L_VIA4 = (41, 0)  # Via4  -- Metal4 <-> Metal5, and FuseTop <-> Metal5
L_METAL5 = (81, 0)
L_FUSETOP = (75, 0)  # MiM top plate
L_CAP_MK = (117, 5)  # MiM device-recognition marker
L_MIM_L_MK = (117, 10)  # MiM device-recognition marker (second of the pair)

# --------------------------------------------------------------------------- #
# Floorplan constants (um)
# --------------------------------------------------------------------------- #

CHANNEL_UM = 3.2  # vertical gap between stacked device strips
DOMAIN_GAP_UM = 20.0  # 3.3V group top -> 5V/6V group bottom
RAIL_WIDTH_UM = 0.8  # Metal2 net rail
RAIL_PITCH_UM = 1.6
RAIL_MARGIN_UM = 6.0  # first rail's offset from the device column
STUB_WIDTH_UM = 0.42  # Metal1 pad stub / gate route
VIA_SIZE_UM = 0.26  # Via1 square
LANDING_UM = 0.6  # Metal1 landing pad around a via
JUMPER_WIDTH_UM = 0.6  # Metal1 left-rail <-> right-rail jumper
JUMPER_PITCH_UM = 1.4
JUMPER_BAND_GAP_UM = 4.0  # stack top -> first jumper
DNWELL_MARGIN_UM = 4.0  # DNWELL_DRV enclosure of the 5V/6V group
LVPWELL_MARGIN_UM = 1.2  # LVPWELL enclosure of one 5V/6V nfet strip -- also
# the enclosure every per-device WELL_TIE_MARGIN_UM rectangle uses (bumped
# from the original 1.0 so a body tap -- offset TAP_LEFT_OFFSET_UM/
# TAP_TOP_OFFSET_UM outside the device's own bbox -- lands comfortably inside
# it; still well under half of CHANNEL_UM (1.6), so it never reaches a
# vertically-stacked neighbour's own bbox, and leaves >=0.6um clear of an
# *adjacent* pfet's own WELL_TIE_MARGIN_UM rectangle when two same-flavor
# devices are stacked back to back (3.2 - 2*1.2 = 0.8 > nwell.space.1's
# 0.6um "merge below this" threshold -- see body_ties()).
DUALGATE_MARGIN_UM = 2.0  # Dualgate enclosure of the 5V/6V group

# Per-device body-tie tap (body_ties()) and PMOS well-tie rectangle sizing.
# CONTACT_SIZE_UM/ENCLOSURE_MARGIN_UM/WELL_ENCLOSURE_MARGIN_UM below mirror
# klayout-tools' own generator constants (gen.py) so a hand-drawn tap clears
# the same gf180mcu DRC thresholds `klt gen`'s own generators are sized
# against, without re-deriving them independently.
CONTACT_SIZE_UM = 0.22  # contact.width.1 (CO.1)
ENCLOSURE_MARGIN_UM = 0.10  # comp.enclosing.contact.1 / poly2.enclosing.contact.1 (CO.3/CO.4)
TAP_COMP_UM = CONTACT_SIZE_UM + 2 * ENCLOSURE_MARGIN_UM  # 0.42um Comp tap pad
TAP_LEFT_OFFSET_UM = 0.6  # tap center, left of the device's own bbox.x0
TAP_TOP_OFFSET_UM = 0.6  # tap center, above the device's own bbox.y1
WELL_TIE_MARGIN_UM = 1.2  # PMOS per-device Nwell-tie rectangle margin --
# same value/rationale as LVPWELL_MARGIN_UM above (both must clear the tap
# offset and stay under half of CHANNEL_UM / away from nwell.space.1).
GUARD_RING_MARGIN_UM = 5.5  # PCOMP guard ring offset -- genuinely *outside*
# DNWELL_MARGIN_UM=4.0 so the ring sits around the DNWELL_DRV marker (DRM
# 7.2's own intent: a P+ ring in the substrate surrounding the deep-nwell,
# not inside it) with a real, non-touching 0.5um gap from DNWELL_DRV's own
# edge -- `klt components`/`check_gate_driver_core.py`'s `dnwell_partition`
# check groups any Comp shape *touching* a DNWELL region into that DNWELL's
# own component (the same mechanism the check itself uses to assert 3.3V/
# 5V/6V separation), so a ring that merely abutted DNWELL_DRV would pull
# every one of its 4 strokes into that count -- confirmed empirically (a
# margin of 4.5, one edge touching, inflated `active_regions_in_dnwell` by
# the ring's own 4 raw rectangles on top of the expected per-tap adjustment
# below). Also far enough from every per-device body_ties() tap (offset only
# TAP_LEFT_OFFSET_UM/TAP_TOP_OFFSET_UM=0.6um past a device's own bbox) to
# clear comp.space.1 (0.28um) between the ring's Comp and a tap's own Comp --
# worst case (a device that itself defines the group bbox edge) leaves
# (5.5 - GUARD_RING_WIDTH_UM) - (TAP_LEFT_OFFSET_UM + TAP_COMP_UM/2)
# = 4.5 - 0.81 = 3.69um clearance, comfortably over 0.28um. The ring's own
# Metal1-layer neighbours (the jumper band, gate-route channels) never
# interact with it at all since it draws bare Comp only -- see guard_ring().
GUARD_RING_WIDTH_UM = 1.0  # PCOMP guard ring stroke width
GUARD_RING_STROKE_COUNT = 4  # N/S/E/W rects guard_ring() draws (one Comp
# "active" shape each, positioned entirely outside DNWELL_DRV -- exported
# so check_gate_driver_core.py's dnwell_partition check can account for them
# in its own expected "active regions outside DNWELL" arithmetic).
GUARD_RING_STRAP_WIDTH_UM = STUB_WIDTH_UM  # Metal1 strap along the ring's own
# contacted N/S strokes -- same width as every other Metal1 stub/strap this
# generator draws, wide enough to enclose CONTACT_SIZE_UM with margin.
GUARD_RING_CONTACT_PITCH_UM = 2.0  # contact-row pitch along the ring's N/S
# strokes -- comfortably above contact.space (CO.2, 0.28um: pitch leaves a
# 2.0 - CONTACT_SIZE_UM = 1.78um gap between adjacent contacts).
GUARD_RING_JUMPER_CLEARANCE_UM = 1.0  # north stroke's own metal1.space.1
# clearance above jumpers()'s topmost jumper bar -- see guard_ring()'s own
# comment for why this can be needed at all (well over the deck's actual
# metal1.space.1 minimum, no reason to cut it close against a check that
# only needs to run once per regeneration).

# MiM capacitor row (issue #166 / spec/decision-records/0014).  Every number
# below is a DRM 10.4.2 "MIM Option B" rule minimum or a clearance derived
# from one; `klt`'s curated gf180mcu DRC deck transcribes three of them
# (MIMTM.1 -> `mim.space.1`, MIMTM.2 -> `mim.enclosing.via4.1`, MIMTM.3 ->
# `mim.enclosing.fusetop.1`), and the rest are honoured here because the DRM
# states them even though this deck does not yet check them -- see
# Interconnect.mim_caps()'s docstring.
MIM_BOTTOM_OVERLAP_UM = 0.6  # MIMTM.3: min. Metal4 bottom-plate overlap of the
# FuseTop top plate, on every side -- a 5.0um top plate therefore needs a
# 5.0 + 2*0.6 = 6.2um bottom plate.
MIM_PLATE_SPACE_UM = 1.2  # MIMTM.1: min. bottom-plate spacing to adjacent
# bottom-plate-or-routing Metal4.  Sets the row pitch (6.2 + 1.2 = 7.4um) and
# the clearance every non-plate Metal4 shape keeps from a plate.
MIM_TOP_VIA_ENCLOSURE_UM = 0.4  # MIMTM.5 (top plate over Via4) / MIMTM.2 (the
# virtual bottom plate over Via4).  The Via4 is drawn at the plate centre, so
# both enclosures come out at ~2.4/~3.0um rather than being set by this
# number -- mim_caps() checks the drawn geometry against it instead of laying
# out to it, so a future plate small enough to violate either rule fails the
# generator rather than the DRC run.
MIM_ROW_MARGIN_UM = 12.0  # bottom of the Metal4 plate row, above the whole
# block's own northmost drawn edge (the guard ring's north stroke).  Puts the
# row over bare substrate: DRM 10.4.2 asks that no matching-sensitive analog
# circuitry sit under a MiM, and "nothing at all" is the strongest form of
# that.  Also keeps the Metal3 escape lanes clear of the Metal2 rails' own
# top edge, so the only Metal3-to-Metal2 interaction anywhere is the two
# deliberate Via2 taps.
MIM_TAIL_WIDTH_UM = 1.0  # Metal4 stub out of an end plate, down to its Via3.
MIM_TAIL_DROP_UM = 0.5  # how far past the Via3 centre that stub runs.
MIM_BRIDGE_HEIGHT_UM = 3.0  # Metal4 bridge that makes two adjacent bottom
# plates one polygon (an interior series node -- see mim_caps()).
MIM_BRIDGE_OVERLAP_UM = 0.1  # bridge/strap overlap into the shape it merges
# with, so the union is one polygon rather than two abutting ones.
MIM_STRAP_WIDTH_UM = 1.0  # Metal5 strap over two adjacent top plates' Via4s.
MIM_STRAP_EXTEND_UM = 0.5  # how far past the outer Via4 centres it runs.
MIM_LANE_WIDTH_UM = 0.42  # Metal3 escape route (metal3.width.1 is 0.28).
MIM_LANE_GAP_UM = 4.0  # first Metal3 escape lane, below the plate row.
MIM_LANE_PITCH_UM = 3.0  # spacing between the two escape lanes.
MIM_RAIL_TAP_DROP_UM = 1.0  # Via2 tap point, below a Metal2 rail's own top.

# Thick-oxide (medium-voltage) model names -- the ones that must sit inside
# DNWELL_DRV + Dualgate and must never share a DNWELL with the 3.3V devices
# (spec/gate-driver.md 2.4, DRM 7.2, design/level-shifter-partition.md).
MV_MODELS = {"nfet_06v0", "pfet_06v0"}
LV_MODELS = {"nfet_03v3", "pfet_03v3"}

# uvlo's bias resistor network (issue #221): `Rref`/`R1`/`R2`/`Rfb` are bare
# SPICE `R` elements in design/netlist/uvlo.spice (an ideal ohms value, no
# physical W/L -- design/uvlo-comparator-sizing.md is explicit that a physical
# realization is *this* issue's scope, not #220's). `klt gen res_array`'s
# "generic" flavor is the only one this klt build implements for gf180mcu
# (its 'high'/'xhigh' sheet-rho options are sky130-only per `klt gen --list`,
# filed upstream as klayout-tools friction) -- it draws gf180mcu's base
# `ppolyf_u` device (350 ohm/sq, confirmed against a real `klt extract` run:
# `r_ohm == 350 * l_um / w_um` exactly, class `ppolyf_u`, 3 terminals a/b/w
# where `w` is the deck's global substrate identity -- the same one every
# NMOS body ties to, see body_ties()'s docstring).
#
# A single unit resistor at RES_WIDTH_UM would need an impractically long
# strip for uvlo's largest value (Rfb=16 Mohm is 19.2mm of 0.42um-wide poly),
# so :func:`resistor_array_params` folds it into `num` series unit resistors
# of `length_um` each (`Interconnect.resistors()` chains them with short
# Metal1 jumpers between consecutive `res_array` ports, using their own
# reported coordinates -- the same "matched array, wiring is the caller's
# job" contract `body_ties()`'s per-device taps already rely on), arranged
# into `rows` via `res_array`'s own boustrophedon fold.
RES_SHEET_RHO_OHM_SQ = 350.0  # ppolyf_u ('generic' res_array flavor), gf180mcu
RES_WIDTH_UM = 0.42  # unit resistor width -- res_array's own default
RES_SPACING_UM = 0.5  # res_array's own default unit-to-unit spacing
RES_MAX_UNIT_LENGTH_UM = 80.0  # cap on one series unit's drawn length
RES_UNITS_PER_ROW = 8  # units per res_array row-fold
RES_ROW_GAP_UM = 6.0  # vertical gap between two different resistors' blocks
RES_COLUMN_MARGIN_UM = 8.0  # device column's right rail -> resistor column
RES_ENDPOINT_CLEARANCE_UM = 1.0  # a resistor block's bbox -> its own escape
# lane (below the bottom row / above the top row) -- must stay under
# RES_ROW_GAP_UM so two vertically-stacked resistors' escape lanes never
# collide (see Interconnect.resistors()).


def resistor_array_params(value_ohm: float) -> tuple[int, int, float]:
    """``(num, rows, length_um)`` for a ``klt gen res_array`` request.

    ``num`` series unit resistors of ``length_um`` (all ``RES_WIDTH_UM`` wide),
    chained in series by :meth:`Interconnect.resistors`, draw ``value_ohm``
    exactly under gf180mcu's ``ppolyf_u`` sheet-rho model -- see
    :func:`resistor_ohms`, the exact inverse of this sizing arithmetic, which
    both this generator and ``lvs/make_reference.py`` call on the *same*
    ``(num, length_um)`` pair so the drawn geometry and the LVS reference
    cannot disagree about the resistor's value.
    """
    if value_ohm <= 0:
        raise GenError(f"resistor value must be > 0 ohm (got {value_ohm!r})")
    total_len_um = value_ohm * RES_WIDTH_UM / RES_SHEET_RHO_OHM_SQ
    min_num = max(1, math.ceil(total_len_um / RES_MAX_UNIT_LENGTH_UM))
    # Prefer an exact integer divisor of total_len_um for `num`, so every
    # series unit gets the *same*, exactly round-number length_um. This is
    # load-bearing, not cosmetic: `klt gen res_array`'s own row-fold geometry
    # has been observed to draw a handful of femto-ohm-scale length
    # differences between a row's "forward" and "mirrored" (boustrophedon)
    # orientations for a non-integer length_um -- confirmed against a real
    # `klt extract` run, an 880 kohm / 14-unit request (length_um =
    # 75.428571...) drew alternating 62857.5 / 62856.6666667 ohm units
    # instead of one consistent value (a ~1.3e-5 relative spread), which is
    # over `kdb.NetlistComparer`'s much tighter default tolerance (confirmed
    # separately: it matches a resistor value at a ~4e-7 relative difference
    # but not ~4e-6) and produced a real `klt lvs` topological mismatch on an
    # otherwise-correctly-wired chain. Every value this repo's committed
    # netlist actually resistor_array_params()s (800k/880k/200k/16M ohm)
    # makes total_len_um an exact integer, so this loop always finds a clean
    # divisor; a future value that does not still gets *a* valid sizing
    # (falling through to num=min_num) rather than a hard failure -- just
    # without this guarantee, which lvs/test_make_reference.py does not
    # exercise for such a value today.
    num = min_num
    total_len_int = round(total_len_um)
    if abs(total_len_um - total_len_int) < 1e-6 and total_len_int > 0:
        for candidate in range(min_num, total_len_int + 1):
            if total_len_int % candidate == 0:
                num = candidate
                break
        else:
            num = total_len_int
    length_um = total_len_um / num
    rows = max(1, math.ceil(num / RES_UNITS_PER_ROW))
    return num, rows, length_um


def resistor_ohms(num: int, length_um: float) -> float:
    """The series resistance ``num`` unit resistors of ``length_um`` draw."""
    return num * RES_SHEET_RHO_OHM_SQ * length_um / RES_WIDTH_UM

# Passive (non-MOS) device model families this netlist may contain.  gf180mcu
# spells its capacitor primitives `cap_mim_*` / `cap_nmos*` / `cap_pmos*`, and
# they carry `c_width`/`c_length` rather than a MOSFET's `W`/`L`.
PASSIVE_MODEL_PREFIXES = ("cap_",)

# The one passive model this generator can *draw* (issue #166).  `klt gen` has
# no capacitor generator in this repo's flow (`klt gen --list`: mos_array,
# diff_pair, guard_ring, res_array, esd_device, bjt_array, bond_pad,
# resistor_strip -- none of which is a MiM cap), so
# :meth:`Interconnect.mim_caps` draws the plate/marker/via geometry directly
# through `klt draw`, on exactly the layers `klt`'s own gf180mcu extraction
# deck recognises this device on (`decks/gf180mcu.py`'s
# `EXTRACTION_DECK.capacitors`, transcribed from the PDK's own
# `mimcap_extraction.lvs`).  A netlist passive of any *other* model still
# raises rather than being silently dropped -- see :func:`build`, which
# refuses to write a GDS that does not implement its own source netlist.
MIM_MODEL = "cap_mim_2f0_m4m5_noshield"


class GenError(RuntimeError):
    """A layout-generation step could not be completed."""


# --------------------------------------------------------------------------- #
# SPICE netlist parsing
# --------------------------------------------------------------------------- #


def _logical_lines(text: str) -> list[str]:
    """Join SPICE ``+`` continuations and drop comment lines.

    ``*.ipin``/``**.subckt`` style comments are kept as raw text so the caller
    can read the commented-out top-cell header xschem emits for a netlist
    *fragment* (design/README.md): the top cell's ``.subckt``/``.ends`` pair is
    commented out on purpose, but its ``x`` instance lines are live.
    """
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("+"):
            if not lines:
                raise GenError("netlist starts with a '+' continuation line")
            lines[-1] = lines[-1] + " " + stripped[1:].strip()
            continue
        lines.append(stripped)
    return lines


_PARAM_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*('[^']*'|\"[^\"]*\"|\S+)")
_SI_SUFFIX = {
    "t": 1e12,
    "g": 1e9,
    "meg": 1e6,
    "k": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
}


def _spice_number(value: str) -> float:
    """Parse a SPICE scalar such as ``0.28u`` / ``4.4U`` / ``500`` into a float."""
    text = value.strip().strip("'\"").lower()
    match = re.fullmatch(r"([+-]?[0-9.]+(?:e[+-]?[0-9]+)?)\s*([a-z]*)", text)
    if not match:
        raise GenError(f"cannot parse SPICE number {value!r}")
    mantissa = float(match.group(1))
    suffix = match.group(2)
    if not suffix:
        return mantissa
    for name in ("meg", "t", "g", "k", "m", "u", "n", "p", "f"):
        if suffix.startswith(name):
            return mantissa * _SI_SUFFIX[name]
    raise GenError(f"unknown SPICE unit suffix in {value!r}")


class Device:
    """One flattened MOS device, with top-level net names.

    ``w_um`` is the **per-finger** drawn width (the netlist's ``W`` divided by
    its ``nf``), and ``fingers`` is ``nf * m`` -- i.e. exactly the pair
    ``klt gen mos_array`` wants, where a ``finger_topology: "parallel"`` unit
    device is one folded transistor of total width ``fingers * w_um``.  For
    ``nf=1`` (every device in the committed netlist) ``w_um`` is just ``W``.
    See :func:`_device_from_tokens` for why the split is the right reading.
    """

    def __init__(
        self,
        name: str,
        model: str,
        w_um: float,
        l_um: float,
        fingers: int,
        d: str,
        g: str,
        s: str,
        b: str,
    ) -> None:
        self.name = name
        self.model = model
        self.w_um = w_um
        self.l_um = l_um
        self.fingers = fingers
        self.d = d
        self.g = g
        self.s = s
        self.b = b

    @property
    def flavor(self) -> str:
        return "pfet" if self.model.startswith("pfet") else "nfet"

    @property
    def is_mv(self) -> bool:
        return self.model in MV_MODELS

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "model": self.model,
            "w_um": self.w_um,
            "l_um": self.l_um,
            "fingers": self.fingers,
            "nets": {"d": self.d, "g": self.g, "s": self.s, "b": self.b},
        }


class Passive:
    """One flattened two-terminal passive device, with top-level net names.

    Today these are only the four series MIM capacitors ``XCCOMP1``..
    ``XCCOMP4`` (``cap_mim_2f0_m4m5_noshield`` at 5.0 um x 5.0 um, issue #155 /
    decision record 0007, re-modeled by issue #192 / decision record 0014),
    whose geometry is ``c_width``/``c_length`` rather than a MOSFET's
    ``W``/``L``.

    A ``Passive`` is deliberately **not** a :class:`Device`: it is drawn by
    :meth:`Interconnect.mim_caps` (plate geometry through ``klt draw``), never
    by ``klt gen mos_array``, so keeping the two types distinct is what stops a
    capacitor from being fed to the MOS generator as if it were a transistor --
    or, worse, silently dropped, leaving a GDS that claims to implement a
    netlist it does not.
    """

    def __init__(
        self,
        name: str,
        model: str,
        w_um: float,
        l_um: float,
        multiplicity: int,
        plus: str,
        minus: str,
    ) -> None:
        self.name = name
        self.model = model
        self.w_um = w_um
        self.l_um = l_um
        self.multiplicity = multiplicity
        self.plus = plus
        self.minus = minus

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "model": self.model,
            "c_width_um": self.w_um,
            "c_length_um": self.l_um,
            "m": self.multiplicity,
            "nets": {"plus": self.plus, "minus": self.minus},
        }


class Resistor:
    """One flattened two-terminal bare-SPICE ``R`` element, top-level nets.

    Today these are ``uvlo``'s ``Rref``/``R1``/``R2``/``Rfb`` (issue #221),
    each a bare ``R<name> <n1> <n2> <value>`` line -- an ideal ohms value, no
    drawn geometry in the schematic (design/uvlo-comparator-sizing.md: "not a
    layout deliverable ... layout is #221"). Kept distinct from
    :class:`Device`/:class:`Passive` for the same reason those are distinct
    from each other: a resistor is drawn by neither ``klt gen mos_array`` nor
    the hand-drawn MiM plates, but by ``klt gen res_array``
    (:meth:`Interconnect.resistors`).
    """

    def __init__(self, name: str, value_ohm: float, plus: str, minus: str) -> None:
        self.name = name
        self.value_ohm = value_ohm
        self.plus = plus
        self.minus = minus

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "value_ohm": self.value_ohm,
            "nets": {"plus": self.plus, "minus": self.minus},
        }


def parse_netlist(path: str) -> tuple[list[str], list[Device]]:
    """Flatten ``gate_driver_core.spice`` into (top port list, MOS device list).

    Thin wrapper over :func:`parse_netlist_full` that drops the passive and
    resistor lists, kept because every downstream consumer of this parser
    (``check_gate_driver_core.py``, ``lvs/make_reference.py``) is MOS-only by
    construction: both audit the drawn transistors of the committed GDS.
    Anything that *generates* layout should call :func:`parse_netlist_full`
    instead, so an undrawn passive/resistor is visible rather than silently
    absent.
    """
    top_ports, devices, _passives, _resistors = parse_netlist_full(path)
    return top_ports, devices


def parse_netlist_full(
    path: str,
) -> tuple[list[str], list[Device], list[Passive], list[Resistor]]:
    """Flatten ``gate_driver_core.spice`` into (ports, MOS devices, passives, resistors).

    Returns the top cell's port names in ``.subckt`` order, every MOS device in
    the design, every non-MOS ``X`` passive device, and every bare-SPICE ``R``
    resistor element (issue #221 -- ``uvlo``'s ``Rref``/``R1``/``R2``/``Rfb``),
    with each terminal renamed to the *top-level* net it resolves to through
    the ``x1``/``x2``/``x3`` instance lines.
    """
    with open(path, encoding="utf-8") as handle:
        lines = _logical_lines(handle.read())

    top_ports: list[str] = []
    top_instances: list[tuple[str, list[str], str]] = []
    subckts: dict[str, tuple[list[str], list[list[str]]]] = {}

    current: str | None = None
    for line in lines:
        low = line.lower()
        if low.startswith("**.subckt "):
            # '**.subckt <cell> <port> ...' -- drop the directive and cell name
            top_ports = line.split()[2:]
            continue
        if low.startswith(".subckt "):
            tokens = line.split()
            current = tokens[1]
            subckts[current] = (tokens[2:], [])
            continue
        if low.startswith(".ends") or low.startswith("**.ends"):
            current = None
            continue
        if line.startswith("*"):
            continue
        if not (low.startswith("x") or low.startswith("r")):
            continue
        tokens = line.split()
        if current is None:
            # Top-level subcircuit instance: X<name> <nets...> <subckt>. This
            # netlist never instantiates a bare resistor at the top level
            # (every 'R' line lives inside a sub-cell body, e.g. uvlo's own
            # Rref/R1/R2/Rfb) -- refuse loudly rather than mis-parse one as an
            # instance if that ever changes.
            if not low.startswith("x"):
                raise GenError(
                    f"{path}: top-level resistor line {line!r} is not "
                    "supported -- every resistor must live inside a sub-cell"
                )
            top_instances.append((tokens[0], tokens[1:-1], tokens[-1]))
        else:
            subckts[current][1].append(tokens)

    if not top_ports:
        raise GenError(f"{path}: no top-level '**.subckt' header found")
    if not top_instances:
        raise GenError(f"{path}: no top-level subcircuit instances found")

    devices: list[Device] = []
    passives: list[Passive] = []
    resistors: list[Resistor] = []
    for inst_name, inst_nets, subckt_name in top_instances:
        if subckt_name not in subckts:
            raise GenError(f"{path}: instance {inst_name} names unknown cell {subckt_name}")
        formal, body = subckts[subckt_name]
        if len(formal) != len(inst_nets):
            raise GenError(
                f"{path}: instance {inst_name} has {len(inst_nets)} nets but "
                f"{subckt_name} declares {len(formal)} ports"
            )
        mapping = {f: a for f, a in zip(formal, inst_nets)}
        for tokens in body:
            if tokens[0].lower().startswith("r"):
                resistors.append(_resistor_from_tokens(tokens, mapping, prefix=f"{inst_name}_"))
                continue
            parsed = _device_from_tokens(tokens, mapping, prefix=f"{inst_name}_")
            if isinstance(parsed, Passive):
                passives.append(parsed)
            else:
                devices.append(parsed)
    return top_ports, devices, passives, resistors


def _resistor_from_tokens(tokens: list[str], mapping: dict[str, str], prefix: str) -> Resistor:
    """Build a :class:`Resistor` from a bare ``R<name> <n1> <n2> <value> ...`` line.

    Unlike a MOS/passive ``X`` line, a bare SPICE ``R`` element names no model
    -- ``value`` is the resistance directly (issue #221: ``uvlo.spice``'s
    ``Rref``/``R1``/``R2``/``Rfb``, e.g. ``Rref VDD_DRV nref 800k m=1``).
    """
    if len(tokens) < 4:
        raise GenError(f"{tokens[0]}: resistor line has too few fields: {' '.join(tokens)!r}")
    name, n1, n2, value_tok = tokens[0], tokens[1], tokens[2], tokens[3]
    params = dict(_PARAM_RE.findall(" ".join(tokens[4:])))
    m = int(round(_spice_number(params.get("m", "1"))))
    if m != 1:
        raise GenError(f"{name}: m={m} is not drawn -- this generator draws one physical resistor per netlist R element")
    return Resistor(
        name=f"{prefix}{name}",
        value_ohm=_spice_number(value_tok),
        plus=mapping.get(n1, f"{prefix}{n1}"),
        minus=mapping.get(n2, f"{prefix}{n2}"),
    )


def _split_instance(tokens: list[str]) -> tuple[str, list[str], str, dict[str, str]]:
    """Split ``X<name> <net>... <model> [param=value ...]`` into its four parts.

    The terminal count is *not* fixed at four: a MOSFET line has four (d g s b)
    and a two-terminal passive has two, so the model is located as "the last
    token before the first ``param=value``" rather than at a fixed index.  The
    old fixed-index reading is what produced ``KeyError: 'W'`` on the MIM cap
    line: it took the cap's first parameter (``c_width=3.0u``) for the model
    name and then looked up a width that was never there (issue #155 / #166).
    """
    param_start = next((i for i, tok in enumerate(tokens) if "=" in tok), len(tokens))
    if param_start < 3:
        raise GenError(
            f"{tokens[0]}: cannot read a device line with fewer than one "
            f"terminal and a model name: {' '.join(tokens)!r}"
        )
    return (
        tokens[0],
        tokens[1 : param_start - 1],
        tokens[param_start - 1],
        dict(_PARAM_RE.findall(" ".join(tokens[param_start:]))),
    )


def _device_from_tokens(
    tokens: list[str], mapping: dict[str, str], prefix: str
) -> Device | Passive:
    """Build one device from a ``X<name> <nets...> model params...`` line.

    Returns a :class:`Device` for a MOSFET and a :class:`Passive` for a
    recognized non-MOS model (:data:`PASSIVE_MODEL_PREFIXES`).  Any other line
    shape is a :class:`GenError`, never a bare ``KeyError``: a netlist device
    this generator cannot classify must fail loudly, since silently dropping it
    would produce a GDS that does not implement the schematic.
    """
    name, terminals, model, params = _split_instance(tokens)

    def resolve(net: str) -> str:
        return mapping.get(net, f"{prefix}{net}")

    if model.startswith(PASSIVE_MODEL_PREFIXES):
        return _passive_from_params(name, terminals, model, params, prefix, resolve)

    if len(terminals) != 4:
        raise GenError(
            f"{name}: MOS device {model} has {len(terminals)} terminals "
            f"(expected 4: d g s b)"
        )
    missing = [key for key in ("W", "L") if key not in params]
    if missing:
        raise GenError(
            f"{name}: model {model} has no {'/'.join(missing)} parameter -- it "
            f"is neither a MOSFET nor a model family this generator knows how "
            f"to draw (recognized passives: {', '.join(PASSIVE_MODEL_PREFIXES)}*)"
        )
    total_w_um = _spice_number(params["W"]) * 1e6
    l_um = _spice_number(params["L"]) * 1e6
    nf = int(round(_spice_number(params.get("nf", "1"))))
    m = int(round(_spice_number(params.get("m", "1"))))
    if nf < 1 or m < 1:
        raise GenError(f"{name}: nf/m must be >= 1 (got nf={nf}, m={m})")
    # `W` is the device's *total* width, split across its `nf` fingers, and `m`
    # replicates the whole device -- gf180mcu's model cards hand `w=w nf=nf`
    # straight to the BSIM core and size their drift resistors on `w/nf`, and
    # this netlist's own geometry parameters use `W/nf` as the per-finger width
    # (`ad='int((nf+1)/2) * W/nf * 0.18u'`).  `klt gen mos_array`'s `w_um` is
    # the *per-finger* width on the other side of the handoff: with
    # `finger_topology: "parallel"` the unit device is "one folded transistor of
    # width `fingers * w_um`" (klayout-tools docs/cli/gen.md; same sentence in
    # its `_mos_unit_strapped_layout` docstring), which klt 0.2.0 confirms by
    # extracting `{"w_um": 1.0, "fingers": 2}` back as two parallel transistors
    # of `w_um: 1.0`.  So `nf*m` fingers of `W/nf` -- total drawn width `W*m`,
    # whatever `nf` is.  Every device in the committed netlist has `nf=1`, where
    # this is `m` fingers of `W` exactly as before (issue #129).
    return Device(
        name=f"{prefix}{name}",
        model=model,
        w_um=total_w_um / nf,
        l_um=l_um,
        fingers=nf * m,
        d=resolve(terminals[0]),
        g=resolve(terminals[1]),
        s=resolve(terminals[2]),
        b=resolve(terminals[3]),
    )


def _passive_from_params(
    name: str,
    terminals: list[str],
    model: str,
    params: dict[str, str],
    prefix: str,
    resolve,
) -> Passive:
    """Build a :class:`Passive` from a recognized non-MOS device line."""
    if len(terminals) != 2:
        raise GenError(
            f"{name}: passive {model} has {len(terminals)} terminals "
            f"(expected 2)"
        )
    missing = [key for key in ("c_width", "c_length") if key not in params]
    if missing:
        raise GenError(
            f"{name}: passive {model} has no {'/'.join(missing)} parameter"
        )
    m = int(round(_spice_number(params.get("m", "1"))))
    if m < 1:
        raise GenError(f"{name}: m must be >= 1 (got m={m})")
    return Passive(
        name=f"{prefix}{name}",
        model=model,
        w_um=_spice_number(params["c_width"]) * 1e6,
        l_um=_spice_number(params["c_length"]) * 1e6,
        multiplicity=m,
        plus=resolve(terminals[0]),
        minus=resolve(terminals[1]),
    )


# --------------------------------------------------------------------------- #
# klt drivers
# --------------------------------------------------------------------------- #


def _klt(*args: str) -> dict:
    """Run one ``klt`` subcommand with ``--format json`` and return its response."""
    exe = shutil.which("klt")
    if exe is None:
        raise GenError(
            "klayout-tools ('klt') is not on PATH -- this repo's layout flow "
            "requires it (see CLAUDE.md)"
        )
    proc = subprocess.run(
        [exe, *args, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GenError(
            f"klt {' '.join(args[:2])} failed (exit {proc.returncode}):\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise GenError(f"klt {' '.join(args[:2])} produced non-JSON output: {exc}") from exc


def generate_device_cells(
    devices: list[Device], out_dir: str, pdk: str
) -> dict[str, dict]:
    """Run ``klt gen mos_array`` once per device; return name -> generator report."""
    reports: dict[str, dict] = {}
    for device in devices:
        params = {
            "w_um": round(device.w_um, 4),
            "l_um": round(device.l_um, 4),
            "fingers": device.fingers,
            "finger_topology": "parallel",
            "rows": 1,
            "cols": 1,
            "dummy": 0,
            "topology": "array",
            "flavor": device.flavor,
            "gate_contact": True,
        }
        gds_path = os.path.join(out_dir, f"{device.name}.gds")
        report = _klt(
            "gen",
            "mos_array",
            "--pdk",
            pdk,
            "--params",
            json.dumps(params),
            "--cell-name",
            device.name,
            "-o",
            gds_path,
        )
        reports[device.name] = report
    return reports


def generate_resistor_cells(
    resistors: list[Resistor], out_dir: str, pdk: str
) -> dict[str, dict]:
    """Run ``klt gen res_array`` once per resistor; return name -> generator report.

    Sizing comes from :func:`resistor_array_params` (issue #221) -- one
    ``res_array`` block per netlist ``R`` element, folded into ``num`` series
    unit resistors across ``rows``.
    """
    reports: dict[str, dict] = {}
    for resistor in resistors:
        num, rows, length_um = resistor_array_params(resistor.value_ohm)
        params = {
            "length_um": round(length_um, 6),
            "width_um": RES_WIDTH_UM,
            "spacing_um": RES_SPACING_UM,
            "num": num,
            "rows": rows,
            "dummy": 0,
            "flavor": "generic",
        }
        gds_path = os.path.join(out_dir, f"{resistor.name}.gds")
        report = _klt(
            "gen",
            "res_array",
            "--pdk",
            pdk,
            "--params",
            json.dumps(params),
            "--cell-name",
            resistor.name,
            "-o",
            gds_path,
        )
        reports[resistor.name] = report
    return reports


# --------------------------------------------------------------------------- #
# Floorplan
# --------------------------------------------------------------------------- #


def _ports_by_role(report: dict) -> dict[str, dict]:
    """Map a ``mos_array`` report's ``U0_S``/``U0_D``/``U0_G`` ports to s/d/g."""
    roles = {}
    for port in report.get("ports", []):
        suffix = port["name"].rsplit("_", 1)[-1].lower()
        if suffix in ("s", "d", "g"):
            roles[suffix] = port
    missing = {"s", "d", "g"} - set(roles)
    if missing:
        raise GenError(
            f"generator report for {report.get('cell_name')} is missing "
            f"port(s) {sorted(missing)}"
        )
    return roles


class Placement:
    """Absolute placement of one device strip."""

    def __init__(self, device: Device, report: dict, origin_x: float, origin_y: float):
        self.device = device
        self.report = report
        self.x = origin_x
        self.y = origin_y
        bbox = report["bbox_um"]
        self.x0 = bbox["x0"] + origin_x
        self.y0 = bbox["y0"] + origin_y
        self.x1 = bbox["x1"] + origin_x
        self.y1 = bbox["y1"] + origin_y
        roles = _ports_by_role(report)
        self.pad = {
            role: (port["x_um"] + origin_x, port["y_um"] + origin_y)
            for role, port in roles.items()
        }


def place_devices(devices: list[Device], reports: dict[str, dict]) -> list[Placement]:
    """Stack every device strip vertically: 3.3V group, domain gap, 5V/6V group."""
    ordered = [d for d in devices if not d.is_mv] + [d for d in devices if d.is_mv]
    placements: list[Placement] = []
    cursor = 0.0
    previous_mv: bool | None = None
    for device in ordered:
        report = reports[device.name]
        bbox = report["bbox_um"]
        if previous_mv is not None:
            cursor += DOMAIN_GAP_UM if device.is_mv != previous_mv else CHANNEL_UM
        origin_y = cursor - bbox["y0"]
        placements.append(Placement(device, report, 0.0, origin_y))
        cursor = origin_y + bbox["y1"]
        previous_mv = device.is_mv
    return placements


_RES_PORT_RE = re.compile(r"^R(\d+)_(A|B)$")


class ResistorPlacement:
    """Absolute placement of one ``res_array`` block (issue #221).

    ``units`` is ``[(A_um, B_um), ...]`` in unit-index order -- the two
    terminal coordinates of each series unit resistor, in this block's
    absolute (post-origin) frame.  :meth:`Interconnect.resistors` chains
    ``units[i][1]`` (B) to ``units[i+1][0]`` (A) with a short jumper, and
    wires ``units[0][0]``/``units[-1][1]`` out to the resistor's own two nets.
    """

    def __init__(self, resistor: Resistor, report: dict, origin_x: float, origin_y: float):
        self.resistor = resistor
        self.report = report
        self.x = origin_x
        self.y = origin_y
        bbox = report["bbox_um"]
        self.x0 = bbox["x0"] + origin_x
        self.y0 = bbox["y0"] + origin_y
        self.x1 = bbox["x1"] + origin_x
        self.y1 = bbox["y1"] + origin_y
        by_index: dict[int, dict[str, tuple[float, float]]] = {}
        for port in report.get("ports", []):
            match = _RES_PORT_RE.match(port["name"])
            if not match:
                raise GenError(
                    f"res_array report for {report.get('cell_name')} has an "
                    f"unrecognized port name {port['name']!r} (expected R<i>_A/_B)"
                )
            index, terminal = int(match.group(1)), match.group(2)
            by_index.setdefault(index, {})[terminal] = (
                port["x_um"] + origin_x,
                port["y_um"] + origin_y,
            )
        expected_num, _rows, _length_um = resistor_array_params(resistor.value_ohm)
        missing = [i for i in range(len(by_index)) if by_index.get(i, {}).keys() != {"A", "B"}]
        if missing or len(by_index) != expected_num:
            raise GenError(
                f"res_array report for {report.get('cell_name')} does not "
                f"carry exactly A/B ports for units 0..{expected_num - 1}"
            )
        self.units = [(by_index[i]["A"], by_index[i]["B"]) for i in range(len(by_index))]


def place_resistors(
    resistors: list[Resistor],
    reports: dict[str, dict],
    start_x: float,
    start_y: float,
) -> list[ResistorPlacement]:
    """Stack every resistor's ``res_array`` block vertically at ``start_x``.

    Placed as its own column, entirely north of nothing in particular but
    always east of every device rail (``start_x`` is the caller's
    already-computed clear-of-everything x) -- so it never overlaps
    ``DNWELL_DRV`` regardless of the marker's own x-extent, the same
    "outside every device's bbox" property :meth:`Interconnect.guard_ring`
    relies on, just along the other axis.
    """
    placements: list[ResistorPlacement] = []
    cursor = start_y
    for resistor in resistors:
        report = reports[resistor.name]
        bbox = report["bbox_um"]
        origin_y = cursor - bbox["y0"]
        placements.append(ResistorPlacement(resistor, report, start_x, origin_y))
        cursor = origin_y + bbox["y1"] + RES_ROW_GAP_UM
    return placements


# --------------------------------------------------------------------------- #
# Interconnect / marker cell
# --------------------------------------------------------------------------- #


def _rect(layer: tuple[int, int], x0: float, y0: float, x1: float, y1: float, name=None):
    shape = {
        "layer": list(layer),
        "rect_um": [round(v, 4) for v in (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))],
    }
    if name:
        shape["name"] = name
    return shape


def _hbar(layer, x0: float, x1: float, y: float, width: float, name=None):
    return _rect(layer, x0, y - width / 2.0, x1, y + width / 2.0, name)


def _vbar(layer, y0: float, y1: float, x: float, width: float, name=None):
    return _rect(layer, x - width / 2.0, y0, x + width / 2.0, y1, name)


class Interconnect:
    """Builds the ``klt draw`` request for the wiring + marker cell."""

    def __init__(
        self,
        placements: list[Placement],
        nets: list[str],
        passives: list["Passive"] | None = None,
    ):
        self.placements = placements
        self.nets = nets
        self.passives = list(passives or [])
        #: Resistor blocks (issue #221), attached after construction via
        #: :meth:`set_resistors` once their own ``res_array`` origins are
        #: known -- see module-level ``build()``.
        self.resistor_placements: list["ResistorPlacement"] = []
        self.shapes: list[dict] = []
        self.labels: list[dict] = []
        #: Provenance for the drawn MiM stack, filled in by :meth:`mim_caps`
        #: and echoed into ``gate_driver_core.provenance.json`` -- one entry
        #: per drawn capacitor, naming the plate rectangles it was drawn as.
        self.mim_records: list[dict] = []
        #: Provenance for the drawn resistor network (issue #221), filled in
        #: by :meth:`resistors`.
        self.resistor_records: list[dict] = []
        # guard_ring()'s ring is strapped to the 3.3V group's own ground
        # rail -- this block's substrate reference, since the 3.3V devices
        # sit directly on native substrate outside every DNWELL (see that
        # method's docstring).
        self.substrate_net = "GND_LOGIC"

        column_x1 = max(p.x1 for p in placements)
        self.left_rail_x = {
            net: -RAIL_MARGIN_UM - index * RAIL_PITCH_UM
            for index, net in enumerate(nets)
        }
        self.right_rail_x = {
            net: column_x1 + RAIL_MARGIN_UM + index * RAIL_PITCH_UM
            for index, net in enumerate(nets)
        }
        self.stack_bottom = min(p.y0 for p in placements)
        self.stack_top = max(p.y1 for p in placements)
        self.jumper_y = {
            net: self.stack_top + JUMPER_BAND_GAP_UM + index * JUMPER_PITCH_UM
            for index, net in enumerate(nets)
        }
        self.rail_y0 = self.stack_bottom - 2.0
        self.rail_y1 = max(self.jumper_y.values()) + 2.0
        #: Northmost drawn edge so far.  :meth:`guard_ring` raises it to its
        #: own north stroke; :meth:`mim_caps` stacks the MiM row above
        #: whatever it ends up being, so the row never lands on top of drawn
        #: circuitry regardless of how the floorplan below it grows.
        self.north_edge_y = self.rail_y1

    def set_resistors(self, placements: list["ResistorPlacement"]) -> None:
        """Attach already-placed resistor blocks (issue #221) for :meth:`resistors`."""
        self.resistor_placements = placements

    # -- primitives -------------------------------------------------------- #

    def _via_stack(self, x: float, y: float) -> None:
        """Via1 plus its Metal1 landing pad (the Metal2 rail is the top plate)."""
        self.shapes.append(
            _rect(
                L_METAL1,
                x - LANDING_UM / 2,
                y - LANDING_UM / 2,
                x + LANDING_UM / 2,
                y + LANDING_UM / 2,
            )
        )
        self.shapes.append(
            _rect(
                L_VIA1,
                x - VIA_SIZE_UM / 2,
                y - VIA_SIZE_UM / 2,
                x + VIA_SIZE_UM / 2,
                y + VIA_SIZE_UM / 2,
            )
        )

    # -- build steps ------------------------------------------------------- #

    def rails(self) -> None:
        for net in self.nets:
            for x in (self.left_rail_x[net], self.right_rail_x[net]):
                self.shapes.append(
                    _vbar(L_METAL2, self.rail_y0, self.rail_y1, x, RAIL_WIDTH_UM, name=net)
                )
            self.labels.append(
                {
                    "layer": list(L_METAL2_LABEL),
                    "text": net,
                    "at_um": [round(self.left_rail_x[net], 4), round(self.rail_y0 + 1.0, 4)],
                }
            )
            self.labels.append(
                {
                    "layer": list(L_METAL2_LABEL),
                    "text": net,
                    "at_um": [round(self.right_rail_x[net], 4), round(self.rail_y0 + 1.0, 4)],
                }
            )

    def jumpers(self) -> None:
        """Tie each net's left rail to its right rail on Metal1, above the stack."""
        for net in self.nets:
            y = self.jumper_y[net]
            left = self.left_rail_x[net]
            right = self.right_rail_x[net]
            self.shapes.append(_hbar(L_METAL1, left, right, y, JUMPER_WIDTH_UM, name=net))
            self._via_stack(left, y)
            self._via_stack(right, y)

    def device_wiring(self) -> None:
        for index, placement in enumerate(self.placements):
            device = placement.device
            # Source -> left rail.
            sx, sy = placement.pad["s"]
            rail = self.left_rail_x[device.s]
            self.shapes.append(
                _hbar(L_METAL1, rail, sx + STUB_WIDTH_UM / 2, sy, STUB_WIDTH_UM, name=device.s)
            )
            self._via_stack(rail, sy)

            # Drain -> right rail.
            dx, dy = placement.pad["d"]
            rail = self.right_rail_x[device.d]
            self.shapes.append(
                _hbar(L_METAL1, dx - STUB_WIDTH_UM / 2, rail, dy, STUB_WIDTH_UM, name=device.d)
            )
            self._via_stack(rail, dy)

            # Gate -> up out of the strip, left through the channel above it.
            gx, gy = placement.pad["g"]
            channel_y = self._gate_channel_y(index)
            rail = self.left_rail_x[device.g]
            self.shapes.append(
                _vbar(
                    L_METAL1,
                    gy - STUB_WIDTH_UM / 2,
                    channel_y + STUB_WIDTH_UM / 2,
                    gx,
                    STUB_WIDTH_UM,
                    name=device.g,
                )
            )
            self.shapes.append(
                _hbar(
                    L_METAL1,
                    rail,
                    gx + STUB_WIDTH_UM / 2,
                    channel_y,
                    STUB_WIDTH_UM,
                    name=device.g,
                )
            )
            self._via_stack(rail, channel_y)

    def _gate_channel_y(self, index: int) -> float:
        """Centre of the empty horizontal channel above device strip ``index``."""
        this_top = self.placements[index].y1
        if index + 1 < len(self.placements):
            next_bottom = self.placements[index + 1].y0
        else:
            next_bottom = self.stack_top + JUMPER_BAND_GAP_UM
        return this_top + min(CHANNEL_UM / 2.0, (next_bottom - this_top) / 2.0)

    def voltage_domain_markers(self) -> None:
        """DNWELL_DRV + LVPWELL + Dualgate over the 5V/6V group only.

        The 3.3V group is left entirely outside every DNWELL, which is
        spec/gate-driver.md 2.4's second allowed option and the one
        design/level-shifter-partition.md's device table already commits to.
        """
        mv = [p for p in self.placements if p.device.is_mv]
        if not mv:
            return
        x0 = min(p.x0 for p in mv)
        x1 = max(p.x1 for p in mv)
        y0 = min(p.y0 for p in mv)
        y1 = max(p.y1 for p in mv)
        self.shapes.append(
            _rect(
                L_DNWELL,
                x0 - DNWELL_MARGIN_UM,
                y0 - DNWELL_MARGIN_UM,
                x1 + DNWELL_MARGIN_UM,
                y1 + DNWELL_MARGIN_UM,
                name="DNWELL_DRV",
            )
        )
        self.shapes.append(
            _rect(
                L_DUALGATE,
                x0 - DUALGATE_MARGIN_UM,
                y0 - DUALGATE_MARGIN_UM,
                x1 + DUALGATE_MARGIN_UM,
                y1 + DUALGATE_MARGIN_UM,
                name="DUALGATE_DRV",
            )
        )
        # Isolated p-well under each thick-oxide nfet inside DNWELL_DRV. The
        # pfets sit in their own Nwell (drawn by `klt gen mos_array`), so the
        # two never overlap: strips are stacked with a CHANNEL_UM gap and
        # LVPWELL_MARGIN_UM is well inside half of it.
        for placement in mv:
            if placement.device.flavor != "nfet":
                continue
            self.shapes.append(
                _rect(
                    L_LVPWELL,
                    placement.x0 - LVPWELL_MARGIN_UM,
                    placement.y0 - LVPWELL_MARGIN_UM,
                    placement.x1 + LVPWELL_MARGIN_UM,
                    placement.y1 + LVPWELL_MARGIN_UM,
                    name=f"LVPWELL_{placement.device.name}",
                )
            )

    def _tap(self, x: float, y: float, implant: tuple[int, int], net: str) -> None:
        """One body-tie tap at ``(x, y)``: Comp + implant + Contact + Metal1 pad,
        strapped west on Metal1 to ``net``'s own left rail and via'd up to it.

        ``implant`` selects which body the tap ties: ``L_NPLUS`` (n+ diffusion
        inside an Nwell -> a *well* tie) or ``L_PPLUS`` (p+ diffusion outside
        every Nwell -> a *substrate/p-well* tie).  gf180mcu draws no dedicated
        tap mask, so that implant choice is the only thing that distinguishes a
        tie from ordinary source/drain diffusion -- both for the foundry and
        for `klt extract`, whose gf180mcu deck derives its tap region as
        ``(tap_nplus & active & nwell) | (tap_pplus & (active - nwell))``
        (klayout-tools #1084).  Drawing the implant *only* over the tap
        footprint (never as a blanket rectangle over a device) is therefore
        load-bearing: a Pplus rectangle covering an nfet's own diffusion would
        turn its source and drain into substrate ties and short the block.

        The Metal1 strap crosses *under* whichever unrelated Metal2 rails sit
        between the tap and ``net``'s rail with no via, the same crossing
        scheme :meth:`device_wiring` uses for every source/gate stub.
        """
        half_comp = TAP_COMP_UM / 2.0
        half_contact = CONTACT_SIZE_UM / 2.0
        self.shapes.append(_rect(L_COMP, x - half_comp, y - half_comp, x + half_comp, y + half_comp))
        self.shapes.append(_rect(implant, x - half_comp, y - half_comp, x + half_comp, y + half_comp))
        self.shapes.append(
            _rect(L_CONTACT, x - half_contact, y - half_contact, x + half_contact, y + half_contact)
        )
        self.shapes.append(
            _rect(L_METAL1, x - LANDING_UM / 2, y - LANDING_UM / 2, x + LANDING_UM / 2, y + LANDING_UM / 2)
        )
        rail = self.left_rail_x[net]
        self.shapes.append(_hbar(L_METAL1, rail, x + STUB_WIDTH_UM / 2, y, STUB_WIDTH_UM, name=net))
        self._via_stack(rail, y)

    def body_ties(self) -> None:
        """Per-device body tap for every drawn transistor (issue #132).

        Each device gets its own tap just outside its own bbox
        (``TAP_LEFT_OFFSET_UM`` left of ``x0``, ``TAP_TOP_OFFSET_UM`` above
        ``y1``), wired to the net the netlist itself names as that device's
        body (``device.b``) -- so every one of the 959 drawn transistors has a
        real, drawn, contacted body tie rather than a floating well or an
        extractor-synthesized placeholder.  Which implant a tap carries, and
        which body region it therefore ties, follows the device's own flavor
        and voltage domain:

        =============================  ===========  =====================================
        device                         implant      ties
        =============================  ===========  =====================================
        pfet (either domain)           ``Nplus``    its own Nwell -> ``VDD_LOGIC``/``VDD_DRV``
        nfet, 3.3 V group              ``Pplus``    the native p-substrate -> ``GND_LOGIC``
        nfet, 5 V/6 V group            ``Pplus``    the ``LVPWELL`` patch inside
                                                    ``DNWELL_DRV`` -> ``GND_DRV``
        =============================  ===========  =====================================

        **pfet taps** additionally draw a fresh Nwell rectangle that is a
        strict *superset* of the device's own reported ``bbox_um`` (with
        ``WELL_TIE_MARGIN_UM`` margin on every side): `klt gen mos_array`'s own
        internal Nwell for a ``flavor: "pfet"`` device cannot extend past its
        own reported bbox by definition, so a redundant rectangle containing
        the whole bbox is guaranteed to overlap (merge with) it once flattened
        -- the same "redundant enclosing rectangle" technique
        :meth:`voltage_domain_markers` already uses for LVPWELL/DNWELL, per
        device instead of per group.  `klt extract`'s pfet body terminal *is*
        the Nwell region a device's active sits in, so tying that per-device
        Nwell island to a real net through an n+ tap resolves that device's own
        body to ``VDD_LOGIC``/``VDD_DRV`` independently of every other device's
        island.

        **nfet taps** are drawn the same way but land on a body region
        gf180mcu's `klt` extraction deck does not model as a region at all: it
        declares one deck-wide ``substrate_net`` global and ties *every* nfet
        body terminal to it with KLayout's ``connect_global``, with no
        ``DNWELL``/``LVPWELL`` in its connectivity graph (``204/0`` is reported
        in `klt extract`'s own ``ignored_layers``).  Every drawn p+ tie in the
        design -- the 3.3 V group's substrate taps, the isolated ``LVPWELL``
        taps inside ``DNWELL_DRV``, and :meth:`guard_ring`'s ring -- therefore
        lands on that single global identity, so the extractor reports
        ``GND_LOGIC`` and ``GND_DRV`` as one merged net.  That merge is the
        *extractor's* model, not this layout's routing: the two ground rails
        are drawn as separate Metal2 nets and stay separate in the drawn
        interconnect, which ``check_gate_driver_core.py``'s
        ``ground_rail_isolation`` check asserts independently -- `klt
        components` over Metal1/Via1/Metal2 only, net names from the Metal2
        text layer, no deck globals and no device recognition, so it rules on
        the drawn interconnect rather than on the extractor's substrate model.
        That check is what covers this gap now that neither `klt lvs` nor
        ``check_gate_driver_core.py``'s own ``devices`` check can still tell
        the two rails apart, and DRC cannot either (two overlapping same-layer
        shapes on different nets merge into one polygon and raise no spacing
        violation).  It is also electrically
        the node the block already declares: ``spec/decision-records/0001``
        Decision 1 ratifies ``GND_LOGIC``/``GND_DRV`` as **one** electrical
        reference node, split into two pins only at the pad ring (option (c),
        genuinely isolated grounds, was considered and rejected).  See
        ``layout/lvs/make_reference.py``'s transform 3 and ``layout/README.md``
        for how the LVS reference models it and what that costs.
        """
        for placement in self.placements:
            device = placement.device
            tap_x = placement.x0 - TAP_LEFT_OFFSET_UM
            tap_y = placement.y1 + TAP_TOP_OFFSET_UM
            if device.flavor == "pfet":
                self._tap(tap_x, tap_y, L_NPLUS, device.b)
                self.shapes.append(
                    _rect(
                        L_NWELL,
                        placement.x0 - WELL_TIE_MARGIN_UM,
                        placement.y0 - WELL_TIE_MARGIN_UM,
                        placement.x1 + WELL_TIE_MARGIN_UM,
                        placement.y1 + WELL_TIE_MARGIN_UM,
                        name=f"NWELL_TIE_{device.name}",
                    )
                )
            else:
                self._tap(tap_x, tap_y, L_PPLUS, device.b)

    def guard_ring(self) -> None:
        """Closed, contacted PCOMP guard ring around ``DNWELL_DRV`` (DN.3).

        gf180mcu's own DRC deck states the rule this draws, and states it as a
        connectivity requirement rather than a geometry one -- ``DN.3``: *"Each
        DNWELL shall be directly surrounded by PCOMP guard ring tied to the
        P-substrate potential"* (the PDK's ``dnwell.rb`` implements it as
        ``dnwell.not_inside(pcomp.holes.not(pcomp).interacting(dnwell, 1..1)``
        ``.extents)``, i.e. the DNWELL must sit inside the *hole* of a closed
        PCOMP annulus).  So the ring is:

        * **closed** -- four overlapping Comp+Pplus strokes merge into one
          annulus whose hole contains all of ``DNWELL_DRV``;
        * **PCOMP**, not bare Comp -- ``pcomp = comp AND pplus`` in the PDK's
          own derivation, so the Pplus stroke is what makes this a guard ring
          rather than a rectangle of undoped diffusion;
        * **tied to the P-substrate potential** -- contacted on a
          ``GUARD_RING_CONTACT_PITCH_UM`` pitch along its north and south
          strokes and strapped on Metal1 to the 3.3 V group's own ground rail,
          which is this block's substrate reference (the 3.3 V devices sit
          directly on native substrate, outside every DNWELL);
        * placed ``GUARD_RING_MARGIN_UM`` outside the 5 V/6 V group's bbox,
          which clears ``DF.18`` (min. DNWELL space to PCOMP outside Nwell and
          DNWELL, 2.5 um) against the ``DNWELL_MARGIN_UM``-sized DNWELL_DRV
          marker with margin to spare.

        The **east and west strokes carry no contacts**, and that is the
        "closed ring has to be cut for every signal crossing the domain
        boundary" problem ``layout/README.md`` predicted, landing exactly where
        it was predicted to: every 5 V/6 V device's source, gate and drain stub
        leaves the domain horizontally on Metal1 and crosses those two strokes,
        so a Metal1 strap along them would short all of them together.  Comp
        and Metal1 do not interact without a Contact bridging them, so the
        crossings themselves are harmless -- the strokes are tied through the
        ring's own continuous p+ diffusion instead of through metal, which
        keeps the ring closed (DN.3) and grounded, at a higher tie resistance
        on the two vertical strokes than a fully-strapped ring would have.
        Distributing contacts along them needs a Metal2 crossover per stub,
        i.e. a routing-channel redesign; it is recorded in ``layout/README.md``
        rather than bolted on here.
        """
        mv = [p for p in self.placements if p.device.is_mv]
        if not mv:
            return
        x0 = min(p.x0 for p in mv) - GUARD_RING_MARGIN_UM - GUARD_RING_WIDTH_UM
        x1 = max(p.x1 for p in mv) + GUARD_RING_MARGIN_UM + GUARD_RING_WIDTH_UM
        y0 = min(p.y0 for p in mv) - GUARD_RING_MARGIN_UM - GUARD_RING_WIDTH_UM
        y1 = max(p.y1 for p in mv) + GUARD_RING_MARGIN_UM + GUARD_RING_WIDTH_UM
        w = GUARD_RING_WIDTH_UM
        # When the 5V/6V group's own y1 sits at (or near) the whole device
        # stack's own top -- true for this netlist's placement order -- the
        # margin-derived north stroke lands inside jumpers()'s own band
        # (every net's Metal1 jumper bar, drawn above `stack_top`): the
        # narrow gaps *between* individual jumper bars are too tight for this
        # stroke's own contact/strap Metal1 to clear metal1.space.1 from its
        # neighbours on both sides at once (confirmed empirically -- a naive
        # margin-only y1 landed two `metal1.space.1` violations against the
        # nearest jumpers' own via-landing pads). DN.3 sets no *maximum*
        # ring-to-DNWELL distance, so it is always safe to push the north
        # stroke up past the jumper band entirely instead of threading it
        # through -- the strap then never shares a y-band with any jumper.
        if self.jumper_y:
            jumper_top = max(self.jumper_y.values()) + JUMPER_WIDTH_UM / 2.0
            y1 = max(y1, jumper_top + GUARD_RING_JUMPER_CLEARANCE_UM + w)
        self.north_edge_y = max(self.north_edge_y, y1)
        strokes = [
            (x0, y0, x1, y0 + w),  # S
            (x0, y1 - w, x1, y1),  # N
            (x0, y0, x0 + w, y1),  # W
            (x1 - w, y0, x1, y1),  # E
        ]
        for rect in strokes:
            self.shapes.append(_rect(L_COMP, *rect, name="GUARD_RING_DRV"))
            self.shapes.append(_rect(L_PPLUS, *rect, name="GUARD_RING_DRV"))

        # Contact row + Metal1 strap on the north and south strokes only (see
        # the docstring for why not east/west), tied to the substrate net.
        net = self.substrate_net
        rail = self.left_rail_x[net]
        half_contact = CONTACT_SIZE_UM / 2.0
        for y in (y0 + w / 2.0, y1 - w / 2.0):
            self.shapes.append(
                _hbar(L_METAL1, min(rail, x0), x1, y, GUARD_RING_STRAP_WIDTH_UM, name=net)
            )
            self._via_stack(rail, y)
            x = x0 + GUARD_RING_CONTACT_PITCH_UM / 2.0
            while x <= x1 - GUARD_RING_CONTACT_PITCH_UM / 2.0:
                self.shapes.append(
                    _rect(L_CONTACT, x - half_contact, y - half_contact, x + half_contact, y + half_contact)
                )
                x += GUARD_RING_CONTACT_PITCH_UM

    # -- MiM capacitor stack (issue #166) ---------------------------------- #

    def _mim_series_chain(self) -> list[str]:
        """Validate the netlist passives as one series chain; return its nodes.

        Returns ``[n0, n1, ... nN]`` for ``N`` capacitors, where capacitor
        ``i`` spans ``n[i]``..``n[i+1]``.  Everything this method rejects is a
        :class:`GenError` rather than a best-effort draw: a stack drawn from a
        misread chain would still be four legal-looking capacitors, would still
        pass DRC, and would silently implement a different effective
        capacitance than ``spec/decision-records/0014`` ratified.
        """
        passives = self.passives
        for passive in passives:
            if passive.model != MIM_MODEL:
                raise GenError(
                    f"{passive.name}: this generator can only draw "
                    f"{MIM_MODEL} (got {passive.model}) -- gf180mcuD is a "
                    "5-metal DRM Option-B build whose only MiM device is the "
                    "2.0 fF/um^2 flavour on Metal4-FuseTop-Metal5"
                )
            if passive.multiplicity != 1:
                raise GenError(
                    f"{passive.name}: m={passive.multiplicity} is not drawn -- "
                    "this generator draws one plate pair per netlist device"
                )
        if len(passives) % 2 != 0:
            # An even count is what makes every interior series node land on
            # a *shared plate* (see mim_caps()'s docstring): caps 2k/2k+1
            # share a Metal5 strap, caps 2k+1/2k+2 share a Metal4 bottom
            # plate, and both chain ends come out on Metal4.  An odd count
            # would leave one end on Metal5, needing a Metal5->Metal4->Metal3
            # escape whose Via4 would have to be kept clear of every virtual
            # bottom plate (MIMTM.2).  That is drawable, but it is not drawn
            # here, and guessing would be worse than refusing.
            raise GenError(
                f"{len(passives)} series MiM capacitor(s): this generator "
                "draws an even-length chain only (each interior node is a "
                "shared plate), see Interconnect.mim_caps()"
            )
        nodes = [passives[0].plus]
        for passive in passives:
            if passive.plus != nodes[-1]:
                raise GenError(
                    f"{passive.name}: expected its first terminal to be "
                    f"{nodes[-1]!r} (the previous capacitor's second "
                    f"terminal), got {passive.plus!r} -- the netlist's "
                    f"{MIM_MODEL} devices are not one series chain"
                )
            nodes.append(passive.minus)
        if len(set(nodes)) != len(nodes):
            # A repeated node is a loop, not a series chain: shorting one
            # capacitor out changes the effective capacitance without changing
            # the device count, so it must never be drawn as if it were a
            # chain.
            raise GenError(f"series MiM chain revisits a node: {nodes}")
        for endpoint in (nodes[0], nodes[-1]):
            if endpoint not in self.left_rail_x:
                raise GenError(
                    f"series MiM chain terminates on {endpoint!r}, which has "
                    "no drawn Metal2 rail (it is on no MOS terminal) -- there "
                    "is nothing to escape to"
                )
        return nodes

    def mim_caps(self) -> None:
        """Draw the ``XCCOMP*`` MiM series stack (issue #166, decision record 0014).

        ``klt gen`` ships no capacitor generator, so the plates are drawn
        directly as ``klt draw`` rectangles -- on exactly the layers `klt`'s
        own gf180mcu **extraction** deck recognises this device on
        (``decks/gf180mcu.py``'s ``EXTRACTION_DECK.capacitors``, itself
        transcribed from the PDK's ``mimcap_extraction.lvs``), so the result is
        a real, extractable, LVS-comparable device rather than decorative
        geometry:

        ==================  =========  =====================================
        role                layer      why
        ==================  =========  =====================================
        top plate           FuseTop    ``capacitors[].top_plate`` (75/0)
        recognition marker  CAP_MK     ``top_plate_requires`` (117/5)
        recognition marker  MIM_L_MK   ``top_plate_requires`` (117/10)
        bottom plate        Metal4     ``bottom_plate`` (46/0) -- gf180mcuD is
                                       a 5-metal DRM Option-B build, so
                                       ``topmin1_metal`` *is* Metal4 and the
                                       metal pair is fixed by the process, not
                                       chosen here
        top-plate contact   Via4       ``top_plate_via`` (41/0)
        top-plate metal     Metal5     ``top_plate_via_metal`` (81/0)
        ==================  =========  =====================================

        **Series topology: every interior node is a shared plate.**  With an
        even-length chain the capacitors alternate orientation, so no interior
        node needs a via at all:

        * capacitors ``2k`` and ``2k+1`` share one **Metal5 strap** laid over
          both their Via4s -- that is the odd-numbered node;
        * capacitors ``2k+1`` and ``2k+2`` share one **Metal4 polygon**, their
          two bottom plates joined by a bridge -- that is the even-numbered
          interior node;
        * both chain ends therefore come out on Metal4, and escape through
          Via3 -> Metal3 -> Via2 down to the Metal2 rail each end net already
          has.

        That is what keeps ``nccomp1``/``nccomp2``/``nccomp3`` **floating by
        construction** rather than by inspection (the correctness risk issue
        #166 calls out): an interior node is one metal polygon with two plate
        terminals on it and nothing else -- no via, no strap, no tie, no
        shield.  There is no geometry that *could* connect them to anything
        else, so the "did we accidentally strap a floating node" question has
        a structural answer here, not just a visual one.  The Via4s under a
        Metal5 strap do not short it to the bottom plate either, and that is
        the extractor's own model rather than an assumption: ``klt extract``
        cuts each top-plate Via4's overlap with the recognised bottom plate
        out of the generic Via4 connectivity precisely so a DRM-legal MiM
        stack does not read as a plate-to-plate short.

        **DRM 10.4.2 "MIM Option B" rules honoured** (the three `klt`'s
        curated DRC deck transcribes are re-checked by ``layout/drc``; the
        rest are honoured here because the DRM states them, and are recorded
        so a future deck update finds them already satisfied):

        * **MIMTM.1** (1.2 um bottom-plate spacing to adjacent bottom-plate or
          routing Metal4) -- the row pitch is ``6.2 + 1.2``, and the only other
          Metal4 in the design is each end plate's own escape stub, which is
          part of that plate's own polygon.
        * **MIMTM.2** (0.4 um virtual-bottom-plate overlap of Via4) and
          **MIMTM.5** (0.4 um top-plate overlap of Via4) -- the Via4 sits at
          the plate centre, ~2.4 um and ~2.9 um inside respectively.
        * **MIMTM.3** (0.6 um bottom-plate overlap of the top plate) -- the
          Metal4 plate is the FuseTop plate grown by exactly that on all four
          sides.
        * **MIMTM.8a** (25 um^2 minimum MiM area) -- comes from the netlist's
          own ``c_width``/``c_length`` (5.0 x 5.0), asserted here rather than
          assumed.
        * **MIMTM.10** ("Via(n-2)", i.e. Via3 on this 5LM stack, may not touch
          the bottom plate) -- an end plate's Via3 sits on a stub that runs
          well clear of the *virtual* bottom plate (the DRM's own
          ``FuseTop`` sized by 1.06 um, intersected with Metal4), not on the
          plate itself.
        * **10.4.2's "no matching-sensitive analog circuitry underneath"** --
          the row is north of every other drawn shape in the block, over bare
          substrate.
        """
        passives = self.passives
        if not passives:
            return
        nodes = self._mim_series_chain()

        top_w = passives[0].w_um
        top_l = passives[0].l_um
        for passive in passives:
            if (passive.w_um, passive.l_um) != (top_w, top_l):
                raise GenError(
                    "series MiM capacitors must all be the same size (this "
                    f"row is drawn on one pitch): {passive.name} is "
                    f"{passive.w_um}x{passive.l_um}um, expected {top_w}x{top_l}um"
                )
            if passive.w_um * passive.l_um < 25.0:
                raise GenError(
                    f"{passive.name}: {passive.w_um}x{passive.l_um}um is "
                    f"{passive.w_um * passive.l_um:g}um^2, below DRM MIMTM.8a's "
                    "25um^2 minimum MiM area -- not a drawable device"
                )

        # MIMTM.5 / MIMTM.2: the Via4 lands at the plate centre, so both
        # enclosures are half the smaller plate dimension minus half the via.
        # Checked rather than laid out to -- a plate this generator could not
        # legally contact must fail here, not at DRC time.
        via_enclosure = (min(top_w, top_l) - VIA_SIZE_UM) / 2.0
        if via_enclosure < MIM_TOP_VIA_ENCLOSURE_UM:
            raise GenError(
                f"a {top_w}x{top_l}um MiM top plate encloses its centred "
                f"{VIA_SIZE_UM}um Via4 by only {via_enclosure:g}um, under DRM "
                f"MIMTM.5/MIMTM.2's {MIM_TOP_VIA_ENCLOSURE_UM}um"
            )

        bottom_w = top_w + 2 * MIM_BOTTOM_OVERLAP_UM
        bottom_l = top_l + 2 * MIM_BOTTOM_OVERLAP_UM
        pitch = bottom_w + MIM_PLATE_SPACE_UM
        row_x0 = 0.0  # left-aligned with the device column, like every strip
        row_y0 = self.north_edge_y + MIM_ROW_MARGIN_UM
        cy = row_y0 + bottom_l / 2.0
        centre_x = [row_x0 + bottom_w / 2.0 + index * pitch for index in range(len(passives))]

        half_via = VIA_SIZE_UM / 2.0
        for index, passive in enumerate(passives):
            cx = centre_x[index]
            # Bottom plate (Metal4), top plate (FuseTop) and the two
            # recognition markers the extraction deck requires the top plate
            # to interact with.
            self.shapes.append(
                _rect(
                    L_METAL4,
                    cx - bottom_w / 2.0,
                    cy - bottom_l / 2.0,
                    cx + bottom_w / 2.0,
                    cy + bottom_l / 2.0,
                    name=f"MIM_BOTTOM_{passive.name}",
                )
            )
            for layer in (L_FUSETOP, L_CAP_MK, L_MIM_L_MK):
                self.shapes.append(
                    _rect(
                        layer,
                        cx - top_w / 2.0,
                        cy - top_l / 2.0,
                        cx + top_w / 2.0,
                        cy + top_l / 2.0,
                        name=f"MIM_TOP_{passive.name}",
                    )
                )
            # Top-plate contact: Via4 straight up off the FuseTop plate.
            self.shapes.append(
                _rect(L_VIA4, cx - half_via, cy - half_via, cx + half_via, cy + half_via)
            )
            # Orientation, per the shared-plate scheme in the docstring: an
            # even-indexed capacitor takes its first terminal on the bottom
            # plate, an odd-indexed one takes it on the top plate.
            bottom_net, top_net = (
                (nodes[index], nodes[index + 1])
                if index % 2 == 0
                else (nodes[index + 1], nodes[index])
            )
            self.mim_records.append(
                {
                    "name": passive.name,
                    "model": passive.model,
                    "c_width_um": passive.w_um,
                    "c_length_um": passive.l_um,
                    "m": passive.multiplicity,
                    "nets": {"plus": passive.plus, "minus": passive.minus},
                    "plates": {
                        "bottom": {
                            "layer": list(L_METAL4),
                            "net": bottom_net,
                            "rect_um": [
                                round(cx - bottom_w / 2.0, 4),
                                round(cy - bottom_l / 2.0, 4),
                                round(cx + bottom_w / 2.0, 4),
                                round(cy + bottom_l / 2.0, 4),
                            ],
                        },
                        "top": {
                            "layer": list(L_FUSETOP),
                            "net": top_net,
                            "rect_um": [
                                round(cx - top_w / 2.0, 4),
                                round(cy - top_l / 2.0, 4),
                                round(cx + top_w / 2.0, 4),
                                round(cy + top_l / 2.0, 4),
                            ],
                        },
                    },
                }
            )

        # Interior odd nodes: one Metal5 strap over capacitors 2k and 2k+1's
        # Via4s.  Interior even nodes: one Metal4 bridge merging capacitors
        # 2k+1 and 2k+2's bottom plates into a single polygon.
        for index in range(0, len(passives) - 1, 2):
            self.shapes.append(
                _hbar(
                    L_METAL5,
                    centre_x[index] - MIM_STRAP_EXTEND_UM,
                    centre_x[index + 1] + MIM_STRAP_EXTEND_UM,
                    cy,
                    MIM_STRAP_WIDTH_UM,
                    name=nodes[index + 1],
                )
            )
        for index in range(1, len(passives) - 1, 2):
            self.shapes.append(
                _hbar(
                    L_METAL4,
                    centre_x[index] + bottom_w / 2.0 - MIM_BRIDGE_OVERLAP_UM,
                    centre_x[index + 1] - bottom_w / 2.0 + MIM_BRIDGE_OVERLAP_UM,
                    cy,
                    MIM_BRIDGE_HEIGHT_UM,
                    name=nodes[index + 1],
                )
            )

        # Chain ends: Metal4 stub -> Via3 -> Metal3 lane -> Via2 -> the rail
        # each end net already has.  The end whose rail sits furthest left
        # takes the *upper* lane, so its horizontal run passes above -- never
        # through -- the other end's vertical drop.
        ends = [(0, nodes[0]), (len(passives) - 1, nodes[-1])]
        ends.sort(key=lambda entry: self.left_rail_x[entry[1]])
        tap_y = self.rail_y1 - MIM_RAIL_TAP_DROP_UM
        for lane, (index, net) in enumerate(ends):
            lane_y = row_y0 - MIM_LANE_GAP_UM - lane * MIM_LANE_PITCH_UM
            cx = centre_x[index]
            rail_x = self.left_rail_x[net]
            # Metal4 stub out of the plate's south edge, down past the Via3.
            self.shapes.append(
                _vbar(
                    L_METAL4,
                    lane_y - MIM_TAIL_DROP_UM,
                    cy - bottom_l / 2.0 + MIM_BRIDGE_OVERLAP_UM,
                    cx,
                    MIM_TAIL_WIDTH_UM,
                    name=net,
                )
            )
            # Metal3 lane: across to the rail, then down the rail to the tap.
            self.shapes.append(
                _hbar(L_METAL3, rail_x, cx, lane_y, MIM_LANE_WIDTH_UM, name=net)
            )
            self.shapes.append(
                _vbar(L_METAL3, tap_y, lane_y, rail_x, MIM_LANE_WIDTH_UM, name=net)
            )
            for x, y, via_layer in ((cx, lane_y, L_VIA3), (rail_x, tap_y, L_VIA2)):
                self.shapes.append(
                    _rect(
                        L_METAL3,
                        x - LANDING_UM / 2,
                        y - LANDING_UM / 2,
                        x + LANDING_UM / 2,
                        y + LANDING_UM / 2,
                    )
                )
                self.shapes.append(
                    _rect(via_layer, x - half_via, y - half_via, x + half_via, y + half_via)
                )

    # -- resistor network (issue #221) -------------------------------------- #

    def resistors(self) -> None:
        """Wire every placed ``res_array`` block into its netlist net (issue #221).

        Each block is ``num`` series unit resistors (:func:`resistor_array_params`);
        this method chains unit ``i``'s ``B`` port to unit ``i+1``'s ``A`` port
        with a short Metal1 jumper (using the *exact* coordinates
        ``klt gen res_array`` reported -- same-row units land at the same y,
        a row transition at the same x, per its own boustrophedon fold, so a
        plain ``_hbar``/``_vbar`` always suffices; anything else means the
        fold changed shape and this refuses rather than drawing a bad short).

        The chain's two open ends -- unit 0's ``A``, the last unit's ``B`` --
        then stub out to the resistor's own ``plus``/``minus`` net rail. By
        the fold's own numbering, unit 0 is always in the *bottom* row and
        the last unit always in the *top* row (``res_array`` fills row 0
        first, then row 1, ...), so each end's stub first drops (unit 0) or
        rises (the last unit) clear of the block's own bbox -- past every
        other row's Metal1 pads, which occupy only their own row's narrow
        y-band -- before turning to run west to the rail. A flat stub run
        straight from a multi-unit row's *far* end to the rail, at the row's
        own y, would instead cross directly over every unit in between (all
        on the same Metal1 y-band) and short the whole chain together --
        confirmed the hard way: a first pass of this method did exactly that
        and a real `klt lvs` run reported R1/R2's entire interior chain
        merged into one net.

        **The long-distance run back to the rail is drawn on Metal3, not
        Metal1 (issue #221 fix).** A first pass ran that whole leg on Metal1,
        reasoning that "Metal1 does not connect to Metal2 without a Via1, the
        same 'stubs cross under unrelated rails' property every other stub in
        this class relies on" -- true for *rails* (Metal2), but the resistor
        column sits well east of `column_x1` (the widest drawn device --
        uvlo's own `MPD`, m=800, spans nearly 900um), so *every* device's own
        drain stub (:meth:`device_wiring`) now also runs on Metal1 nearly the
        full width of the block, at that device's own pad y. A same-layer
        Metal1 escape run from the resistor column back to a device-side
        rail is therefore no longer confined to "empty" territory the way it
        was when the drawn block was narrow: confirmed the hard way a second
        time, a real `klt lvs` run reported `uvlo`'s own `GND_DRV` net
        electrically merged with the unrelated level-shifter net `x1_inb`,
        because `R2`'s Metal1 escape lane (y from its own block position)
        happened to cross `XMPINV`'s Metal1 drain stub (y from *its* pad,
        clear across the block) at the same y band. Landing the long leg on
        Metal3 instead -- the same "crosses the whole interconnect without a
        single via into it" technique :meth:`mim_caps` already uses for its
        own chain-end escape -- makes that crossing layer-safe unconditionally:
        Metal3 never interacts with a device's Metal1 stub, or with a Metal2
        rail, without an explicit Via2 this method places only at its own two
        endpoints.

        **The Via2-to-rail landing sits at the escape's own `lane_y`, not up
        near the top of the rail.** A first pass of this Metal3 rework
        landed every end's Via2 near `self.rail_y1` (mirroring
        :meth:`mim_caps`'s own `tap_y`), reasoning that any point along a
        rail's full-height span is an equally valid connection -- true in
        isolation, but it meant every end's Metal3 lane grew a second,
        *vertical* leg spanning nearly the whole design height at that net's
        own rail x. With eight ends (four resistors x two terminals) each
        contributing one such near-full-height strip, several pairs of
        those verticals crossed a *third* net's own horizontal lane whose x
        happened to reach that far (`R2`'s minus lane alone reaches from
        `GND_DRV`'s rail all the way to its own last unit, deep inside the
        resistor column) -- confirmed the hard way a third time, a real `klt
        lvs` run reported `GND_DRV`/`VDD_DRV`/`x3_ndiv`/`x3_nref`/
        `x3_uvlo_ok` all merged into one net. Every end's own `lane_y` is
        already distinct from every other end's (:func:`place_resistors`'s
        `RES_ROW_GAP_UM` spacing, more than twice `RES_ENDPOINT_CLEARANCE_UM`
        apart, keeps every resistor's own below/above escape y clear of
        every other resistor's), so landing directly at `(rail, lane_y)`
        needs no vertical Metal3 leg at all -- each end's entire Metal3
        footprint is then confined to its own narrow y-band, and two ends
        can only ever collide if their y-bands do, which they structurally
        cannot.
        """
        half_via = VIA_SIZE_UM / 2.0
        for placement in self.resistor_placements:
            resistor = placement.resistor
            units = placement.units
            for (_a, prev_b), (next_a, _b) in zip(units, units[1:]):
                if prev_b[1] == next_a[1]:
                    self.shapes.append(_hbar(L_METAL1, prev_b[0], next_a[0], prev_b[1], STUB_WIDTH_UM))
                elif prev_b[0] == next_a[0]:
                    self.shapes.append(_vbar(L_METAL1, prev_b[1], next_a[1], prev_b[0], STUB_WIDTH_UM))
                else:
                    raise GenError(
                        f"{resistor.name}: res_array's unit ports are not "
                        "row/column-aligned between consecutive units -- "
                        "cannot draw a straight series jumper"
                    )

            # The resistor column sits east of every device (place_resistors()
            # -- module-level build()'s resistor_start_x is derived from
            # right_rail_x), so each escape lane reaches back toward the
            # *right* rail, not the left one -- using left_rail_x here would
            # draw a lane spanning the entire block westward, merging every
            # net whose own rail it happened to land on along the way.
            below_y = placement.y0 - RES_ENDPOINT_CLEARANCE_UM
            above_y = placement.y1 + RES_ENDPOINT_CLEARANCE_UM
            ends = (
                (resistor.plus, units[0][0], below_y),
                (resistor.minus, units[-1][1], above_y),
            )
            for net, (px, py), lane_y in ends:
                rail = self.right_rail_x[net]
                # Short Metal1 run from the unit's own pin down/up to the
                # lane y, then Via1+Via2 up onto a local Metal2 landing --
                # entirely within the resistor's own column (x >= every
                # device's own bbox), clear of every device's own Metal1
                # wiring by construction (see :func:`place_resistors`).
                self.shapes.append(_vbar(L_METAL1, min(py, lane_y), max(py, lane_y), px, STUB_WIDTH_UM, name=net))
                self.shapes.append(
                    _rect(L_METAL1, px - LANDING_UM / 2, lane_y - LANDING_UM / 2, px + LANDING_UM / 2, lane_y + LANDING_UM / 2)
                )
                self.shapes.append(
                    _rect(L_VIA1, px - half_via, lane_y - half_via, px + half_via, lane_y + half_via)
                )
                self.shapes.append(
                    _rect(L_METAL2, px - LANDING_UM / 2, lane_y - LANDING_UM / 2, px + LANDING_UM / 2, lane_y + LANDING_UM / 2)
                )
                self.shapes.append(
                    _rect(L_VIA2, px - half_via, lane_y - half_via, px + half_via, lane_y + half_via)
                )
                # The long leg itself: Metal3, from the local landing back to
                # the target rail's own x, entirely at this end's own
                # `lane_y` -- no separate vertical leg, so this end's whole
                # Metal3 footprint stays inside its own narrow y-band (see
                # the docstring above for why that is load-bearing). The
                # Via2 at the rail end lands directly on the rail polygon
                # (which spans the full design height, so any y along it is
                # a valid tie-in).
                self.shapes.append(_hbar(L_METAL3, rail, px, lane_y, MIM_LANE_WIDTH_UM, name=net))
                for x in (px, rail):
                    self.shapes.append(
                        _rect(L_METAL3, x - LANDING_UM / 2, lane_y - LANDING_UM / 2, x + LANDING_UM / 2, lane_y + LANDING_UM / 2)
                    )
                self.shapes.append(
                    _rect(L_VIA2, rail - half_via, lane_y - half_via, rail + half_via, lane_y + half_via)
                )

            _num, _rows, length_um = resistor_array_params(resistor.value_ohm)
            self.resistor_records.append(
                {
                    "name": resistor.name,
                    "value_ohm": resistor.value_ohm,
                    "nets": {"plus": resistor.plus, "minus": resistor.minus},
                    "num": len(units),
                    "drawn_ohm": resistor_ohms(len(units), length_um),
                    "origin_um": {"x": round(placement.x, 4), "y": round(placement.y, 4)},
                    "bbox_um": {
                        "x0": round(placement.x0, 4),
                        "y0": round(placement.y0, 4),
                        "x1": round(placement.x1, 4),
                        "y1": round(placement.y1, 4),
                    },
                }
            )

    def build(self) -> dict:
        self.rails()
        self.jumpers()
        self.device_wiring()
        self.resistors()
        self.voltage_domain_markers()
        self.body_ties()
        self.guard_ring()
        self.mim_caps()
        # `klt draw --params` takes the *params* object itself (dbu_um /
        # shapes / labels); the CLI wraps it in the request envelope.
        return {"dbu_um": 0.001, "shapes": self.shapes, "labels": self.labels}


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #


def compose(
    placements: list[Placement],
    interconnect_report: dict,
    out_gds: str,
    out_dir: str,
    pdk: str,
    resistor_placements: list["ResistorPlacement"] | None = None,
) -> dict:
    blocks = [
        {"id": p.device.name, "generator_report": p.report} for p in placements
    ]
    origins = {p.device.name: {"x": p.x, "y": p.y} for p in placements}
    for rp in resistor_placements or []:
        blocks.append({"id": rp.resistor.name, "generator_report": rp.report})
        origins[rp.resistor.name] = {"x": rp.x, "y": rp.y}
    blocks.append({"id": "interconnect", "generator_report": interconnect_report})
    origins["interconnect"] = {"x": 0.0, "y": 0.0}
    order = [b["id"] for b in blocks]

    request = {
        "schema": "klt.gen_compose.request/1",
        "pdk": {"variant": pdk},
        "blocks": blocks,
        "placement": {"strategy": "explicit", "order": order, "origins_um": origins},
        "options": {"cell_name": TOP_CELL, "output": out_gds},
    }
    request_path = os.path.join(out_dir, "gen-compose-request.json")
    with open(request_path, "w", encoding="utf-8") as handle:
        json.dump(request, handle, indent=1)
    return _klt("gen-compose", request_path)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", REPO_ROOT, *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:  # pragma: no cover - git absent
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def build(out_dir: str, pdk: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    work_dir = os.path.join(out_dir, "build")
    os.makedirs(work_dir, exist_ok=True)

    top_ports, devices, passives, resistors = parse_netlist_full(NETLIST_PATH)
    undrawable = [p for p in passives if p.model != MIM_MODEL]
    if undrawable:
        # Loud on purpose: a passive this generator cannot draw means the GDS
        # it is about to write would NOT implement the whole schematic.  It
        # refuses to write one rather than shipping a layout whose own
        # provenance has to disclaim it (which is what the pre-#166
        # `passives_not_drawn` block did).
        raise GenError(
            f"{len(undrawable)} passive device(s) in "
            + os.path.relpath(NETLIST_PATH, REPO_ROOT)
            + " cannot be drawn by this generator: "
            + ", ".join(f"{p.name} ({p.model})" for p in undrawable)
            + f" -- only {MIM_MODEL} is drawable (Interconnect.mim_caps)"
        )
    reports = generate_device_cells(devices, work_dir, pdk)
    placements = place_devices(devices, reports)

    nets = sorted({n for d in devices for n in (d.d, d.g, d.s)})
    interconnect = Interconnect(placements, nets, passives)

    # Resistor network (issue #221): every net a netlist R element names is
    # already a MOS d/g/s net (confirmed for uvlo's Rref/R1/R2/Rfb), so it
    # already has a Metal2 rail from `Interconnect.__init__` above -- sizing
    # and placement need no further coupling to the interconnect beyond the
    # rail x-extent it already computed, which is why this can happen before
    # `interconnect.build()` runs.
    resistor_reports = generate_resistor_cells(resistors, work_dir, pdk)
    resistor_start_x = (
        max(interconnect.right_rail_x.values()) + RES_COLUMN_MARGIN_UM
        if interconnect.right_rail_x
        else 0.0
    )
    # Start the resistor column far enough above `rail_y0` that even the
    # *lowest* resistor's own "below" escape lane (`RES_ENDPOINT_CLEARANCE_UM`
    # below its own block bbox.y0) still lands inside the rails' own drawn
    # y0..y1 span, not below it. A first pass started the column exactly at
    # `rail_y0` (matching the rails' own bottom edge), which put that lowest
    # lane a further `RES_ENDPOINT_CLEARANCE_UM` *below* rail_y0 -- outside
    # every rail's own drawn extent, so the Via2 landing meant to merge onto
    # a rail there touched nothing: confirmed the hard way, a real `klt lvs`
    # run reported that resistor's own "plus" pin as a dangling, one-terminal
    # anonymous net rather than the schematic net it was meant to reach.
    # `LANDING_UM` of headroom on top of the clearance keeps the landing
    # pad's own footprint (not just its center point) inside the rail.
    resistor_start_y = interconnect.rail_y0 + RES_ENDPOINT_CLEARANCE_UM + LANDING_UM
    resistor_placements = place_resistors(
        resistors, resistor_reports, resistor_start_x, resistor_start_y
    )
    interconnect.set_resistors(resistor_placements)

    interconnect_request = interconnect.build()
    request_path = os.path.join(work_dir, "draw-request.json")
    with open(request_path, "w", encoding="utf-8") as handle:
        json.dump(interconnect_request, handle, indent=1)
    interconnect_gds = os.path.join(work_dir, "interconnect.gds")
    draw_report = _klt(
        "draw",
        "--params",
        request_path,
        "--cell-name",
        "gate_driver_core_interconnect",
        "-o",
        interconnect_gds,
    )
    # `klt draw` is not a `klt gen` generator, so it does not emit a
    # generator_report. `gen-compose` only needs generator/cell_name/gds_path/
    # bbox_um/ports (see docs/cli/gen-compose.md) -- synthesise exactly those
    # for the interconnect cell, which carries no routable ports of its own.
    interconnect_report = {
        "generator": "klt-draw:interconnect",
        "cell_name": draw_report["cell_name"],
        "gds_path": draw_report["gds_path"],
        "bbox_um": draw_report["bbox_um"],
        "ports": [],
    }

    out_gds = os.path.join(out_dir, f"{TOP_CELL}.gds")
    compose_report = compose(
        placements, interconnect_report, out_gds, work_dir, pdk, resistor_placements
    )

    provenance = {
        "top_cell": TOP_CELL,
        "layout": {
            "path": os.path.relpath(out_gds, REPO_ROOT),
            "sha256": _sha256(out_gds),
            "bbox_um": compose_report.get("bbox_um"),
        },
        "source_netlist": {
            "path": os.path.relpath(NETLIST_PATH, REPO_ROOT),
            "sha256": _sha256(NETLIST_PATH),
            "top_ports": top_ports,
            "device_count": len(devices),
            "transistor_count": sum(d.fingers for d in devices),
            "passive_count": len(passives),
            "resistor_count": len(resistors),
            # Netlist devices this generator does not draw. An empty list is
            # the "layout covers the whole netlist" statement; it has been
            # empty since issue #166 drew the `XCCOMP*` MiM stack, and
            # `build()` now refuses to write a GDS that would make it
            # non-empty rather than shipping a disclaimed layout.
            "passives_not_drawn": [],
            # The drawn MiM stack, one entry per netlist capacitor, naming the
            # plate rectangle and the series node each terminal landed on
            # (issue #166 / spec/decision-records/0014).
            "passives_drawn": interconnect.mim_records,
            # The drawn resistor network, one entry per netlist R element
            # (issue #221) -- num series units, its computed drawn ohms
            # (matches value_ohm by construction, see resistor_ohms()), and
            # its own block placement.
            "resistors_drawn": interconnect.resistor_records,
        },
        "generator": {
            "path": os.path.relpath(os.path.abspath(__file__), REPO_ROOT),
            "sha256": _sha256(os.path.abspath(__file__)),
        },
        "tools": {
            "klt_version": _klt_version(),
            "pdk": compose_report.get("pdk"),
            "note": (
                "the klayout build and the extraction deck's content hash are "
                "recorded in gate_driver_core.checks.json (klt extract's own "
                "provenance block)"
            ),
        },
        "git": {
            "commit": _git("rev-parse", "HEAD"),
            "describe": _git("describe", "--always", "--dirty"),
        },
        "placement": [
            {
                "id": p.device.name,
                "origin_um": {"x": round(p.x, 4), "y": round(p.y, 4)},
                "bbox_um": {
                    "x0": round(p.x0, 4),
                    "y0": round(p.y0, 4),
                    "x1": round(p.x1, 4),
                    "y1": round(p.y1, 4),
                },
                "domain": "5V/6V" if p.device.is_mv else "3.3V",
            }
            for p in placements
        ],
        "compose_warnings": compose_report.get("warnings", []),
        "devices": [d.as_dict() for d in devices],
        "resistors": [r.as_dict() for r in resistors],
    }
    provenance_path = os.path.join(out_dir, f"{TOP_CELL}.provenance.json")
    with open(provenance_path, "w", encoding="utf-8") as handle:
        json.dump(provenance, handle, indent=2, sort_keys=False)
        handle.write("\n")
    return {
        "gds": out_gds,
        "provenance": provenance_path,
        "compose": compose_report,
        "devices": devices,
        "passives": passives,
        "resistors": resistors,
    }


def _klt_version() -> str:
    exe = shutil.which("klt")
    if exe is None:
        return "unknown"
    proc = subprocess.run([exe, "--version"], capture_output=True, text=True, check=False)
    return proc.stdout.strip() or proc.stderr.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out-dir",
        default=HERE,
        help="directory to write the layout + provenance into (default: layout/)",
    )
    parser.add_argument("--pdk", default=DEFAULT_PDK, help="PDK variant (default: %(default)s)")
    args = parser.parse_args(argv)

    try:
        result = build(os.path.abspath(args.out_dir), args.pdk)
    except GenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    compose_report = result["compose"]
    print(f"top cell     : {TOP_CELL}")
    print(f"layout       : {result['gds']}")
    print(f"provenance   : {result['provenance']}")
    print(f"blocks placed: {len(compose_report.get('blocks', []))}")
    bbox = compose_report.get("bbox_um") or {}
    if bbox:
        print(
            "bbox (um)    : "
            f"{bbox['x1'] - bbox['x0']:.2f} x {bbox['y1'] - bbox['y0']:.2f}"
        )
    print(f"netlist devs : {len(result['devices'])}")
    print(f"transistors  : {sum(d.fingers for d in result['devices'])}")
    print(
        f"passives     : {len(result['passives'])} MiM cap(s) drawn "
        f"({', '.join(p.name for p in result['passives']) or 'none'})"
    )
    print(
        f"resistors    : {len(result['resistors'])} drawn "
        f"({', '.join(r.name for r in result['resistors']) or 'none'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
