# 0018: UVLO comparator PVT measurement — wide threshold spread, documented bounded finding

- **Status**: Ratified
- **Date**: 2026-08-26
- **Decided by**: Builder agent, issue #220
- **Extends**: `spec/gate-driver.md` §5 (protection scope). **Supersedes**:
  none. Does not reopen or amend decision record 0001 itself — that record's
  Decisions 4–5 explicitly flagged every number as "a design target... not
  yet a verified result" and instructed that PVT verification "is the job of
  the UVLO implementation issue this record unblocks" (i.e. this issue).
  This record is that verification, following the same bounded-exception
  shape decision records 0013/0015/0016 already established.

## Context

Issue #220 implemented `design/uvlo.sch` — the comparator/reference topology
decision record 0001 Decision 5 specifies (resistive divider off `VDD_DRV`
vs. a diode-connected `nfet_06v0` `Vt` reference, decided precisely *because*
"no bandgap exists in this block") — and instantiated it in
`design/gate_driver_core.sch` as `x3`. `design/uvlo-comparator-sizing.md`
documents the sizing derivation. This record is the PVT verification decision
record 0001's own "Consequences" section anticipated: "If simulation...
shows the Decision 4/5 numbers don't clear their stated margins... this
record must be superseded by a new decision record, not silently
redesigned in the implementation."

**Evidence**:

- `sim/uvlo-trip-verification/records/20260826-013053-6299c36.md` — standalone
  `uvlo` cell, full 15-point process×temperature grid (this cell has no
  supply rail of its own to sweep at ±10 % — `VDD_DRV` itself is the swept
  quantity, via an internal 0 V→6 V→0 V transient triangle-wave ramp per
  corner; see that script's module docstring for why a ramp rather than a
  `.dc` sweep). Measures rising/falling trip voltage, hysteresis, and lockout
  response time.
- `sim/gate-driver-core-drive-with-uvlo/records/20260826-013137-6299c36.md` —
  full block (`level_shifter` + `output_stage` + `uvlo`), the mandated
  ±10 % + 6 V stretch grid (60 points), decision record 0001 Decision 5's
  "`OUT` forced low... independent of `IN`" claim probed at `t=200 ns`
  (mid-way through `IN`'s first high pulse) via `x3.lockout`/`OUT`/`VDD_DRV`.
- `sim/gate-driver-core-drive-with-uvlo/records/20260826-013206-6299c36.md` —
  guaranteed-off supplementary point: `VDD_DRV` fixed at 2.0 V (below every
  corner's own measured falling threshold), all 15 process×temperature
  points.
- `sim/gate-driver-core-drive-with-uvlo/records/20260826-013219-6299c36.md` —
  "Challenge #5" rails (3.3 V digital / 5.0 V analog envelope, `vdrv` swept
  3.3/4.15/5.0 V instead of the spec ±10 % band), same 45-point grid.

## Finding 1 — Rising/falling trip voltage and hysteresis are wider than decision record 0001 Decision 4's targets

Decision record 0001 Decision 4: falling typ 3.6 V / worst-case range
3.3–3.9 V; rising typ 3.9 V / worst-case range 3.6–4.2 V; hysteresis typ
300 mV. Measured (standalone facet, 15 corners):

| Corner | Falling (V) | Rising (V) | Hysteresis (V) |
|---|---|---|---|
| `typical_27c` | 3.607 | 3.931 | 0.324 |
| `typical_-40c` | 4.005 | 4.333 | 0.328 |
| `typical_125c` | 3.017 | 3.341 | 0.324 |
| `ff_-40c` | 3.261 | 3.543 | 0.282 |
| `ff_27c` | 2.849 | 3.126 | 0.277 |
| `ff_125c` (worst-case-low both) | **2.231** | **2.503** | 0.273 |
| `ss_-40c` (worst-case-high both) | **4.737** | **5.115** | 0.378 |
| `ss_27c` | 4.352 | 4.726 | 0.375 |
| `ss_125c` | 3.786 | 4.162 | 0.376 |
| `fs_-40c` | 3.468 | 3.775 | 0.307 |
| `fs_27c` | 3.060 | 3.365 | 0.305 |
| `fs_125c` | 2.449 | 2.757 | 0.308 |
| `sf_-40c` | 4.526 | 4.876 | 0.350 |
| `sf_27c` | 4.137 | 4.481 | 0.344 |
| `sf_125c` | 3.566 | 3.906 | 0.340 |

**Only 4 of 15 corners** (`typical_27c`, `ss_125c`, `fs_-40c`, `sf_125c`)
land inside decision record 0001's stated worst-case ranges for both
thresholds. The measured spread is roughly 2.9 V peak-to-peak on the falling
threshold (2.231–4.737 V) and 2.6 V on the rising threshold
(2.503–5.115 V) — about three times the 0.9 V/0.6 V bands decision record
0001 budgeted per threshold. Hysteresis itself stays reasonably close to
target (273–378 mV vs. 300 mV typ, no stated worst-case range to score
against).

**Root cause**: decision record 0001 Decision 5 explicitly accepted that,
with no bandgap, "the resulting `VT0` spread (0.61–0.85 V, a ±16 % swing
around typical)... is exactly why Decision 4's thresholds carry a wide
corner range." That reasoning under-weighted two effects: (1) `VT0`'s own
**temperature** coefficient (not just its process-corner spread) moves the
diode-connected reference by several hundred mV across −40…125 °C on top of
the process spread; (2) the divider's own gain — needed to scale the
~0.7–0.8 V reference up into the 3.3–4.2 V trip-voltage range, roughly 5× —
amplifies *both* the reference's process spread and its temperature
coefficient by that same ~5× at the trip-voltage node. Decision record
0001's ±16 % `VT0` figure was never passed through that gain when the
worst-case ranges were derived, so the stated 3.3–3.9 V / 3.6–4.2 V bands
under-predicted the actual PVT spread by roughly 3×.

## Finding 2 — A genuine false-trip risk at one corner, not just a wider band

Decision record 0001 Decision 4's rationale explicitly required "the
worst-case-high rising threshold (4.2 V) sits 300 mV below the 4.50 V
low-line floor — the block cannot lock out at a legitimate −10 % rail
corner even at the comparator's worst PVT extreme." **This margin is
violated**: `ss_-40c`'s measured rising threshold, 5.115 V, sits **615 mV
above** the 4.50 V low-line floor, and its falling threshold, 4.737 V,
sits 237 mV above it too. This means at the `ss`/−40 °C process/temperature
corner, the block **remains locked out at `VDD_DRV` = 4.50 V — a
legitimate, in-spec −10 % operating point** — exactly the false-trip
failure mode decision record 0001 Decision 4 designed against.

`sf_-40c` sits closer to the same risk (falling 4.526 V, 26 mV above the
4.50 V floor) but its rising threshold (4.876 V) is below the 5.0 V nominal
point, so it releases at nominal `VDD_DRV`, unlike `ss_-40c`.

**Corroborated independently in the full-block context**
(`sim/gate-driver-core-drive-with-uvlo/records/20260826-013137-6299c36.md`,
same commit, real `level_shifter`+`output_stage` load on `OUT`, not the
standalone cell's weak 100 kΩ/6 fF stand-in): at the mandated grid's
`vdrv4p50v` point, `ss_-40c` and `sf_-40c` are the **only two of 60 points**
that measure `x3.lockout ≈ VDD_DRV` (locked, `OUT` held near 0 V) at
`t = 200 ns` while `IN` is high — every other point (including every other
corner at 4.50 V, and both of these two corners at 5.00 V and above)
measures `x3.lockout ≈ 0` (released, `OUT` tracking `IN`). This is the same
two corners the standalone facet flags, via an independent methodology (a
flat DC bias rather than a triangle-wave ramp) and a real downstream load —
strong corroboration this is a real circuit result, not a testbench
artifact, matching the "corroborated N ways" pattern decision record 0016
established.

## Finding 3 — Decision record 0001's "guaranteed-off"/"guaranteed-on" claims hold at their own literal bounds

Decision record 0001 Decision 4 also states: "Guaranteed-off window:
`VDD_DRV` < 3.3 V"; "Guaranteed-on window: `VDD_DRV` > 4.2 V." Read as
literal bounds (not the worst-case-range numbers Finding 1 shows are
violated), both hold:

- **Guaranteed-off**: `sim/gate-driver-core-drive-with-uvlo/records/20260826-013206-6299c36.md`
  fixes `VDD_DRV` at 2.0 V (below every corner's own measured falling
  threshold, worst case 2.231 V at `ff_125c`) across all 15 process×temperature
  points, full block. Every point measures `x3.lockout ≈ 2.0 V` (fully
  locked) and `OUT`'s peak excursion stays under 0.18 V despite `IN`
  toggling — `OUT` never approaches a meaningful high level at any corner.
  Confirms decision record 0001's literal "`VDD_DRV` < 3.3 V" guaranteed-off
  claim with margin (down to 2.0 V, not just up to 3.3 V).
- **Guaranteed-on**: no measured rising threshold across either the
  standalone or full-block grids reaches decision record 0001's literal
  4.2 V floor — the worst case (`ss_-40c`, 5.115 V) exceeds it by 915 mV.
  **The literal "guaranteed-on above 4.2 V" claim is also not met** at that
  corner; it is folded into Finding 2's false-trip finding above rather than
  treated as a separate result, since both describe the same underlying gap
  (measured worst-case-high rising threshold vs. decision record 0001's
  stated one).

## Finding 4 — Response time clears decision record 0001 Decision 5's target with wide margin at every corner

Measured lockout response time (`VDD_DRV` step, released → locked, crossing
that corner's own measured falling threshold, to `OUT` reaching a 0.5 V low
proxy level): 95.0–238.0 ns across all 15 corners (worst case `ss_-40c`,
consistent with that corner's slowest process skew). **All 15 corners PASS**
the < 500 ns target with at least ~55 % margin even at the worst corner.

## Finding 5 — Challenge #5 rails (3.3 V digital / 5.0 V analog envelope)

`sim/gate-driver-core-drive-with-uvlo/records/20260826-013219-6299c36.md`
(vdrv swept 3.3/4.15/5.0 V instead of the mandated ±10 % band — an
exploratory alternate-rail characterization per issue #219's framing, not a
ratified spec bound) shows a real, expected consequence of Finding 1's
spread: at `VDD_DRV = 3.3 V`, `x3.lockout` ranges from ≈0 (released, at
corners whose rising threshold sits below 3.3 V — e.g. every `ff` and `fs`
corner) up to 4.15 V (fully locked at some corners) within the same 15-point
sub-grid. **This is not a defect in this record's finding** — decision
record 0001's own numbers were derived against the 5 V/6 V nominal drive
rail, and 3.3 V sits below several corners' measured falling threshold by
construction (Finding 1's table). A future revision that wants UVLO to
function correctly on the Challenge #5 3.3 V/5.0 V envelope specifically
would need to re-derive the divider/reference sizing against *that* rail's
own low-line floor, not reuse the 5 V/6 V-derived component values as-is —
noted here as an open item for a future proposal, not resolved by this
record.

## Decision

**Decision record 0001 Decision 4's worst-case corner ranges (falling
3.3–3.9 V, rising 3.6–4.2 V) and its "guaranteed-on above 4.2 V" claim are
superseded by the measured ranges below, with the false-trip risk recorded
as an open safety finding — not silently narrowed back to the original
numbers, and not silently widened without flagging the consequence:**

- **Measured falling threshold range** (5 process corners × 3 temperatures):
  **2.231 V – 4.737 V** (`ff_125c` .. `ss_-40c`).
- **Measured rising threshold range**: **2.503 V – 5.115 V**
  (`ff_125c` .. `ss_-40c`).
- **Measured hysteresis range**: 0.273 V – 0.378 V (close to decision
  record 0001's 300 mV typical target; not itself in violation).
- **Response time**: < 240 ns at every corner, clearing the < 500 ns target
  with wide margin at every corner (decision record 0001 Decision 5's
  number is **confirmed**, not superseded).
- **Guaranteed-off** (`VDD_DRV` < 3.3 V forces lockout at every corner) is
  **confirmed**, with margin (verified down to 2.0 V).
- **Guaranteed-on above 4.2 V is NOT confirmed**: at the `ss`/−40 °C
  corner, the block remains locked out up to `VDD_DRV` = 5.115 V — **above
  the drive rail's own −10 % low-line floor (4.50 V)**, i.e. a real
  false-trip risk at that corner in otherwise-legitimate operation. This is
  recorded as an **open, unresolved safety finding**, not a bounded
  exception this record closes — see "Why no design fix is undertaken here"
  below for why a redesign is deferred rather than attempted in this issue.

`design/uvlo.sch`, `design/netlist/uvlo.spice`, and
`design/gate_driver_core.sch`/`design/netlist/gate_driver_core.spice` are
**unchanged** by this record — it documents the measured PVT behavior of the
already-committed design, per `CLAUDE.md`'s "agents do not relax the
ratified spec to make results pass." The evidence records cited above stand
as this finding's evidence; no new `sim/` record is required by this
decision record itself.

## Why no design fix is undertaken here

Per `CLAUDE.md` and the pattern decision record 0016 established, the
remaining paths are: fix the design, or formally document the finding.
Closing Finding 2's false-trip gap requires reducing the divider's
amplification of the reference's own PVT spread — e.g. a multi-diode
reference stack that builds a ~3.6–4 V reference directly (near-unity
divider gain) rather than amplifying a single ~0.75 V diode reference ~5×,
or an actual bandgap. Both are a materially different circuit from decision
record 0001 Decision 5's specified topology (a single diode-connected `Vt`
reference, chosen *because* it avoids exactly this class of added
complexity) and would need their own PVT re-verification pass, exactly the
"a multi-PR body of work, not a single-pass Builder scope" reasoning
decision record 0016 §"Why a design change... is not undertaken here" used
for a different §3 finding on this same repo. Issue #220 is explicitly the
schematic + pre-layout PVT verification slice (epic #542's own phase split);
redesigning the reference topology after measuring it is exactly the kind of
follow-on decision that belongs in a new issue with its own decision record,
not folded silently into this one.

## Alternatives considered

- **Silently narrow decision record 0001 Decision 4's numbers to whatever
  passed** — rejected outright; `CLAUDE.md` forbids relaxing the spec to
  make a result pass, and doing so here would also hide Finding 2's real
  safety gap.
- **Treat the spread as simulation noise** — rejected: consistent, large
  (order 1 V), and directly traceable to a specific, understood physical
  cause (Finding 1's root-cause analysis), the signature of a real circuit
  result.
- **Redesign the reference now, in this issue** — considered and rejected;
  see "Why no design fix is undertaken here" above.
- **Treat Finding 2 as acceptable because it only widens protection margin
  in one direction** — rejected: Finding 2 is specifically a *false-trip*
  risk (the block refuses to release at a legitimate operating point), the
  exact failure mode decision record 0001 Decision 4 was designed to avoid,
  not the safe-but-conservative direction (over-protection).

## Consequences

- Every `sim/uvlo-trip-verification/` and `sim/gate-driver-core-drive-with-uvlo/`
  record continues to report **FAIL** overall (11/15 and 3/3 respectively) —
  intentional and expected; a reviewer should check this record before
  treating a FAIL verdict on these facets as a regression, same convention
  decision record 0016 established for `sim/output-stage-drive/`.
- **Finding 2 (false-trip risk at `ss`/−40 °C) is an open safety item**, not
  closed by this record. A future revision that redesigns the reference to
  close it must re-verify, in the same pass: `sim/uvlo-trip-verification/`
  (full 15-point grid) and `sim/gate-driver-core-drive-with-uvlo/` (full
  grid, all three facets: default rails, guaranteed-off, Challenge #5), and
  should re-derive the sizing basis against the drive rail's actual −10 %
  low-line floor (4.50 V) directly, per decision record 0001 Decision 4's
  original margin rationale, rather than the informal typ-target hand-solve
  `design/uvlo-comparator-sizing.md` used for the current values.
- Issue #221 (layout) inherits the current, PVT-imperfect comparator as its
  LVS reference — this record does not block that (layout/DRC/LVS does not
  depend on the comparator's trip-voltage accuracy), but a reader of #221's
  own results should know the schematic-level comparator this finding
  documents, not a corrected one, is what gets drawn.
- If a future half-bridge/Challenge-5 revision needs UVLO to function
  correctly on the 3.3 V/5.0 V envelope specifically (Finding 5), the
  reference/divider sizing needs re-deriving against that rail's own
  low-line floor from the outset, not reused from the 5 V/6 V-derived
  values this record measures.
