"""Monte Carlo / **local device mismatch** sampling for gf180mcu decks.

This module is the harness's answer to a gap ``sim/README.md``'s record
schema has always reserved a field for but which no record had ever
populated: every recorded PVT result in this repo is a **global process
corner** claim (``tt``/``ff``/``ss``/``fs``/``sf``), which captures
die-to-die and wafer-to-wafer skew but says nothing about **within-die
mismatch** between two nominally-identical devices on the same die at the
same corner. See ``sim/README.md``'s "Monte Carlo / local-mismatch
convention" section for the ratified convention this module implements, and
``sim/gate-driver-indrv-mismatch/`` for the first campaign that uses it.

What the installed PDK actually ships (issue #204)
--------------------------------------------------

Confirmed by reading the installed ``gf180mcuD`` decks
(open_pdks ``c6d73a35f524070e85faff4a6a9eef49553ebc2b``), not by assuming a
foundry convention:

* ``libs.tech/ngspice/design.ngspice`` defines two global switches,
  ``sw_stat_global`` (die-to-die/global skew) and ``sw_stat_mismatch``
  (intra-die mismatch), **both defaulting to 0** -- so every deck this
  harness has generated so far ran with statistical modeling entirely off,
  and its corner skew came only from the deterministic ``.LIB`` sections.
  The file's own comment table is explicit that ``sw_stat_mismatch``
  "includes intra-die variation, and it is especially critical for analog
  matching applications".
* ``libs.tech/ngspice/sm141064.ngspice``'s ``.lib fets_mm`` section -- which
  every one of the five MOS corner sections (``typical``/``ff``/``ss``/
  ``fs``/``sf``) already pulls in unconditionally -- defines subcircuit
  wrappers named ``nfet_03v3``, ``pfet_03v3``, ``nfet_05v0``, ``nfet_06v0``,
  ``pfet_05v0``, ``pfet_06v0`` whose MOS instance line carries
  ``delvto='mis_vth*sw_stat_mismatch'`` and
  ``mulu0='1-mis_k*sw_stat_mismatch'``, with ``mis_vth``/``mis_k`` drawn per
  *instance* from ``agauss(0, var, 1)`` and ``var`` scaled Pelgrom-style by
  ``1/sqrt(W_eff * L_eff)``. This repo's netlists instantiate exactly those
  names as ``X`` subcircuit calls (``design/netlist/level_shifter.spice``,
  ``design/netlist/output_stage.spice``), so **turning the switch on is all
  that is required** -- no netlist edit, no device swap.
* **Not** covered by any shipped distribution: the MiM capacitor. The
  ``mimcap_typical``/``_ss``/``_ff`` sections define a mismatch hook
  (``mc_c_cox_1p0fF``/``_1p5fF``/``_2p0fF``, consumed by
  ``sm141064_mim.ngspice``'s ``c_c0``) but hardcode all three to ``0`` in
  every corner, and nothing in the PDK ever assigns them a distribution.
  They are also ``.LIB``-scope parameters, i.e. one value shared by every
  instance, so even a hand-supplied sigma would model *global* capacitance
  skew rather than device-to-device mismatch. Resistors are the same story
  one level up: ``.lib res_statistical`` draws ``agauss`` sheet-rho
  deviations but gates them on ``sw_stat_global``, not
  ``sw_stat_mismatch``.
* Within the MOS families the PDK ships, the current-factor coefficient
  ``par_k`` is **zero for `nfet_05v0`/`nfet_06v0`** and non-zero for every
  other family -- so the thick-oxide n-channel devices get threshold
  mismatch only, no beta mismatch, in this deck.

Sampling model
--------------

ngspice evaluates ``agauss`` at netlist-parse time and draws independently
per subcircuit *instance*, so **one ngspice invocation is one Monte Carlo
sample of the whole circuit** -- which maps exactly onto the harness's
existing "one PVT point is one ngspice invocation" model. Reproducibility
comes from ``.options seed=<n>``: a deck re-run at the same seed reproduces
its draws bit-for-bit, and a different seed redraws. :func:`sample_seed`
derives every sample's seed deterministically from one recorded base seed so
a record's whole distribution is reproducible from two integers.

Sample :data:`CONTROL_SAMPLE` (0) is reserved for the **deterministic
zero-sigma negative control**: ``sw_stat_mismatch=0``, i.e. the same deck
with mismatch switched back off, which must reproduce the corresponding
process-corner run *exactly*. That control is what makes a Monte Carlo
record checkable: it proves the MC deck is the same deck as the corner
matrix's, and that the spread reported is mismatch rather than a deck
difference or solver noise.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .corners import PvtPoint

#: The two global statistical switches ``design.ngspice`` defines (both 0 by
#: default). ``sw_stat_global`` is deliberately pinned **off** by
#: :meth:`MismatchSample.deck_lines`: the deterministic ``.LIB`` process
#: corner the deck already carries is this harness's global-skew axis, so
#: letting the PDK also draw a random global skew would double-count it and
#: make a "mismatch at the ``ss`` corner" claim mean something else entirely.
SW_STAT_MISMATCH = "sw_stat_mismatch"
SW_STAT_GLOBAL = "sw_stat_global"

#: Sample index reserved for the deterministic zero-sigma control (see the
#: module docstring). Every other sample index draws mismatch.
CONTROL_SAMPLE = 0

#: Highest sample index :func:`sample_seed`'s default stride keeps collision
#: free within one PVT point. Sample indices are formatted into the corner-id
#: as four digits, which caps them at the same place.
MAX_SAMPLE = 9999

#: Device families whose gf180mcu subcircuit wrapper carries a per-instance
#: mismatch term (``.lib fets_mm``), i.e. the families a mismatch run of this
#: repo's netlists actually perturbs. Recorded here so a record can state its
#: coverage without re-deriving it from the PDK deck each time.
MISMATCH_FAMILIES: tuple[str, ...] = (
    "nfet_03v3",
    "pfet_03v3",
    "nfet_05v0",
    "nfet_06v0",
    "pfet_05v0",
    "pfet_06v0",
)

#: Device families this repo's netlists use that the PDK ships **no**
#: per-instance mismatch distribution for -- see the module docstring. A
#: record that claims mismatch coverage must say these are excluded.
NO_MISMATCH_FAMILIES: tuple[str, ...] = (
    "cap_mim_1f0_m4m5_noshield",
    "cap_mim_1f5_m4m5_noshield",
    "cap_mim_2f0_m4m5_noshield",
)


@dataclass(frozen=True)
class MismatchSample:
    """One Monte Carlo draw (or the control) at one PVT point.

    ``sample`` is the index within the PVT point's sample set;
    :data:`CONTROL_SAMPLE` means "mismatch off". ``seed`` is the ngspice
    random seed the deck pins, recorded so the draw is reproducible.
    """

    sample: int
    seed: int

    def __post_init__(self) -> None:
        if self.sample < 0 or self.sample > MAX_SAMPLE:
            raise ValueError(
                f"sample index {self.sample} out of range 0..{MAX_SAMPLE} "
                "(it is formatted as four digits into the corner-id)"
            )

    @property
    def enabled(self) -> bool:
        """Whether this deck draws mismatch at all."""
        return self.sample != CONTROL_SAMPLE

    @property
    def token(self) -> str:
        """``mc0000`` / ``mc0042`` -- the corner-id's sample token.

        Lowercase alphanumeric, so it is a legal *process* token under the
        corner-id grammar ``sim/README.md`` ratifies and
        ``harness/evidence_lint.parse_corner_id`` enforces (the process field
        is "one or more lowercase alphanumeric tokens" joined by ``_``).
        """
        return f"mc{self.sample:04d}"

    def deck_lines(self) -> list[str]:
        """The deck fragment that switches this sample's statistics on.

        Emitted *after* the corner ``.lib`` sections, because
        ``design.ngspice`` (included ahead of them) sets both switches to 0
        and ngspice takes the last ``.param`` definition of a name.
        """
        return [
            "",
            "* ---- statistical (local device mismatch) ----------------------------",
            "* gf180mcu design.ngspice switches. sw_stat_global stays 0: the "
            "deterministic",
            "* .LIB process corner above is this harness's global-skew axis, so a "
            "second,",
            "* random global skew would double-count it (sim/harness/montecarlo.py).",
            f".param {SW_STAT_GLOBAL}=0",
            f".param {SW_STAT_MISMATCH}={1 if self.enabled else 0}",
            f".options seed={self.seed}",
        ]


#: Distance between consecutive PVT points' seed blocks in
#: :func:`sample_seed`. Larger than :data:`MAX_SAMPLE` so two PVT points can
#: never share a seed.
SEED_STRIDE = 10_000


def sample_seed(base_seed: int, point_index: int, sample: int, stride: int = SEED_STRIDE) -> int:
    """Deterministic per-sample ngspice seed.

    ``base_seed + point_index * stride + sample`` -- one recorded integer
    (plus the point ordering, which the record's own grid table fixes)
    regenerates every draw in a campaign. ``stride`` exceeds
    :data:`MAX_SAMPLE`, so no two PVT points in a campaign can collide on a
    seed and accidentally share a draw.
    """
    if not 0 <= sample <= MAX_SAMPLE:
        raise ValueError(f"sample index {sample} out of range 0..{MAX_SAMPLE}")
    if stride <= MAX_SAMPLE:
        raise ValueError(
            f"seed stride {stride} must exceed the maximum sample index {MAX_SAMPLE} "
            "or two PVT points would share seeds"
        )
    return base_seed + point_index * stride + sample


def mc_point(point: PvtPoint, sample: MismatchSample) -> PvtPoint:
    """``point`` re-labelled with ``sample``'s token in its process field.

    The harness identifies a run by :attr:`PvtPoint.corner_id`, and uses it
    for the raw-log filename, so a Monte Carlo campaign needs one id per
    sample. Folding the ``mc<NNNN>`` token into the *process* field keeps the
    id inside the ratified grammar (``ss_mc0042_125c_vlogic3p30v-vdrv6p00v``
    parses as process ``ss_mc0042``, temp ``125c``, supply
    ``vlogic3p30v-vdrv6p00v``) rather than inventing a fourth field the
    evidence linter would reject.

    Only the corner's *name* changes; its ``.lib`` sections -- the actual
    process skew simulated -- are carried through untouched.
    """
    corner = replace(
        point.corner,
        name=f"{point.corner.name}_{sample.token}",
        description=(
            f"{point.corner.description}; "
            + (
                f"local mismatch sample {sample.sample} (ngspice seed {sample.seed})"
                if sample.enabled
                else "zero-sigma control (mismatch off)"
            )
        ),
    )
    return replace(point, corner=corner)
