# gf180-gate-driver — target specification

**Status: Ratified 2026-08-05.**

This document is the ratified spec for the first design increment of this
block. It replaces the DRAFT table that previously lived in `README.md`
(see [issue #1](https://github.com/2AMLogic/gf180-gate-driver/issues/1)).
Changing any decision recorded here requires a new decision record in this
file (or a successor spec document), not a silent edit — see `CLAUDE.md`:
"Spec changes go through `spec/` with a decision record; agents do not relax
the ratified spec to make results pass."

Every PDK electrical claim below is cited to a specific page of the
`gf180mcu-pdk` documentation (`gf180mcu-pdk.readthedocs.io/en/latest/`,
GlobalFoundries GF180MCU PDK docs), re-fetched and re-verified directly on
2026-08-05 for this ratification — not copied from the issue's research
notes without re-checking. Where the documentation itself is ambiguous or
silent, that is stated explicitly rather than inferred.

## 1. Scope of this increment

**Configuration: low-side driver only.** A half-bridge / high-side
configuration is explicitly out of scope for this increment and is the
stretch target for a follow-on spec revision.

**Decision record**

| | |
|---|---|
| Options considered | (a) low-side only, single channel; (b) half-bridge, two channels with high-side bootstrap or isolated supply |
| Trade-offs | (a) is the smaller first step: one output stage, one level-shifter instance, no high-side floating-supply problem, no shoot-through hazard to protect against. (b) fully exercises the HV devices in the harder high-side-referenced regime and is closer to a sellable part, but adds a second level-shifter domain, a floating/bootstrapped supply, and dead-time/shoot-through protection — multiple new failure modes stacked on top of the medium-voltage devices this block exists to characterize. |
| Chosen | (a) low-side only |
| Rationale | Per `CLAUDE.md`, the medium-voltage devices are the point of this block, and their behavior in this tool/PDK combination is unverified. A low-side-only driver still exercises the full 5 V/6 V device set and the 3.3 V→5 V level-shifting problem — the two things this canary is actually testing — without also debugging a second, independent failure surface (high-side floating supply, dead-time). Half-bridge is deferred to a follow-on spec revision once the low-side increment has simulated and (ideally) measured results. |

## 2. Device flavors

### 2.1 What the PDK actually offers

Per PDK Design Manual, [Appendix A — Device List for Model and LVS
Deck](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_15.html)
(re-fetched 2026-08-05):

| SPICE model name | Description | Note |
|---|---|---|
| `nfet_03v3` / `pfet_03v3` (+ `_dn` deep-nwell variants) | 3.3 V NMOS/PMOS | thin-oxide, LV |
| `nfet_05v0` / `pfet_05v0` (+ `_dn`) | listed in the same table row as `nfet_06v0`/`pfet_06v0`, described as "5V NMOS/PMOS (with V5_XTOR mark layer)" | see 2.2 |
| `nfet_06v0` / `pfet_06v0` (+ `_dn`) | 6 V NMOS/PMOS | thick-oxide, MV |
| `nfet_06v0_nvt` | 6 V native/zero-Vt NMOS | not used in this design |
| `nfet_10v0_asym` / `pfet_10v0_asym` | asymmetric LDMOS, 10 V | not used in this design; noted for a possible future CAN/LIN follow-on per `CLAUDE.md` |

### 2.2 Finding: `nfet_05v0`/`pfet_05v0` are the same physical device as `nfet_06v0`/`pfet_06v0`, not a separate flavor

This is a new finding produced during ratification, not present in the
issue's research notes, and is exactly the kind of "what can these devices
actually withstand" answer `CLAUDE.md` asks to record as it emerges.

The Appendix A device table (link above) lists the `nfet_05v0`/`pfet_05v0`
row's underlying model as `nfet_06v0`/`pfet_06v0` **with an added `V5_XTOR`
mark layer** — i.e. `nfet_05v0` is not a distinct physical transistor, it is
the same thick-gate-oxide device with a marking layer that selects a
different characterization/model corner. This is corroborated independently
by the electrical-spec tables themselves: [§2.0 Medium Voltage Devices
(6V)](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_2.html)
and [§3.0 Medium Voltage Devices
(5V)](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_3.html)
both key their rows to the **identical** device mnemonics `NCH (NE2)` /
`PCH (PE2)` — the same test-structure names, just measured at a different
bias point (`|Vgs|=|Vds|=5V` vs. `6V`).

Practical consequence: choosing "5 V0 vs. 6 V0" is a **model/verification
corner** choice, not a layout choice — both flavors share layout rules,
DRC/LVS treatment, and (per §2.4 below) DNWELL placement rules. It does
**not**, by itself, resolve the DC gate-limit ambiguity noted next; that
ambiguity is about the shared thick-oxide device's absolute rating, not
about a difference between the two flavors.

### 2.3 DC gate-voltage ceiling (thin-oxide vs. thick-oxide)

Per [DRM 14.1.4.2, Voltage Limits Due to Gate Oxide
Breakdown](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html)
(re-fetched 2026-08-05, quoted verbatim): *"Maximum absolute value of DC
voltage allowed between the gate and any other FET node (gate-node voltage)
is 3.63V (for thin oxide), 6.5V/6V for 5V/6V process thick gate."*

**Unresolved ambiguity, confirmed still present on re-fetch**: this sentence
does not cleanly assign a single number to each of the 5 V and 6 V flavors —
read literally it could mean "6.5 V for the 5 V flavor, 6 V for the 6 V
flavor" or simply "approximately 6–6.5 V for the thick-gate family as a
whole." Given the §2.2 finding that `nfet_05v0`/`nfet_06v0` are the *same*
physical device differentiated only by a model-selection mark layer, the
second reading is the physically sensible one — there is one thick-oxide DC
gate ceiling, quoted in the doc as a 6.0–6.5 V range, not two different
oxide ratings for two different devices. **This design adopts 6.0 V as the
conservative DC gate-node ceiling for any thick-oxide gate terminal**
(the lower bound of the quoted range), and treats 6.5 V as the documented
absolute limit with no margin. Thin-oxide (3.3 V) gate terminals are limited
to 3.63 V DC, per the same source.

The PDK document also allows brief excursions above the DC ceiling, subject
to a duty-cycle-dependent TDDB (time-dependent dielectric breakdown)
derating not quantified numerically on this page. This design does not rely
on that allowance — the level-shifter topology in §4 is chosen specifically
so no thin-oxide terminal is designed to exceed 3.63 V even momentarily.

### 2.4 DNWELL isolation constraint

Per [DRM 7.2
Dnwell](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_07_03.html)
(re-fetched 2026-08-05, quoted verbatim): *"Both 3.3V and 5V/6V transistors
are not allowed in the same DNWELL."* Each DNWELL must be directly
surrounded by a PCOMP guard ring tied to substrate potential.

Consequence for this design: the level-shifter cell (§4), which straddles
the 3.3 V logic domain and the 5 V/6 V drive domain, must place its 3.3 V
devices and its 5 V/6 V devices in **separate** DNWELL regions (or keep the
3.3 V side entirely outside any DNWELL), each with its own guard ring. This
is recorded here so it is a schematic/floorplan constraint from the start,
not a layout-time surprise, per the issue's explicit request.

### 2.5 Device-flavor decision

**Decision record**

| | |
|---|---|
| Options considered | (a) `nfet_06v0`/`pfet_06v0` model corner for the drive-rail output stage; (b) `nfet_05v0`/`pfet_05v0` model corner for the same physical devices |
| Trade-offs | Per §2.2 these are the same physical device — the choice only affects which characterization corner (Idsat/Vt measured at `\|Vgs\|=\|Vds\|=5V` vs. `6V`) is used for sizing and simulation. The 6 V0 corner is characterized (and its `Ioff` spec measured) at the higher bias point (6.6 V, per [§2.0](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_2.html)), giving margin against the README target's 6 V stretch supply. The 5 V0 corner's `Ioff` is only characterized to 5.5 V ([§3.0](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_3.html)), which is exactly the 5 V rail's +10% overshoot allowance per [DRM 14.1.2](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html) ("supply overshoot tolerance of 10%") — leaving no characterized margin above nominal overshoot. |
| Chosen | `nfet_06v0`/`pfet_06v0` model corner for all drive-rail (output stage and thick-oxide level-shifter) devices |
| Rationale | The output stage sees the full drive-rail swing (5 V nominal, 6 V stretch per the existing README target). Using the 6 V0 corner's characterization keeps the design's operating point inside the region the PDK actually validates `Ioff`/`Idsat` for, at both the 5 V nominal point and the 6 V stretch point, at zero layout cost (§2.2 — same physical device either way). The 3.3 V logic side (pre-driver logic, input buffering) uses `nfet_03v3`/`pfet_03v3` thin-oxide devices, kept under the 3.63 V DC gate ceiling from §2.3. |

## 3. Drive strength and reference load

| Parameter | Target | Stretch |
|---|---|---|
| Drive rail | 5 V nominal (+10% overshoot per [DRM 14.1.2](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html)) | 6 V |
| Logic input | 3.3 V | — |
| Reference load | 1 nF (gate-capacitance stand-in for a mid-size discrete power MOSFET/IGBT) | — |
| Peak source/sink current | ≥ 0.5 A | 1 A |
| Propagation delay | < 50 ns | < 25 ns |
| Rise/fall into reference load | < 50 ns (10–90%) | — |
| Signoff | DRC + LVS clean | — |

**Rationale for the reference load and current target**: a 1 nF load
charged through 4 V of swing (5 V rail, ~1 V margin for switch drop) in a
20 ns 10–90% edge — leaving headroom inside the 50 ns propagation-delay
budget — requires an average charging current of `I = C·dV/dt = 1nF ×
4V / 20ns = 200 mA`. Real driver output stages source/sink well above their
average current at the start of the edge (the output impedance and load
both start at their extremes), so a 0.5 A peak target gives roughly 2–3×
margin over that average-current figure, consistent with the existing
README draft numbers. These are **design targets**, not yet verified
results — per `CLAUDE.md`, "no claim without a testbench"; PVT-corner
verification against these numbers is the job of the sim-harness follow-on
issue (§6), not this spec.

## 4. Level-shifter topology (3.3 V logic → 5 V/6 V drive rail)

This is the central design problem for this block (per `CLAUDE.md`) and is
recorded here as a first-class decision, not left to be discovered during
schematic capture or layout.

**Options considered** (general bulk-CMOS survey; see issue #1 for the
original three-option menu):

1. **Cross-coupled differential-pair latch** — two thin-oxide (3.3 V)
   NMOS pull-downs plus a cross-coupled thick-oxide PMOS latch referenced to
   the drive rail. Simple and common for LV→HV level shifting, but the
   thin-oxide pull-down transistors' drain nodes swing up toward the drive
   rail as part of normal operation — which, on a 5–6.5 V rail, risks
   exceeding the 3.63 V thin-oxide DC gate/node ceiling from §2.3 unless
   those nodes are independently clamped.
2. **Cascode/clamped level shifter** — adds thick-oxide (6 V0-corner)
   cascode devices between the thin-oxide pull-downs and the drive-rail
   latch, biased so no thin-oxide terminal ever sees more than its 3.63 V
   ceiling. Directly addresses the §2.3 constraint by construction rather
   than by relying on the PDK's unquantified duty-cycle overshoot allowance.
3. **Current-mode level shifter** — better suited to high dv/dt / high-side
   (floating-node-referenced) level shifting, which only becomes relevant if
   a future half-bridge revision changes the §1 configuration decision.

**Decision record**

| | |
|---|---|
| Options considered | 1. cross-coupled latch; 2. cascode/clamped latch; 3. current-mode |
| Trade-offs | Option 1 is the smallest cell but requires an additional clamp to keep thin-oxide nodes under 3.63 V — i.e. it degenerates into option 2 once that clamp is added, just with the clamp treated as an afterthought rather than a core part of the topology. Option 3 solves a problem (fast dv/dt on a floating reference node) that does not exist in a low-side-only configuration (§1) and adds current-mirror bias-current overhead for no benefit here. |
| Chosen | Option 2 — cascode/clamped level shifter, thick-oxide (6 V0-corner) cascode devices clamping the thin-oxide pull-down drains |
| Rationale | Directly satisfies the §2.3 DC gate-ceiling constraint for every thin-oxide node by construction, for a fixed (grounded-source, low-side) drive-rail reference — exactly this block's §1 configuration. It also composes with the §2.4 DNWELL constraint cleanly: the thin-oxide pull-down pair and the thick-oxide cascode/latch are naturally separable into distinct DNWELL regions at the schematic-partition level, since the cascode devices are the only ones that need to be in the 5 V/6 V domain's DNWELL. Option 3 is explicitly deferred, to be reconsidered if/when a half-bridge revision (§1) makes high-side, floating-reference level shifting relevant. |

## 5. Protection scope

| Feature | Status this increment | Rationale |
|---|---|---|
| UVLO (undervoltage lockout) on the 5 V/6 V drive rail | **In scope** | Operating the thick-oxide output stage and level-shifter cascode below a valid `Vgs` collapses drive strength and increases switching loss without tripping any other protection; cheap to add and directly protects the medium-voltage devices this block exists to characterize. |
| Dead-time / shoot-through control | **Deferred** | Dead-time is a non-overlap constraint between two complementary output channels. Per §1, this increment has exactly one output channel — there is nothing to sequence against. Revisit when a half-bridge revision adds a second channel. |
| Thermal shutdown | **Deferred** | Adds design complexity (a temperature sensor + shutdown comparator) disproportionate to a single-channel canary block whose primary purpose is exercising the HV devices and the level-shifter, not shipping a fully protected commercial part. Revisit if PVT/measured-silicon results (§6) show a real thermal risk at the target drive currents. |
| Overvoltage / gate-oxide protection | **In scope, structural, with two documented exceptions (decision records 0003, 0005)** | Addressed by the level-shifter topology choice itself (§4) rather than as a separate protection circuit, for every thin-oxide node exposed to the 5 V/6 V drive rail — verified across the full PVT matrix (decision record 0002). **Exception 1** (decision record 0003): the level shifter's pre-driver inverter's own output (`inb`, gate of thin-oxide `XMNPDB`, internal to the 3.3 V logic domain and never touching the drive rail) transiently overshoots its own `VDD_LOGIC` rail by 20–35 mV, only at the `vlogic3p63v` (+10 %) PVT corner — measured worst case 3.65019 V–3.66512 V across the 15 affected process×temperature points, `sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`. **Exception 2** (decision record 0005): the output stage's internal taper nodes (`n1`…`n5`, `design/output_stage.sch`, entirely thick-oxide `nfet_06v0`/`pfet_06v0`) transiently exceed the 6.0 V thick-oxide DC gate ceiling (§2.3), only at the 6 V stretch rail (never at the 4.5/5.0/5.5 V nominal-tolerance points) — measured worst case `n5` = 6.0538 V (margin −53.8 mV) across the 15 affected process×temperature points, `sim/output-stage-drive/records/20260812-064304-03699ea.md`. Neither exception invokes the PDK's duty-cycle TDDB overshoot allowance (§2.3, not invoked either time). See decision records 0003 / 0005 for the mitigation attempts investigated and why each claim is scoped this way instead. |

## 6. Verification

No simulation results exist yet for this design (the repo is pre-schematic
as of this ratification). PVT-corner verification of §3's targets is
tracked as a separate follow-on issue that will bootstrap the sim-harness
pattern from `2AMLogic/gf180-bandgap`, per `CLAUDE.md`. Per that repo's
`sim/README.md` (verified via that repo 2026-08-05, may drift — re-check
before filing the follow-on issue): the harness lays out
`sim/<experiment-slug>/{testbench/, netlist-snapshots/<record-id>.spice,
corners/<record-id>/<corner-id>.log, records/<record-id>.md}`, requires a
PVT matrix of −40/27/125 °C × ±10% supply × process corners
(tt/ss/ff/fs/sf plus per-device-family corners), and enforces append-only
records via CI.

Until that harness exists, every numeric target in §3 is a design target,
not a verified result — treat it accordingly per `CLAUDE.md`'s "no claim
without a testbench."

## 7. Open questions carried forward

- The exact numeric split (if any) of the §2.3 DC gate-node ceiling between
  the 5 V and 6 V model corners remains unresolved in the PDK documentation
  itself as of this ratification's re-fetch (2026-08-05). This design's 6.0 V
  conservative ceiling is a deliberately cautious reading, not a confirmed
  PDK number — re-verify directly against the PDK's `.model`/techfile
  source in `google/gf180mcu-pdk` before this becomes load-bearing for a
  DRC/LVS-clean layout.
- Half-bridge / high-side configuration, current-mode level shifting (§4
  option 3), and dead-time control (§5) are all deferred to a follow-on spec
  revision, not abandoned.
