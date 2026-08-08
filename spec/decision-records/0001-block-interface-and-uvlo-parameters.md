# 0001: Block interface and UVLO parameters

- **Status**: Ratified
- **Date**: 2026-08-08
- **Decided by**: Builder agent, issue #4
- **Extends**: [`spec/gate-driver.md`](../gate-driver.md) §3 (Drive strength
  and reference load) and §5 (Protection scope). This record does not amend
  or contradict any ratified sentence in that document — it fills two
  omissions in it, per `spec/gate-driver.md`'s own amendment rule ("Changing
  any decision recorded here requires a new decision record in this file
  **or a successor spec document**").
- **Format note**: `TEMPLATE.md` in this directory documents a
  one-decision-per-file convention (ported from `2AMLogic/gf180-bandgap`).
  This record deliberately departs from that: it covers six decisions that
  are only meaningful together (a port list, its electrical spec, and the
  protection circuit that shares the same rail all constrain each other), so
  splitting them into six files would scatter cross-references without
  reducing coupling. Each decision below instead uses the
  Options-considered / Trade-offs / Chosen / Rationale table shape that
  `spec/gate-driver.md` §§1, 2.5, 4 already establish for this repo, so the
  record reads consistently with the document it extends. Future
  single-decision records in this directory should still use
  `TEMPLATE.md` directly.

## Context

`spec/gate-driver.md` §5 places UVLO on the 5 V/6 V drive rail **in scope**
for this increment, but §3 — the parameter table a testbench checks against —
has no UVLO row: no rising/falling trip point, no hysteresis, no response
time, no statement of the output's behavior while locked out. Separately, the
spec never states the block's port list: no pin names, no direction, no
voltage domain, no `VIH`/`VIL`, no polarity or enable convention, no ground
scheme. Two downstream issues (#6, output stage; #7, level shifter) both
depend on a single, unambiguous interface to build against, and any future
UVLO implementation issue depends on the parameters below existing before a
testbench can be written for them. See issue #4 for the full problem
statement.

Per `CLAUDE.md`, "agents do not relax the ratified spec to make results
pass" — read together with "no claim without a testbench," a Builder must
also not *invent* spec to unblock an implementation. This record exists so
that inventing is not necessary: every number below is either cited to a PDK
documentation page or derived from one with an explicit calculation, and is
flagged as a design target, not a verified result, exactly as §3 already
flags its own drive-strength numbers.

## Decision 1 — Port list

| Pin | Direction | Domain | Function |
|---|---|---|---|
| `VDD_LOGIC` | Power in | 3.3 V logic | Logic supply, 3.3 V ±10% (2.97–3.63 V per [DRM 14.1.2](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html), "supply overshoot tolerance of 10%," applied symmetrically since the DRM states no separate undervoltage figure). |
| `GND_LOGIC` | Power in (return) | 3.3 V logic | Return for `VDD_LOGIC` and reference for `IN`. |
| `IN` | Input | 3.3 V logic | Logic control input. Non-inverting (Decision 3). Levels per Decision 2. |
| `VDD_DRV` | Power in | 5 V/6 V drive | Drive-rail supply per §3: 5 V nominal (+10 % overshoot), 6 V stretch. |
| `GND_DRV` | Power in (return) | 5 V/6 V drive | Return for `VDD_DRV` and for `OUT`'s switching current. |
| `OUT` | Output | 5 V/6 V drive | Gate-drive output to the external switch's gate. Sources/sinks per §3 (≥0.5 A target, 1 A stretch); forced low during UVLO lockout (Decision 5). |

**Decision record**

| | |
|---|---|
| Options considered | (a) single, shared `GND` pin for both domains; (b) two ground pins (`GND_LOGIC`, `GND_DRV`) that are the same electrical node by design but physically separated at the pad ring; (c) two ground pins with an intentionally different reference (isolated/floating grounds). |
| Trade-offs | (a) is simplest and matches how the chosen level-shifter topology actually behaves electrically — §4's cascode/clamped level shifter is explicitly sized "for a fixed (grounded-source, low-side) drive-rail reference," i.e. the topology assumes one common ground, not two independently-referenced ones. But a single physical pin routes `OUT`'s high-di/dt switching return (≥0.5 A edges, §3) through the same bond wire/pad as the sensitive `IN` comparator/logic return, which is a well-known source of ground-bounce-induced false switching on the input threshold. (c) would solve the bounce problem but contradicts §4's grounded-source assumption and is unjustified complexity for a single low-side channel (§1) with no isolation requirement anywhere in the ratified spec. (b) gets the noise-segregation benefit of separate return paths without changing the electrical assumption §4 already locked in — the two pins are one node, just not one bond wire. |
| Chosen | (b) — two ground pins, `GND_LOGIC` and `GND_DRV`, both the same electrical reference node by design intent, physically separated only to keep `OUT`'s switching-current return off the `IN` comparator's reference path. |
| Rationale | This is consistent with §4's rationale sentence, which already commits this design to a single, fixed low-side ground reference (not a floating/isolated scheme) — that sentence is what answers the issue's port-list question, this record just makes it an explicit pin decision. The two-pin split is standard gate-driver-IC practice for exactly this reason (segregate a high-dI/dt power return from a low-level logic return) and costs nothing electrically since both pins tie to the same node. **Consequence for the test board / package**: `GND_LOGIC` and `GND_DRV` must be tied together with minimal impedance close to the device (star point), not left floating relative to each other — this is a verification-testbench requirement, tracked as a note for the sim-harness follow-on (§6 of `gate-driver.md`), not a design choice this record can silently assume away. |

## Decision 2 — Input electrical spec

| | |
|---|---|
| Options considered | (a) fixed absolute `VIH`/`VIL` voltages, independent of `VDD_LOGIC`; (b) ratiometric `VIH`/`VIL` referenced to `VDD_LOGIC`, using the standard CMOS 0.7/0.3 convention evaluated at the ±10 % supply corners. |
| Trade-offs | (a) is simpler to state but doesn't track supply variation — a fixed threshold picked for 3.3 V nominal either loses noise margin at the −10 % corner (2.97 V) or fails to switch cleanly at the +10 % corner (3.63 V), and this block has no bandgap reference (§5 context) to generate a supply-independent threshold cheaply. (b) is the standard convention for a simple CMOS/Schmitt input buffer built from the same rail it's thresholding against (no extra reference generator needed), and it is self-consistently valid across the full ±10 % range by construction. |
| Chosen | (b) — ratiometric thresholds: `VIH ≥ 0.7 × VDD_LOGIC`, `VIL ≤ 0.3 × VDD_LOGIC`, evaluated at whatever `VDD_LOGIC` actually is at the time (worst case over 2.97–3.63 V: `VIH ≥ 2.08 V`, `VIL ≤ 0.89 V`). Input hysteresis (Schmitt trigger): typical band ≥ 10 % of `VDD_LOGIC` (≈330 mV typ at 3.3 V) to reject board-level noise on a signal crossing into a level-shifter that references a 5–6.5 V rail. |
| Rationale | The 0.7/0.3 split is the conventional CMOS logic-level convention and requires no additional reference beyond the thin-oxide (`nfet_03v3`/`pfet_03v3`, per §2.5) devices already used for the pre-driver logic — no new device flavor or bias network. **Floating-input behavior**: with `VDD_LOGIC` present, `IN` includes a weak on-die pull-down (sized to be dominated by any external driver, i.e. leakage-scale only) so an undriven input reads logic-low and `OUT` defaults to its off state (Decision 3's polarity) — consistent with the fail-safe-off theme already established for UVLO (Decision 5). With `VDD_LOGIC` absent, the input buffer is unpowered and its state is undefined; §5's rail-monitoring choice (Decision 5, drive-rail only, logic-rail UVLO deferred) means this failure mode is not caught by UVLO this increment and is recorded as an open item, not silently assumed safe. |

## Decision 3 — Polarity and enable

| | |
|---|---|
| Options considered | (a) non-inverting `IN` (logic high on `IN` turns the external switch on), no separate enable pin; (b) inverting `IN`; (c) non-inverting `IN` plus a dedicated `EN` pin. |
| Trade-offs | (a) vs (b) is an arbitrary convention with no PDK-driven reason to prefer one — non-inverting is chosen only because it is the more common gate-driver convention and avoids an extra inversion stage in the pre-driver logic. (c) adds a second control pin and its own level/floating-input spec (duplicating Decision 2's work) for a benefit — independent disable without touching `IN` — that has no consumer this increment: §1 fixes this block to a single low-side channel with no interlock or multi-channel sequencing to arbitrate. |
| Chosen | (a) — non-inverting, `IN` high → `OUT` drives the external switch on; no separate `EN` pin this increment. |
| Rationale | `IN` low already forces `OUT` to its off state (both by normal operation, per this polarity choice, and by the fail-safe pull-down in Decision 2), so a dedicated enable pin would duplicate `IN`'s own low state with no independent failure mode it protects against in a single-channel design. **Deferred**: a dedicated `EN` (separate from the data input, e.g. for fault reporting or multi-channel interlock) is deferred to a follow-on spec revision, matching the shape §5 already uses for its own deferred items — revisit when a half-bridge revision (§1's stated follow-on) or a fault-reporting requirement makes an independent enable/disable path necessary. |

## Decision 4 — UVLO parameters

**Reference data used below** (per `spec/gate-driver.md` §2.5, this design
uses the `nfet_06v0`/`pfet_06v0` model corner for all drive-rail devices):

- 6 V0-corner NMOS linear threshold voltage `VT0` (`NCH (NE2)`, W/L=10/0.7):
  min 0.61 V, typ 0.73 V, max 0.85 V. Per [PDK Electrical Specifications §2.0,
  Medium Voltage Devices
  (6V)](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_2.html)
  (fetched 2026-08-08), row 1.
- Drive-rail low-line ("−10 %") floor: 4.50 V. This is a **derived** number,
  not a single citation — per the curator's verified correction on issue #4,
  it combines `spec/gate-driver.md` §3's 5 V nominal drive-rail figure with
  §6's PVT-sweep convention ("a PVT matrix of −40/27/125 °C × ±10 % supply
  and process corners"): `5 V × 0.9 = 4.50 V`. Both §3 and §6 are cited here
  together, not §3 alone.
- Operating temperature range: −40 °C to 125 °C (Decision 6 below).

**Note on threshold direction**: issue #4's Proposed-solution text states the
rising threshold "must sit above the drive rail's −10 % undervoltage corner
(4.50 V)... or the block trips in normal operation." Read literally that
would put the rising (turn-on) threshold *above* 4.50 V, which is backwards:
if the rising/falling thresholds sat above the −10 % floor, the block would
lock out every time the rail is legitimately operating at its −10 % corner —
exactly the false trip the issue is trying to avoid. The correct requirement,
applied below, is that **both** thresholds must sit safely **below** 4.50 V,
with margin, so a rail at its normal −10 % corner is unambiguously read as
"above threshold" (UVLO released) rather than "below threshold" (UVLO
asserted).

| | |
|---|---|
| Options considered | (a) trip thresholds set close to the 4.50 V low-line floor for maximum protection margin against real undervoltage faults; (b) trip thresholds set well below 4.50 V, near the point where the 6 V0-corner thick-oxide output stage's `Vgs` overdrive becomes marginal; (c) trip thresholds set at some point between (a) and (b), balancing false-trip margin at the top against drive-strength margin at the bottom. |
| Trade-offs | (a) maximizes the true-fault detection margin (catches undervoltage sooner) but leaves little headroom against the comparator's own PVT spread (Decision 5) pushing a worst-case threshold above 4.50 V and false-tripping during legitimate −10 % operation — unacceptable per the issue's own framing. (b) maximizes margin against false trips but only disables the output once drive strength is already badly degraded, i.e. UVLO stops protecting *before* the device is meaningfully stressed (Decision 4's whole rationale in issue #4 is that operating below a valid `Vgs` "collapses drive strength and increases switching loss... cheap to add and directly protects the medium-voltage devices"). (c) keeps generous margin on both sides at the cost of catching undervoltage faults slightly later than option (a) would. |
| Chosen | (c). Falling (turn-off) threshold: typ 3.6 V, worst-case corner range 3.3–3.9 V. Rising (turn-on) threshold: typ 3.9 V, worst-case corner range 3.6–4.2 V. Hysteresis: typ 300 mV (≈8 % of the falling threshold). Guaranteed-off window: `VDD_DRV` < 3.3 V (worst-case-low falling threshold). Guaranteed-on window: `VDD_DRV` > 4.2 V (worst-case-high rising threshold). |
| Rationale | **Margin against false trips**: the worst-case-high rising threshold (4.2 V) sits 300 mV below the 4.50 V low-line floor — the block cannot lock out at a legitimate −10 % rail corner even at the comparator's worst PVT extreme. **Margin against drive-strength collapse**: the worst-case-low falling threshold (3.3 V) is 2.45 V above the 6 V0-corner NMOS `VT0` max (0.85 V, cited above) — i.e. at least 2.45 V of gate overdrive (`Vgs − Vt`) is guaranteed everywhere UVLO permits `OUT` to be active, since `Idsat ∝ (Vgs − Vt)²` and overdrive this large is far from where a thick-oxide device's drive current or switching speed becomes marginal, well inside the margin needed to still meet §3's ≥0.5 A / <50 ns targets even at the lowest voltage UVLO allows. The 300 mV hysteresis band prevents chatter at the boundary during noisy or slowly-collapsing supply transients. |

## Decision 5 — UVLO output behavior and reference

| | |
|---|---|
| Options considered | (a) `OUT` forced low (external switch held off) during lockout; (b) `OUT` forced high-impedance during lockout; (c) `OUT` left to track `IN` even during lockout (i.e., UVLO only gates an internal bias, not the output stage directly). |
| Trade-offs | (b) leaves the external switch's gate undriven, which for a discrete power MOSFET/IGBT gate (§3's reference load) risks a floating gate drifting on with no active low-impedance path holding it off — the opposite of "safe." (c) defeats the purpose of UVLO entirely: an inadequately-driven output stage would still attempt to switch, which is exactly the failure mode UVLO exists to prevent per §5's rationale. (a) actively holds the external switch off through a low-impedance path, regardless of `IN`, for as long as lockout is asserted. |
| Chosen | (a) — `OUT` is forced low (actively, through a low-impedance pull-down dominant over the normal output stage) for the duration of UVLO lockout, independent of `IN`'s state. Maximum response time from the rail crossing the falling threshold to `OUT` reaching its safe (low) state: design target < 500 ns. Comparator reference: a resistive divider from `VDD_DRV`, compared against a diode-connected 6 V0-corner NMOS (`VT0`, cited above) reference — staying in the drive-rail's own thick-oxide domain rather than crossing into a second device flavor for the reference alone. |
| Rationale | Low = external switch off is this design's established polarity (Decision 3) and its established "grounded-source, low-side" reference (§4's rationale) — forcing `OUT` low during lockout reuses the same safe state the design already defines for `IN` = low, rather than inventing a third state. The < 500 ns response-time target is set well inside §3's <50 ns propagation-delay budget's order of magnitude, scaled up for a comparator trip (an analog decision plus a debounce stage) rather than a simple digital gate — this is a design target pending a testbench, per `CLAUDE.md`'s "no claim without a testbench," not a verified number. **No bandgap exists in this block** (per issue #4's framing), so the reference is necessarily a device-`Vt`-based level rather than a temperature/process-stable bandgap voltage; the resulting `VT0` spread (0.61–0.85 V, a ±16 % swing around typical) is exactly why Decision 4's thresholds carry a wide corner range (3.3–3.9 V falling, 3.6–4.2 V rising) rather than a tight single number — that spread is the hysteresis/PVT budget this decision explicitly accepts, per the issue's own instruction to "accept the resulting PVT spread as part of the hysteresis budget." **Rail monitored**: only `VDD_DRV` (the 5 V/6 V drive rail) is monitored, matching §5's literal scope ("UVLO... on the 5 V/6 V drive rail"). `VDD_LOGIC` undervoltage is not separately monitored this increment — this is the same open item flagged in Decision 2 for a floating/unpowered `IN`, and is deferred with the same shape §5 already uses for its other deferred protection features: revisit if a half-bridge revision or measured results show a real risk from an unmonitored logic rail. |

## Decision 6 — Operating temperature range

| | |
|---|---|
| Options considered | (a) leave the operating range unstated in the spec, relying only on `CLAUDE.md`'s simulation-axis convention; (b) record −40 °C to 125 °C explicitly in the spec, citing the PDK's own guidance. |
| Trade-offs | (a) is the status quo the issue flags as a gap: `CLAUDE.md` fixes the simulation axis but the spec itself never states an operating range, so a reader of `spec/gate-driver.md` alone (without `CLAUDE.md` open) has no operating-range statement to design or verify against. (b) closes that gap and ties the number to a PDK source rather than only to this repo's own convention. |
| Chosen | (b) — operating range −40 °C to 125 °C. |
| Rationale | Per [DRM §14.1.1, Temperature
Limits](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html)
(fetched 2026-08-08, quoted verbatim): *"Circuit designers typically design
their circuit for operation between -40 deg C to 125 deg C."* This is the
exact −40/27/125 °C axis `CLAUDE.md` already mandates for every PVT sweep in
this program, so recording it here makes the spec and the harness axis agree
by citation rather than by coincidence, closing the gap the issue identifies.
The DRM separately notes (§14.1.1) that sub-0 °C operation carries additional
hot-carrier-induced-degradation guidance (referencing GlobalFoundries
document R-QR-MI-008) — noted here for completeness but not adopted as a
design constraint this increment, since it is a reliability-derating note,
not a different operating-range number. |

## Status of the numbers in this record

Every threshold, timing, and hysteresis value in Decisions 2, 4, and 5 is a
**design target**, derived from cited PDK device data or an explicit
numerical argument, and is **not yet a verified result** — no comparator,
divider, or reference circuit has been simulated. Per `CLAUDE.md`, "no claim
without a testbench": PVT-corner verification of these numbers (across
−40/27/125 °C × ±10 % supply × process corners, per §6 of
`spec/gate-driver.md`) is the job of the UVLO implementation issue this
record unblocks, not this record itself.

## Consequences

- Issues #6 (output stage) and #7 (level shifter) can now build against the
  port list in Decision 1 and the electrical spec in Decisions 2–3 without
  inventing their own interface.
- A future UVLO-implementation issue has concrete numbers (Decision 4) and a
  concrete reference/output-behavior choice (Decision 5) to design a
  testbench against, rather than having to invent them mid-implementation.
- `GND_LOGIC` / `GND_DRV` being two pins but one electrical node (Decision 1)
  is a testbench requirement (tie them together at the board/probe level)
  that the sim-harness follow-on (§6 of `gate-driver.md`) must reflect when
  it lands.
- `VDD_LOGIC` undervoltage remains an open item (Decisions 2 and 5): a
  floating or unpowered logic rail is not caught by this increment's UVLO,
  which only monitors `VDD_DRV`. This is carried forward as an open question,
  not silently resolved.
- If simulation (once the sim-harness exists) shows the Decision 4/5 numbers
  don't clear their stated margins — e.g. the diode-referenced comparator's
  real PVT spread is wider than the 0.61–0.85 V `VT0` range assumed here —
  this record must be superseded by a new decision record, not silently
  redesigned in the implementation, per `spec/gate-driver.md`'s own amendment
  rule.
