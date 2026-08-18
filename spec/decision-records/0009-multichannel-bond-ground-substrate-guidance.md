# 0009: Multi-channel low-side power-NMOS facet — bond wire, ground return, and substrate-noise guidance

- **Status**: Ratified (guidance only — no new `sim/` campaign, no amendment to
  any parameter already ratified in `spec/gate-driver.md` or decision record
  0001; see "Consequences" for what remains open).
- **Date**: 2026-08-18
- **Decided by**: Builder agent, issue #181
- **Extends**: [decision record
  0008](0008-low-side-power-nmos-facet-scope-and-ronw-baseline.md) (which
  scoped the low-side on-die power-NMOS facet into this repo and filed this
  issue as one of three follow-ons) and, by explicit extension, [decision
  record 0001](0001-block-interface-and-uvlo-parameters.md) Decision 1 (the
  `GND_LOGIC`/`GND_DRV` split) and Decision 5 (the UVLO response-time
  budget), neither of which this record amends — both are single-channel
  decisions this record extends to the N-channel case, per the reasoning
  below.
- **Format note**: like 0001, this record covers three decisions (bond wire
  sizing, ground return topology, substrate noise) that are only meaningful
  read together — they are three views of the same system-level question
  ("what does going from one switching channel to N sharing one die/package
  do to the return-path and reference-noise budget 0001 already set?") — so
  this record follows 0001's precedent of departing from `TEMPLATE.md`'s
  one-decision-per-file convention rather than scattering three
  cross-referencing files. Future single-decision records in this directory
  should still use `TEMPLATE.md` directly.

## Context

Decision record 0008 scoped a second facet into this repo — direct low-side
drive of a small load (motor/solenoid/LED) from a single Li-ion cell, using
an on-die `nfet_06v0` switch at logic-level `Vgs`, generic to N channels of
~1 A drive sharing one die/package — and explicitly deferred three
system-level questions that only arise once more than one channel shares a
die: bond wire count/sizing, ground return topology, and substrate-noise
coupling into this repo's existing co-integrated analog (the UVLO comparator
of decision record 0001). This record answers those three questions with
guidance sourced to gf180mcu PDK documentation where the PDK publishes
relevant data, and to explicitly-labeled industry-standard bonding practice
where it does not — per issue #181's own instruction not to invent a number
presented as PDK-sourced.

**What decision record 0001 already established, that this record extends
rather than revisits.** 0001 Decision 1 splits a single low-side channel's
ground into two pins — `GND_LOGIC` (return for `VDD_LOGIC` and reference for
`IN`) and `GND_DRV` (return for `VDD_DRV` and for `OUT`'s switching
current) — both the same electrical node by design, physically separated
"to keep `OUT`'s high-dI/dt switching return off the `IN` comparator's
reference path," with the explicit consequence that the two pins "must be
tied together with minimal impedance close to the device (star point)."
0001 Decision 5 sets the UVLO comparator's response-time budget (design
target < 500 ns from the rail crossing its falling threshold to `OUT`
reaching its safe low state) and states its reference is a diode-connected
`nfet_06v0`-corner `VT0` level compared against a `VDD_DRV` divider — a
device-`Vt`-referenced comparator, not a bandgap, because "no bandgap exists
in this block." Both of those decisions were reasoned for exactly **one**
switching channel. N channels multiply the same bounce mechanism 0001
already reasoned about, which is why this record treats them as an
extension of 0001's pattern rather than a new problem.

**What the PDK documentation says, and does not say, about bond wire
current capacity.** Per [DRM §9.0, Bond
Pad](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_09.html)
(fetched 2026-08-18, quoted verbatim): *"Bond pad size and pitch are limited
by assembly house... Wafer sort and assembly capabilities may impose
additional constraints. It is the customer's responsibility to take these
additional constraints into consideration during layout."* The DRM's §9.1–9.4
subsections (Bond Pad Rules, Bond Pad Guidelines, Circuit-Under-Pad Rules,
Solder Bumping Guidelines) constrain pad **geometry** (opening size, metal
stack, pitch) for DRC purposes — none of them publish a per-wire or
per-pad **current** rating. The PDK's only current-density guidance is
on-die: [DRM §14.2, Electro-migration, Table 14.3 (Maximum Line Current
Density per Drawn Width) and Table 14.4 (Maximum Contact/Via
Current)](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_2.html)
(fetched 2026-08-18), which bound on-die metal/via/contact current density
at 85/110/125 °C junction temperature — e.g. MetalTop (30 kÅ thick)
unidirectional 16.52 mA/µm at 85 °C, down to 5.37 mA/µm at 125 °C — but this
governs the routing from a device to a bond pad, not the wire from the pad
to the package lead frame. **Bond wire current capacity is therefore an
assembly-house parameter, not a gf180mcu PDK-published figure**, exactly as
issue #181 anticipated it might be — this record cites standard industry
bonding practice for that number instead of inventing a PDK citation that
does not exist.

## Decision 1 — Bond wire count/sizing per channel

**Reference data used below** (industry-standard bonding practice, **not**
gf180mcu-PDK-sourced, per the citation gap above): a widely used
first-order design heuristic in wire-bonding/packaging practice for
standard ball/wedge-bonded gold or aluminum wire is approximately **1 A of
steady-state current-carrying capacity per mil (25 µm) of wire diameter**,
before self-heating (a function of wire length, still-air vs. molded
ambient, and duty cycle) becomes the limiting factor rather than
electromigration — this figure recurs across assembly-house application
notes and wire-bonding process texts as a conservative rule of thumb for
continuous DC current, not a datasheet-grade rating; it is cited here in
that spirit, with a stated derating margin below.

| | |
|---|---|
| Options considered | (a) size one bond wire per channel exactly at the ~1 A/mil heuristic's rated point (minimum wire count); (b) derate to roughly half the heuristic's rated current per wire (≥2× margin) and/or use redundant parallel wires per high-current node; (c) leave wire count/gauge entirely to the assembly house's own design rules at tape-out, stating no guidance here. |
| Trade-offs | (a) minimizes wire count and pad count but runs each channel's supply/return wire at the heuristic's own rated point with no margin for the heuristic's own stated sensitivity to wire length, ambient, and duty cycle — a bare-rule-of-thumb design point is not the same as a qualified/characterized rating, and this facet's load current (motor/solenoid/LED) is not guaranteed to be a clean DC value (motor inrush and solenoid pull-in both exceed steady-state current transiently). (c) matches decision record 0008's own conservative posture (not inventing numbers this repo cannot cite) but fails issue #181's explicit acceptance criterion to state a wire-count/gauge recommendation. (b) keeps a stated, reproducible design point while carrying margin against the heuristic's own caveats and against inrush/pull-in transients this facet's load types are known to produce. |
| Chosen | (b) — derate to ≈0.5 A per standard 1 mil (25 µm) bond wire as this record's working design point (2× margin under the ~1 A/mil heuristic), and recommend **one dedicated bond wire per channel for `VDD_DRV`/cell-supply and one dedicated bond wire per channel for that channel's `GND_DRV` return** at the ~1 A/channel target current, i.e. 2 wires/channel minimum at the target current, scaling to more wires or a heavier wire gauge if the stretch load current or assembly house's own rated gauge differs from the 1 mil reference point assumed here. |
| Rationale | 0.5 A/wire at ~1 A/channel means the minimum viable count (1 supply + 1 return wire per channel) already sits at the derated design point with no further margin measures needed for the ~1 A/channel target current stated in decision record 0008's framing; if a given design's actual load current is closer to the facet's stretch range, add a second parallel wire per rail rather than exceeding the 0.5 A/wire design point. This is stated as **this record's own conservative design point**, not a gf180mcu PDK figure — the assembly house's actual qualified bond-diagram rules (wire gauge, span length, bond-pad pitch) govern at tape-out and may differ; this number exists so a first-pass bond diagram and pad count can be planned before that assembly-house engagement happens, consistent with 0008's own posture of providing a starting point rather than a final number. |

### N = 1, 2, 4 channels at ~1 A/channel

| N (channels) | Dedicated `VDD_DRV`/cell-supply wires | Dedicated `GND_DRV` return wires (see Decision 2) | Notes |
|---|---|---|---|
| 1 | 1 (shared supply node — nothing to split) | 1 | Degenerates to 0001's existing single-channel `GND_DRV` pin exactly (see "Consequences"). |
| 2 | 1 shared `VDD_DRV`/cell-supply wire is acceptable if the two channels' combined inrush is bounded (motor/solenoid inrush budgeted below 1 A/wire aggregate is a per-design check, not assumed here) — 2 wires recommended if inrush margin is not separately verified | 2 (one per channel — see Decision 2, not shared) | Supply-side sharing is lower-risk than return-side sharing: `VDD_DRV` is a single low-impedance node upstream of each channel's own switch, not a shared return carrying the sum of independently-timed switching edges. |
| 4 | 2 (parallel wires on the shared supply node, sized for the combined ~4 A worst case at the 0.5 A/wire design point) | 4 (one per channel — see Decision 2) | Supply-side wire count scales with combined current per the same 0.5 A/wire design point; return-side count scales with channel count per Decision 2, not combined current, because the point of per-channel return is noise segregation, not just current capacity. |

## Decision 2 — Ground return topology

| | |
|---|---|
| Options considered | (a) all N channels share a single `GND_DRV` return, as if N channels were just a wider version of 0001's single-channel output stage; (b) each channel gets its own dedicated `GND_DRV_n` return, extending 0001's single-channel `GND_LOGIC`/`GND_DRV` split to N instances of the drive-side domain rather than inventing a third domain type; (c) a fully isolated/floating return per channel (separate substrate or isolated ground network per channel). |
| Trade-offs | (a) reuses 0001's existing two-pin scheme unchanged but multiplies its own already-identified bounce risk: 0001 split `GND_DRV` off `GND_LOGIC` specifically because a single channel's high-dI/dt switching edge on a shared return couples into the comparator's reference path; with N **independently and asynchronously** switching channels sharing one `GND_DRV` return, each channel's edge now also couples into every *other* channel's `OUT` node through the shared return impedance — a second, channel-to-channel bounce mechanism 0001 never had to consider, on top of the original drive-to-logic bounce mechanism 0001 already mitigated. (c) fully isolated returns would eliminate both bounce mechanisms but requires either N separate substrate/DNWELL islands (contradicting `gate-driver.md` §2.4's DNWELL rule, which already constrains one design's logic/drive split to two regions, not N+1) or N independent package-level ground planes, which is unjustified complexity and cost for a single-die, single-package multi-channel facet with no isolation requirement in scope anywhere in this repo's ratified spec. (b) gets the noise-segregation benefit of (c) for the drive-side return specifically — the mechanism 0001's own rationale already targets — without inventing new isolation infrastructure: it is literally N copies of the pin 0001 already defined, converging at the same physical star point 0001 already requires. |
| Chosen | (b) — each channel gets its own dedicated `GND_DRV_n` bond wire/pin (one drive-return wire per channel, per Decision 1's table), all of which — together with the single shared `GND_LOGIC` — remain the same electrical node by design intent and must be tied together with minimal impedance at a single star point, exactly as 0001 Decision 1 already requires for the two-pin case. `GND_LOGIC` itself is **not** split per channel: it carries no switching current (0001's own framing — it is "return for `VDD_LOGIC` and reference for `IN`"), so there is nothing for splitting it to protect against; the N-channel case needs N instances of the drive-side domain, not a new domain type. |
| Rationale | This directly answers the issue's own framing question — "does the N-channel case need a third return domain, or does splitting `GND_DRV` per channel suffice?" — with: splitting `GND_DRV` per channel suffices; no third domain is needed. Each channel's own switching-current return is kept off both the shared logic-comparator reference (0001's original concern) and off every other channel's drive return (the new N-channel concern), for the same reason 0001 already gave: segregating a high-dI/dt power return from a sensitive/other reference path is standard gate-driver-IC practice, and this is simply that practice applied per-channel instead of applied once. **N = 1 degenerates cleanly**: with one channel, `GND_DRV_1` is `GND_DRV`, and this decision is textually identical to 0001 Decision 1 — no discontinuity between the single-channel spec and this record's N-channel extension of it. |

## Decision 3 — Substrate noise coupling into the UVLO comparator/analog reference

| | |
|---|---|
| Options considered | (a) treat substrate coupling as adequately covered by the existing DNWELL guard-ring rule (`gate-driver.md` §2.4) and 0001's ground-return segregation (Decision 2 above), with no additional guidance; (b) give N channels' UVLO/analog structures their own dedicated local substrate tap/guard ring referenced to the quiet `GND_LOGIC` domain, distinct from any `GND_DRV_n` domain, and flag the magnitude question (does a coupled transient actually false-trip the comparator) as unresolved without a transistor-level sim; (c) require a transistor-level substrate-coupling sim before this record can be ratified. |
| Trade-offs | (a) is the cheapest option but is not actually justified by what §2.4 and Decision 2 cover: §2.4's DNWELL rule keeps the 3.3 V logic devices and 5 V/6 V drive devices in separate DNWELL regions for gate-oxide/HCI reasons, not for substrate-noise isolation, and neither §2.4 nor Decision 2 says anything about where the UVLO comparator's own substrate tap sits relative to N switching channels' bulk-current injection — silently assuming it's covered would be exactly the kind of invented-but-unstated margin issue #181 was filed to avoid. (c) is the most rigorous answer but issue #181's own guidance explicitly says a quantitative sim is a stretch goal, not a blocker, for this record — requiring it here would leave the qualitative guidance (which the issue does require) undelivered while waiting on work that isn't scoped to this issue. (b) delivers the qualitative treatment the issue's acceptance criteria actually ask for, states an actionable layout rule extending the segregation principle already established, and explicitly flags the one question that genuinely needs simulation rather than glossing over it. |
| Chosen | (b). **Coupling mechanism**: each channel's `nfet_06v0` switching edge (~1 A, edge duration on the order of the propagation-delay target in `gate-driver.md` §3, i.e. tens of ns) injects a transient bulk/substrate current through the device's drain-body and source-body junction capacitance and through any resistive substrate/well-tap path back to the return network — this is a well-understood mechanism in any shared-substrate power-switching design, not specific to this PDK. With N independently and asynchronously switching channels, the **event rate** of substrate transients scales with N × switching frequency, but each individual event's magnitude is set by one channel's own ~1 A edge, not by N (channels switching in near-synchrony would be the worst case for combined magnitude, and should be treated as the design's worst-case assumption rather than assumed away). **Layout guidance**: the UVLO comparator and any other analog reference structures should receive their own local substrate/well tap and guard ring referenced to the quiet `GND_LOGIC` domain — not to any `GND_DRV_n` domain — extending Decision 2's segregation principle from the *return-wire* level down to the *substrate-tap* level, since a comparator whose own local substrate potential is tied near a switching channel's return would defeat Decision 2's segregation at the return-wire level by reintroducing the coupling through the substrate directly underneath it. |
| Rationale | This is the direct extension of 0001 Decision 1's own logic (segregate high-dI/dt return from sensitive comparator reference) to the coupling path 0001 didn't have to consider with only one channel and no stated multi-channel context: substrate current injection is a second physical path for the same bounce mechanism 0001 already named as its reason for splitting `GND_LOGIC`/`GND_DRV`, and it is not closed by a ground-wire-level fix alone. |

### Does 0001 §5's UVLO response-time budget have margin against this?

**Qualitatively, yes on the time axis, but the magnitude question is
explicitly left open, not resolved, here.** 0001 Decision 5's design target
is < 500 ns from the rail crossing its falling threshold to `OUT` reaching
its safe low state; a substrate-coupled transient from a single channel's
switching edge lasts on the order of that channel's own edge time (tens of
ns, per `gate-driver.md` §3's < 50 ns propagation-delay target), i.e.
roughly an order of magnitude shorter than the UVLO response budget — so a
transient that is too brief to be read as a sustained undervoltage
condition should not, by duration alone, consume the 500 ns budget's margin.
However, **this only bounds duration, not whether the comparator's binary
output glitches at all during that brief window**: 0001 Decision 5's
reference is a diode-connected `nfet_06v0`-corner `VT0` level with no
bandgap, and 0001 Decision 4's own rationale already accepts a wide PVT
spread (0.61–0.85 V `VT0`) "as part of the hysteresis budget" — but that
budget was sized against process/temperature spread and slow supply
transients, not against a fast substrate-coupled disturbance on the
comparator's own local reference node, which is a different noise source
the 300 mV hysteresis band (0001 Decision 4) was not explicitly evaluated
against. **This record does not claim the hysteresis margin is or is not
sufficient against that specific noise source** — resolving it requires a
transistor-level substrate-coupling simulation of the actual comparator
implementation (not yet designed), which issue #181 explicitly scopes as a
stretch goal / separate follow-on, not a blocker for this record. It is
recorded here as an **open item**, not a silently-assumed-safe margin,
consistent with 0001's own convention of explicitly flagging open items
(e.g. `VDD_LOGIC` undervoltage, per 0001 Decision 2/5) rather than glossing
over them.

## Alternatives considered

- **Fold this guidance into `spec/low-side-power-switch.md` instead of a
  standalone decision record** — considered and rejected for now: as of this
  record's date (2026-08-18), issue #179 (which would create that file) had
  not yet landed on `origin/main` (confirmed by checking `origin/main` at
  worktree creation time — highest existing decision-record number was
  0008, and `spec/low-side-power-switch.md` does not exist on `origin/main`).
  Per the issue's own instruction ("this issue does not need to wait for
  that file to exist"), this record lands standalone at number 0009 rather
  than blocking on #179's landing order; if #179 lands `spec/low-side-power-
  switch.md` later, that document can reference this record the same way
  `gate-driver.md` references decision record 0001, without requiring this
  record's content to move.
- **State a single, unqualified bond-wire current number sourced to the
  gf180mcu PDK** — rejected: the PDK does not publish one (§9.0's own text,
  quoted above, explicitly delegates this to the assembly house), and
  presenting an invented number as PDK-sourced is exactly what issue #181's
  acceptance criteria warn against.
- **Require a quantitative substrate-coupling sim before ratifying this
  record** — rejected per issue #181's own guidance, which frames this as a
  stretch goal, not a blocker; see Decision 3's "open item" framing above
  instead of a deferred-ratification approach.

## Consequences

- `spec/README.md` gains an index entry for this record.
- **N = 1 degenerates cleanly to 0001**: Decision 2 above is textually
  identical to 0001 Decision 1 when N = 1 (`GND_DRV_1` = `GND_DRV`), and
  Decision 1's bond-wire table's N = 1 row matches a conventional
  single-channel gate-driver bond diagram (one supply wire, one dedicated
  drive-return wire) — this record does not change anything about the
  already-ratified single-channel spec (`gate-driver.md`, decision record
  0001); it only extends guidance to N > 1, which was previously unstated.
- **Open item, not resolved here**: whether a substrate-coupled transient
  from channel switching can glitch the UVLO comparator's binary output
  within 0001 Decision 5's hysteresis margin is left open (Decision 3
  above), pending a transistor-level sim of the actual comparator
  implementation. This is recorded as a known gap for whichever future
  issue designs and simulates that comparator (a natural continuation of
  `spec/low-side-power-switch.md`'s eventual OCP/thermal-sense structures,
  per decision record 0008's Consequences list referencing #179), not as a
  blocker for this record's own guidance, per issue #181's explicit
  "stretch goal, not a blocker" framing.
- **Bond wire and ground-return guidance is a starting design point, not an
  assembly-qualified rating**: Decision 1's ~0.5 A/wire figure is this
  record's own conservative derating of a general industry heuristic, not a
  gf180mcu-PDK-published number (§9.0 explicitly does not publish one) — the
  actual wire gauge, span, and bond-pad pitch remain the assembly house's
  design-rule responsibility at tape-out, per DRM §9.0's own text quoted in
  "Context" above. A future test-structure/tape-out issue (e.g. a successor
  to #180, which decision record 0008 already notes is blocked on #179) must
  reconcile this record's design point against the actual assembly house's
  bond diagram rules once a shuttle/package is selected, not treat this
  record's numbers as final.
- No existing `sim/` record or ratified spec parameter is edited or
  superseded by this record — it is additive guidance for a facet
  (`spec/low-side-power-switch.md`, not yet written) that does not yet exist
  as ratified spec content.
