# Roadmap

gf180-gate-driver is a high-voltage gate driver (3.3 V logic in, 5 V drive
rail, 6 V stretch) on the gf180mcu open PDK, and the first block in its family
to exercise the medium-voltage devices with klayout-tools (`klt`), xschem and
ngspice.

Status as of 2026-11-13, `main` @ `4013fd1`.

Live label state is in [`WORK_PLAN.md`](../WORK_PLAN.md). The verdict of record is
[`verification/signoff/tier-report.json`](../verification/signoff/tier-report.json), which wins over this file.

## Where it stands

Facet (a), the gate driver (`spec/gate-driver.md`, ratified 2026-08-05):

- Schematic, PVT simulation, layout, DRC, LVS, ERC and post-layout records are
  committed. `layout/gate_driver_core.gds` is LVS `match` and DRC `clean` under
  the current curated deck (#362). That deck models no `_MV` rules, so this is
  not a medium-voltage signoff.
- Graded gap to T1 (tracker #370): **9 of 11 items met, tier `null`**.

| Item | Grade | What holds it |
|---|---|---|
| 1 Design sources, 2 Layout, 3 DRC, 4 LVS | met | |
| 5 Full corner verification | unmet, `check_failed` | 8 of 11 `klt sim` envelopes pass. The UVLO trip envelope passes 4 of 15 corners (decision record 0018), and two envelopes each carry one UVLO-locked corner whose four timing rows produce no value. |
| 6 Monte Carlo | met | four `klt yield` reports (decision record 0021 ratified) |
| 7 Post-layout verification | unmet, `check_failed` | `klt pex` on the current GDS: 408 of 420 delta rows pass, 4 fail, 8 error. Only one failure is introduced by layout (stretch `ipeak_sink_a`, ss / 27 C: 1.0170 A schematic, 0.9996 A extracted). |
| 8 Characterization, 9 Testbenches, 10 Hygiene, 11 Power delivery | met | |

  What each `met` claims: [`verification/signoff/README.md`](../verification/signoff/README.md).
- Two ratified, bounded exceptions stay in force (decision records 0016 and
  0020). Two decision records are `proposed` and not ratified: 0022 (bounds the
  no-value timing rows at the locked corners) and 0023 (a 3-diode stacked UVLO
  reference, measured, 2 of 15 corners pass, recommended against).
- The open design finding is the UVLO: falling trip 2.23 to 4.74 V against a
  3.3 to 3.9 V band, and `ss` / -40 C stays locked out at the legitimate 4.5 V
  low-line rail (decision record 0018 Finding 2).

Facet (b), the low-side on-die power switch (`spec/low-side-power-switch.md`):
spec and test-structure plan ratified (decision records 0010, 0011, 0012);
`Ron·W` characterized across PVT with Monte Carlo evidence. No schematic,
layout or testbench exists for the OCP, thermal-sense or flyback structures.

Since tracker #370 was filed, item 6 moved to `met` and items 5 and 7 from `no_evidence` to `check_failed`.

## Now

Can start today; each is one PR.

1. **Ron·W mismatch runner writes an ERROR record when no draw converges**
   (#446). Done when the `error` fixture scenario renders a complete record and
   its golden is committed, as the three sibling runners already do.
2. **indrv mismatch runner discloses partial reference coverage** (#447). Done
   when a partial cross-check (`0 < compared < total`) no longer emits the
   ngspice-version Finding without stating its coverage, with a fixture test.
3. **Regenerate the extracted netlists from the current GDS and re-run the
   oxide-safety post-layout facet.** `layout/lvs/gate_driver_core.extracted.spice`
   and `.extracted-rc.spice` were last committed on 2026-08-26; the GDS changed
   on 2026-10-24 (#362). The `klt pex` report covers the drive suite on the
   current GDS, but `sim/level-shifter-oxide-safety-postlayout/` has no record
   on it. Done when both netlists are regenerated with
   `layout/lvs/run_pex_extract.py` and a new append-only record exists for
   that facet (no-RC and RC). No issue yet.
4. **Second UVLO reference study: a reference that does not track `Vgs`.**
   Decision record 0023's stated follow-up. Schematic-only candidate under
   `sim/uvlo-reference-study/`, same ramp, bounds and 15 corners as decision
   record 0018. Done when the envelope and a per-corner table are committed and
   the README states pass count, trip spread, worst-case rising trip against
   the 4.50 V floor, and supply current. No change to `design/`. No issue yet.
5. **Complete the reproduction index.** `sim/README.md`'s facet table omits
   four on-disk experiments, and `layout/README.md`'s "Post-layout simulation"
   status row is stale; both are disclosed as known gaps in the root README.
   Done when both are corrected, the root README's disclosure is removed, and
   the item-10 inventory, envelope, manifest and tier report are refreshed so
   `npm run signoff:check` passes. No issue yet.

## Next

- **Attribute the one layout-induced item-7 failure.** After Now 3: run
  stretch ss / 27 C on the schematic, the no-RC extraction and the RC
  extraction, and split the 1.71 % sink-current loss between wiring RC and
  the schematic's ideal bias resistors against the layout's 271 `ppolyf_u`
  units (item 7 note (b), "not checked"). Done when a committed note names the
  dominant contributor; a layout fix or decision record follows from it.
- **Re-check the `klt pex` `model_mismatch` reference tally.** The cause was
  filed as klayout-tools#4630, now closed. Done when a `klt pex` run with a
  build containing that fix is committed as a new append-only report and the
  item-7 note records whether the reference side is populated.
- **UVLO redesign.** After Now 4 produces a candidate that holds the trip band
  over 15 corners: a decision record proposing the topology change, then
  schematic, layout, DRC/LVS and post-layout re-verification. This is the only
  route that closes decision record 0018 Finding 2 rather than bounding it.

## Later

- **Facet (b) test structures** (decision record 0012): schematic capture and
  testbenches for the reduced-scale reference channel, OCP comparator,
  thermal sense and flyback variants. First question: how to split it into
  one-PR issues, and which of the six open items in
  `spec/low-side-power-switch.md` §6 comes first.
- **Medium-voltage DRC coverage.** The curated deck has no `_MV` rules. First
  question: which `_MV` rules the upstream deck can express, to be filed
  against klayout-tools as a generic tool gap.
- **Measured silicon** (`measurements/`). First question: which structures a
  shared-shuttle slot would carry.

## Blocked and waiting

- **Decision record 0022** has been `proposed` since 2026-10-28 and awaits
  operator ratification. Ratifying and encoding it clears the no-value timing
  rows of item 5. It does **not** by itself make item 5 `met`: the UVLO trip
  envelope still fails 11 of 15 corners. Decision record 0023 also awaits
  ratification (it adopts no change).
- **Whether item 7 adopts the item-5 exception shards** (decision records 0016
  and 0020 applied to the extracted leg) is recorded as an open
  spec/verification question in
  `sim/gate-driver-core-drive-with-uvlo/klt/pex/gen_pex_requests.py`. Three of
  the four item-7 failures sit at exactly those corners.
- **Chipalooza Challenge #5 proposal**
  ([`docs/chipalooza/challenge-5-proposal.md`](chipalooza/challenge-5-proposal.md))
  is written; submitting it is an operator action.
- Neither unmet T1 item can reach `met` by agent work alone today; the Now
  list is evidence, tooling and documentation work around that gap.

## Not planned

- A CAN transceiver (rejected; see `CLAUDE.md`), or a high-side or half-bridge
  configuration (the ratified spec is low-side only).
- Relaxing a ratified bound to make a row pass. Failing corners keep reporting
  FAIL until the design changes or a decision record is ratified.
