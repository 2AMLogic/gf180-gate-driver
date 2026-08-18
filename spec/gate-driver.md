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
| Overvoltage / gate-oxide protection | **In scope, structural, with three documented exceptions (decision records 0003, 0005, 0006; Exception 2's quantification and bound narrowed by decision record 0013; Exception 3's bound narrowed by decision record 0007, its measured figure re-stated by decision record 0014)** | Addressed by the level-shifter topology choice itself (§4) rather than as a separate protection circuit, for every thin-oxide node exposed to the 5 V/6 V drive rail — verified across the full PVT matrix (decision record 0002). **Exception 1** (decision record 0003): the level shifter's pre-driver inverter's own output (`inb`, gate of thin-oxide `XMNPDB`, internal to the 3.3 V logic domain and never touching the drive rail) transiently overshoots its own `VDD_LOGIC` rail by 20–35 mV, only at the `vlogic3p63v` (+10 %) PVT corner — measured worst case 3.65019 V–3.66512 V across the 15 affected process×temperature points, `sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`, re-confirmed unregressed by `sim/level-shifter-oxide-safety/records/20260817-201021-ce8027d.md` after decision record 0007's `XCCOMP` addition and again by `sim/level-shifter-oxide-safety/records/20260818-060158-673fcf0.md` after decision record 0014 re-modeled `XCCOMP` onto four series 2 fF/µm² MIM devices (20.34–35.33 mV there, against 20.42–35.84 mV for the *uncompensated* circuit at the same post-issue-#156 `reltol=1e-4` tolerance — note that the uncompensated control now exceeds this band's stated 35 mV upper figure by 0.84 mV on solver-tolerance grounds alone, a stale-figure question decision record 0014 deliberately leaves to a follow-up rather than widening decision record 0003's ratified band here). **Exception 2** (decision record 0005, quantification amended by decision record 0006, further amended and bounded by decision record 0013): the output stage's internal taper nodes (`n1`…`n5`, `design/output_stage.sch`, entirely thick-oxide `nfet_06v0`/`pfet_06v0`) transiently exceed the 6.0 V thick-oxide DC gate ceiling (§2.3), only at the 6 V stretch rail (never at the 4.5/5.0/5.5 V nominal-tolerance points) — measured worst case, under the harness's post-issue-#156 `reltol=1e-4` tolerance, `n1` = 6.14803 V (margin −148.0 mV) at `ss_-40c_vlogic3p30v-vdrv6p00v` across the 15 affected process×temperature points, `sim/gate-driver-core-drive/records/20260817-202640-d7bda87.md` (schematic DUT; this supersedes decision record 0006's own `n1` = 6.10232 V / −102.3 mV figure, measured before the harness-tolerance fix; a companion extracted-DUT, no-RC-parasitic postlayout re-run corroborates a smaller excursion at the same corner, 6.13027 V / −130.3 mV, `sim/gate-driver-core-drive-postlayout/records/20260818-002620-ac84870.md`). **Bounded at ≤ 175 mV above the ceiling** (decision record 0013) — a wider bound than Exception 3's ≤ 10 mV, sized to absorb further deck-fidelity resolution this exception has not yet had run against its own binding corner (unlike Exception 3, per decision record 0006's deeper sweep) and to acknowledge that neither this record nor decision record 0006's re-run above has yet been re-verified against the post-`XCCOMP` design (decision record 0007) — output-stage-side and unlikely to move, per decision record 0013's own analysis, but not yet directly confirmed. **Exception 3** (decision record 0006, bound narrowed by decision record 0007, measured figure re-stated by decision record 0014): the inter-cell net `IN_DRV` (`design/gate_driver_core.sch` — simultaneously the level shifter's output-buffer drain `x1.XMPBUF2`/`x1.XMNBUF2` and the gate of the output stage's first taper inverter `x2.XMP1`/`x2.XMN1`, all thick-oxide and never touching a thin-oxide device) transiently exceeds the same 6.0 V ceiling, again only at the 6 V stretch rail (clearing it by ≥ 397 mV at every nominal-tolerance point). With the `XCCOMP` feedforward compensation capacitor (`x1.ncb` -> `IN_DRV`) now present in `design/level_shifter.sch` — adopted by decision record 0007 and, per decision record 0014, realized as four series `cap_mim_2f0_m4m5_noshield` devices at the DRM-minimum 5.0 µm × 5.0 µm (12.27/13.63/14.99 fF at ff/tt/ss), because `gf180mcuD` fixes the MiM density at 2 fF/µm² and DRM rule MIMTM.8a's 25 µm² minimum MIM area leaves no smaller legal single device — measured worst case narrows to **6.00266 V (margin −2.66 mV)** at `ss_125c_vlogic3p30v-vdrv6p00v` across the 15 affected process×temperature points, `sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md` — a ~56x reduction in the ceiling excess from the uncompensated 6.14833 V / −148.3 mV measured at the same `reltol=1e-4` tolerance (`sim/gate-driver-core-drive/records/20260817-202640-d7bda87.md`). This supersedes decision record 0007's own **6.0003 V / −0.3 mV** figure, which was measured at the pre-issue-#156 `reltol=1e-3` default; of the 2.36 mV difference, decision record 0014's same-tolerance A/B attributes +1.20 mV to that tolerance tightening and +1.16 mV to the device change itself. Bounded at ≤ 10 mV above the ceiling, carrying forward decision record 0006's deck-fidelity caveat (issue #156, unresolved): the harness's default transient tolerances under-resolve this class of narrow coupling excursion, and decision record 0006's own refined-tolerance re-solve of its exploratory 50 fF point moved a harness-convention −0.02 mV figure out to −2.1…−7.2 mV under tighter solver settings; decision record 0007 does not re-run that refined-tolerance analysis for the smaller capacitor adopted here, so this bound covers a similar-magnitude degradation rather than asserting the harness-convention figure as exact. Decision record 0014's re-run *is* at the tightened `reltol=1e-4` default and lands at −2.66 mV, comfortably inside this ≤ 10 mV bound — the bound is met, not relaxed. `XCCOMP` narrows this exception's bound; it does not remove the exception, since `IN_DRV`'s quiescent high level is `VDD_DRV` by construction (zero margin at the 6 V stretch rail regardless of any shaping — decision record 0006's argument, unaffected by decision record 0007). None of the three exceptions invokes the PDK's duty-cycle TDDB overshoot allowance (§2.3, declined each time). See decision records 0003 / 0005 / 0006 / 0007 / 0013 / 0014 for the mitigation attempts investigated and why each claim is scoped this way instead. |

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
