"""Process / voltage / temperature corner definitions for gf180mcu.

Ported from `2AMLogic/gf180-bandgap` (sim/harness/corners.py) and adapted for
this repo's **two-rail** design: a 3.3 V logic rail and a 5 V/6 V drive rail
(spec/gate-driver.md §3), swept together rather than the single ``vdd`` rail
the source harness assumes.

## Process corners (unchanged from gf180-bandgap)

The gf180mcu ngspice model library (``sm141064.ngspice``) does not ship a
single "ss" switch that skews every device. Each device family carries its
own ``.lib`` section:

    MOS      typical | ff | ss | fs | sf
    BJT      bjt_typical | bjt_ff | bjt_ss
    diode    diode_typical | diode_ff | diode_ss
    resistor res_typical | res_ff | res_ss
    MOS cap  moscap_typical | moscap_ff | moscap_ss
    MIM cap  mimcap_typical | mimcap_ff | mimcap_ss

A *named corner* here is therefore a bundle of sections. Section ordering
follows the PDK's own xschem testbenches (MOS first, then passives), and
``design.ngspice`` is always included ahead of them because it defines the
global switch params (``sw_stat_global``, ``mc_skew``, ...) the sections
reference.

Confirmed directly against the installed gf180mcuD `sm141064.ngspice`
(open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b, 2026-08-08): the generic
``typical``/``ff``/``ss``/``fs``/``sf`` `.LIB` sections each already bundle
*both* the 3.3 V (`nfet_03v3_*`/`pfet_03v3_*`) *and* the 6 V
(`nfet_06v0_t`/`pfet_06v0_t` plus a corner-specific `.param` overlay --
`nfet_06v0_vth0`, `_xl`, `_tox`, ... -- consumed by the shared `nfet_06v0`/
`pfet_06v0` subcircuits) device families under one corner name. So the same
five MOS corner names this harness inherits from gf180-bandgap already skew
this repo's thick-oxide drive-rail devices too -- no new corner vocabulary is
needed for the 6 V flavor. This is exactly the kind of "what does the tool
actually do at this voltage" finding CLAUDE.md asks to record as it emerges;
noted here (not filed against klayout-tools, which is unrelated -- this is an
ngspice/PDK deck characteristic, not a layout tool gap).

## Two-rail supply axis (this repo's adaptation)

gf180-bandgap is single-supply, so its ``PvtPoint`` carries one ``vdd``. This
design has two independent, named rails (``Rail`` below): ``vlogic`` (3.3 V
±10 %) and ``vdrv`` (5 V ±10 %, spec §3 / DRM 14.1.2). ``sim/README.md``
documents the decision this module implements: the two rails are **swept
together** (locked to the same relative offset -- both low, both nominal,
both high) rather than full-factorial cross-producted. This keeps the size of
the voltage axis identical to the single-rail convention gf180-bandgap
established (CLAUDE.md commits to "±10% supply" as one axis of the PVT
matrix, not two independent axes) while still recording the exact two-rail
voltage pair present at each simulated point. See ``tied_supply_grid``.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

# Default PVT axes. CLAUDE.md mandates these on every recorded result.
DEFAULT_TEMPERATURES_C: tuple[float, ...] = (-40.0, 27.0, 125.0)
DEFAULT_SUPPLY_TOLERANCE: float = 0.10  # +/-10 %

#: The corner-id grammar's literal supply token for a testbench with no
#: supply rail to sweep -- see ``sim/README.md`` and ``PvtPoint.corner_id`` /
#: ``tied_supply_grid`` below. Matches ``evidence_lint.NO_SUPPLY``.
NO_SUPPLY = "nosupply"


def _bundle(mos: str, bjt: str, diode: str, res: str, moscap: str, mimcap: str) -> tuple[str, ...]:
    return (mos, res, bjt, diode, moscap, mimcap)


@dataclass(frozen=True)
class Corner:
    """A named process corner: an ordered list of model ``.lib`` sections."""

    name: str
    sections: tuple[str, ...]
    description: str = ""


def _all(skew: str, description: str) -> Corner:
    """Global corner: every device family skewed the same direction."""
    suffix = {"ff": "ff", "ss": "ss"}[skew]
    return Corner(
        name=skew,
        sections=_bundle(
            mos=suffix,
            bjt=f"bjt_{suffix}",
            diode=f"diode_{suffix}",
            res=f"res_{suffix}",
            moscap=f"moscap_{suffix}",
            mimcap=f"mimcap_{suffix}",
        ),
        description=description,
    )


_TYPICAL = _bundle(
    mos="typical",
    bjt="bjt_typical",
    diode="diode_typical",
    res="res_typical",
    moscap="moscap_typical",
    mimcap="mimcap_typical",
)


def _mos_only(name: str, mos_section: str, description: str) -> Corner:
    """MOS skewed, passives at typical."""
    sections = (mos_section,) + _TYPICAL[1:]
    return Corner(name=name, sections=sections, description=description)


def _passive_only(name: str, family_index: int, section: str, description: str) -> Corner:
    sections = list(_TYPICAL)
    sections[family_index] = section
    return Corner(name=name, sections=tuple(sections), description=description)


CORNERS: dict[str, Corner] = {
    "tt": Corner("tt", _TYPICAL, "all device families typical"),
    "ff": _all("ff", "all device families fast (incl. thick-oxide 06v0, see module docstring)"),
    "ss": _all("ss", "all device families slow (incl. thick-oxide 06v0, see module docstring)"),
    "fs": _mos_only("fs", "fs", "fast NMOS / slow PMOS, passives typical"),
    "sf": _mos_only("sf", "sf", "slow NMOS / fast PMOS, passives typical"),
    # Passive-dominated corners: the level-shifter's clamp and the output
    # stage's drive strength ride on resistor sheet rho as well as MOS skew.
    "res_ff": _passive_only("res_ff", 1, "res_ff", "resistors fast (low rho), rest typical"),
    "res_ss": _passive_only("res_ss", 1, "res_ss", "resistors slow (high rho), rest typical"),
    "bjt_ff": _passive_only("bjt_ff", 2, "bjt_ff", "BJTs fast, rest typical"),
    "bjt_ss": _passive_only("bjt_ss", 2, "bjt_ss", "BJTs slow, rest typical"),
}

CORNER_SETS: dict[str, tuple[str, ...]] = {
    # Minimum bar for a quick smoke run.
    "tt": ("tt",),
    # The five classic MOS corners -- the default.
    "mos": ("tt", "ff", "ss", "fs", "sf"),
    # Everything: MOS corners plus resistor / BJT skews.
    "full": ("tt", "ff", "ss", "fs", "sf", "res_ff", "res_ss", "bjt_ff", "bjt_ss"),
}
DEFAULT_CORNER_SET = "mos"


def resolve_corners(names: list[str] | tuple[str, ...] | None) -> list[Corner]:
    """Turn a list of corner *or* corner-set names into Corner objects."""
    if not names:
        names = [DEFAULT_CORNER_SET]
    resolved: list[Corner] = []
    seen: set[str] = set()
    for name in names:
        expanded = CORNER_SETS.get(name, (name,))
        for corner_name in expanded:
            if corner_name in seen:
                continue
            if corner_name not in CORNERS:
                raise KeyError(
                    f"unknown corner {corner_name!r}; "
                    f"known corners: {', '.join(sorted(CORNERS))}; "
                    f"known sets: {', '.join(sorted(CORNER_SETS))}"
                )
            seen.add(corner_name)
            resolved.append(CORNERS[corner_name])
    return resolved


# --- two-rail supply axis ----------------------------------------------------


@dataclass(frozen=True)
class Rail:
    """One named supply rail swept by the harness.

    ``name`` doubles as the corner-id token and as the ngspice parameter
    prefix the generated deck exposes (``<name>_val``, ``<name>_nom`` -- see
    ``runner.compose_deck``), so it must be a valid, lowercase-alnum ngspice
    parameter fragment.
    """

    name: str
    nominal_v: float
    tolerance: float = DEFAULT_SUPPLY_TOLERANCE
    #: Optional extra, non-default points (e.g. the 6 V stretch target from
    #: spec/gate-driver.md §3 for ``vdrv``) a testbench may opt into via
    #: ``stretch_points`` below. Never included by default -- CLAUDE.md /
    #: sim/README.md: "Do not silently widen or narrow the PVT axis."
    extra_v: tuple[float, ...] = ()


#: This design's two rails (spec/gate-driver.md §3): 3.3 V logic in,
#: 5 V drive rail out, both ±10 % per DRM 14.1.2. ``vdrv`` also carries the
#: 6 V stretch point as an opt-in extra (see ``stretch_points``).
DEFAULT_RAILS: tuple[Rail, ...] = (
    Rail("vlogic", 3.3, DEFAULT_SUPPLY_TOLERANCE),
    Rail("vdrv", 5.0, DEFAULT_SUPPLY_TOLERANCE, extra_v=(6.0,)),
)


def supply_points(nominal_v: float, tolerance: float = DEFAULT_SUPPLY_TOLERANCE) -> list[float]:
    """Nominal supply and its +/- tolerance rails, low to high, for one rail."""
    if tolerance <= 0:
        return [round(nominal_v, 6)]
    return [
        round(nominal_v * (1.0 - tolerance), 6),
        round(nominal_v, 6),
        round(nominal_v * (1.0 + tolerance), 6),
    ]


def tied_supply_grid(rails: tuple[Rail, ...] | list[Rail]) -> list[dict[str, float]]:
    """The default two-rail supply axis: every rail swept **together**.

    Each rail contributes its own low/nominal/high triple (its own nominal
    voltage and tolerance), but the harness ties them by *index* rather than
    taking the full cross product: point 0 is every rail at its low rail,
    point 1 is every rail at nominal, point 2 is every rail at its high rail.
    This is the "swept together" design decision documented in
    sim/README.md -- see the module docstring for the rationale. All rails
    must produce the same number of points (3, or 1 if a rail's tolerance is
    0) to be tied this way.

    A testbench that declares **no rails at all** (``rails: {}`` in its
    manifest -- the ``tb.json``/``PvtPoint``-grid path's equivalent of a
    device-level ``sim/device-*/run_*.py`` script's ``nosupply`` corner-id,
    see ``sim/README.md``) resolves to a single point with no supplies:
    ``PvtPoint.corner_id`` then renders the literal ``nosupply`` supply
    field instead of an empty one.
    """
    if not rails:
        return [{}]
    per_rail = [supply_points(r.nominal_v, r.tolerance) for r in rails]
    lengths = {len(p) for p in per_rail}
    if len(lengths) != 1:
        raise ValueError(
            "rails must all resolve to the same number of tied supply points "
            f"to be swept together; got {[(r.name, len(p)) for r, p in zip(rails, per_rail)]}"
        )
    n = lengths.pop()
    return [
        {rail.name: per_rail[i][j] for i, rail in enumerate(rails)} for j in range(n)
    ]


def stretch_points(rails: tuple[Rail, ...] | list[Rail]) -> list[dict[str, float]]:
    """Opt-in extra composite points: one rail at each of its ``extra_v``
    values (e.g. the 6 V stretch target), every other rail held at nominal.

    Not part of the default grid (``build_grid`` does not call this) -- a
    testbench opts in explicitly (``"stretch": true`` in its manifest) so the
    mandated ±10 % matrix is never silently widened for every experiment.
    """
    points: list[dict[str, float]] = []
    for i, rail in enumerate(rails):
        for extra in rail.extra_v:
            point = {r.name: r.nominal_v for r in rails}
            point[rail.name] = extra
            points.append(point)
    return points


@dataclass(frozen=True)
class PvtPoint:
    """One point in the PVT grid -- exactly one ngspice invocation."""

    corner: Corner
    temp_c: float
    supplies: dict[str, float]  # rail name -> voltage, insertion order = rail order
    index: int = field(default=0, compare=False)

    @property
    def corner_id(self) -> str:
        """The ``<process>_<temp>c_<supply>`` id from ``sim/README.md``.

        ``<supply>`` for this repo is one or more ``<rail><volts>v`` tokens
        (``p`` standing in for the decimal point, the grammar
        gf180-bandgap's device-characterization scripts already established
        for a named node -- e.g. ``nwell2p97v``) joined by ``-`` so the whole
        field stays the single underscore-free token the corner-id grammar
        expects: e.g. ``tt_27c_vlogic3p30v-vdrv5p00v``. Extended here to
        multiple rails, per sim/README.md. A testbench with no declared
        rails (``tied_supply_grid(())`` above) renders the literal
        ``nosupply`` token instead of an empty field.
        """
        supply_field = "-".join(
            f"{name}{_format_rail_volts(value)}v" for name, value in self.supplies.items()
        ) or NO_SUPPLY
        return f"{self.corner.name}_{self.temp_c:g}c_{supply_field}"

    def as_dict(self) -> dict:
        return {
            "corner": self.corner.name,
            "corner_sections": list(self.corner.sections),
            "temp_c": self.temp_c,
            "supplies": dict(self.supplies),
            "corner_id": self.corner_id,
        }


def _format_rail_volts(value: float) -> str:
    """``3.30`` -> ``3p30`` -- see ``PvtPoint.corner_id``."""
    return f"{value:.2f}".replace(".", "p")


def build_grid(
    corners: list[Corner],
    temperatures: list[float] | tuple[float, ...],
    supply_grid: list[dict[str, float]],
) -> list[PvtPoint]:
    """Full factorial (process corner x temperature) grid, one point per
    entry in ``supply_grid`` -- the tied two-rail supply axis is not
    additionally cross-producted (see ``tied_supply_grid``).
    """
    points = [
        PvtPoint(corner=corner, temp_c=float(temp), supplies=dict(supplies), index=i)
        for i, (corner, temp, supplies) in enumerate(
            itertools.product(corners, temperatures, supply_grid)
        )
    ]
    return points


# --- device-level (nosupply) testbenches -------------------------------------
#
# Ported from `2AMLogic/gf180-bandgap` (sim/harness/corners.py). A device-level
# testbench (a bare transistor/resistor/diode driven from ideal sources, no
# circuit supply rail) does not fit `PvtPoint`/`tied_supply_grid`/`build_grid`
# above -- those always name a *bundle* corner (`tt`, `ss`, ...) and always
# carry this repo's two named rails. A device-level testbench instead selects
# a single `.lib` section by name (`typical`, `ff`, `res_ss`, ...) and usually
# has no supply node at all -- `sim/README.md`'s corner-id grammar spells that
# with the literal supply token `nosupply`. This helper factors that naming
# rule out so every `sim/device-*/` testbench mints ids the same way instead
# of each reimplementing it (see `sim/device-mv-fet/run_device_mv_fet.py`).


def device_corner_id(section: str, temp_c: float, supply: str = "nosupply") -> str:
    """``<section>_<temp>c_<supply>`` -- the corner-id grammar's two-terminal
    device-testbench form documented in ``sim/README.md``.

    ``supply`` may also carry a named auxiliary sweep node instead of the
    literal ``nosupply`` (e.g. a well-tie sensitivity sweep outside the main
    PVT grid), which is why it is a parameter rather than hardcoded.
    """
    temp = f"{temp_c:g}".replace(".", "p")
    return f"{section}_{temp}c_{supply}"
