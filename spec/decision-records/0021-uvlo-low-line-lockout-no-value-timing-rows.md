# 0021: Bound the `sf_-40c`/`ss_-40c` low-line UVLO lockout — the four rise/fall/propagation rows that produce no value at `vdrv4p50v` are the already-open false trip of decision record 0018, not a new defect

- **Status**: proposed
- **Date**: 2026-10-28
- **Decided by**: Builder agent, issue #378 (draft — **awaiting operator ratification**)
- **Extends**: decision records 0018 (UVLO comparator PVT measurement,
  Finding 2) and 0020 (`ss_-40c` `ipeak_source_a` locked-corner artifact).
  **Does not reopen or amend** either, and **does not close 0018 Finding 2**:
  the false trip stays an open safety item. **Does not relax the ratified
  spec**: no `spec/gate-driver.md` bound changes, and nothing here takes
  effect until the operator ratifies it.

## Context

The item-5 nominal-rail envelope
(`sim/gate-driver-core-drive-with-uvlo/klt/envelopes/20261027-03685aa-klt-sim-nominal-rail.json`,
45 corners, Spot batch fleet) leaves two corners at the low-line point
`vlogic2p97v-vdrv4p50v` with no value for `trise_s`, `tfall_s`, `tpdlh_s` and
`tpdhl_s`: `sf/-40C` and `ss/-40C`. Decision record 0020 excepts only
`ipeak_source_a` at `ss_-40c`. The `sf_-40c` corner has no ratified
exception, and `ss_-40c` has none for its four timing rows.

This is **not a new observation.** Decision record 0018 Finding 2 already
names `sf_-40c` and `ss_-40c` as "the only two of 60 points" of the
full-block grid that lock out at `vdrv4p50v` (`sf_-40c` thresholds: falling
4.526 V, rising 4.876 V), and keeps that as "an open safety item" without a
per-row bound. Decision record 0020 notes `sf_-40c` is "also already locked
at this exact corner". This record supplies the missing per-row bound for
the item-5 rows.

## Finding

Values from the envelope above (both corners ran at `VDD_LOGIC` 2.97 V,
`VDD_DRV` 4.50 V, −40 °C):

| Measurement | `ss/-40C` | `sf/-40C` |
|---|---|---|
| `uvlo_lockout_at_in_high` | 4.49999793 V (= `VDD_DRV`, locked) | 4.49999998 V (locked) |
| `uvlo_vout_at_in_high_v` (`vout_max_v`) | 0.24042 V | 0.33369 V |
| `ipeak_source_a` (≥ 0.5 A) | 0.49944 A — **fail**, covered by 0020 | 0.69450 A — pass |
| `ipeak_sink_a` (≥ 0.5 A) | 0.59515 A — pass | 0.91467 A — pass |
| `trise_s`, `tfall_s` | **no value** (error) | **no value** (error) |
| `tpdlh_s`, `tpdhl_s` | **no value** (error) | **no value** (error) |

The four timing rows have no value because `OUT` never reaches 90 % of the
rail while `IN` is high. The envelope uses rail-normalised 10/50/90 %
crossings, so a block that never switches reports no value rather than a
flattering delay. The 0.69 A source and 0.91 A sink peaks at `sf_-40c` are
the same sub-nanosecond contention transient 0020 describes for `ss_-40c`,
not a sustained drive result.

Scope of the evidence: the 45-point nominal-rail envelope only. The
15-point stretch-rail envelope was not re-examined for this record.

## Decision (proposed)

If ratified, the four timing rows (`trise_s`, `tfall_s`, `tpdlh_s`,
`tpdhl_s`) are **excepted at exactly two corners**, and nowhere else:

- `sf/vsup_drv=4.500_vsup_logic=2.970V/-40C` (`sf_-40c_vlogic2p97v-vdrv4p50v`)
- `ss/vsup_drv=4.500_vsup_logic=2.970V/-40C` (`ss_-40c_vlogic2p97v-vdrv4p50v`)

The exception holds only while the locked signature holds:
`uvlo_lockout_at_in_high` ≈ `VDD_DRV` **and** `uvlo_vout_at_in_high_v` ≤ 0.5 V
(measured 0.240 V and 0.334 V). A corner that unexpectedly switches, or a
locked corner anywhere else, is a new finding. The 0.5 V figure is a
proposed guard, not a measured limit; the operator may choose a different
one.

The exception grants "no value" only. It does not excuse a measured value
that is out of bound, and it does not cover:

- `ipeak_source_a` at `ss_-40c` (0020, bound ≥ 0.45 A, unchanged);
- `ipeak_source_a` and `ipeak_sink_a` at `sf_-40c`, which measure a value
  and pass without any exception;
- `ipeak_sink_a` at `ss_-40c`, which also passes.

Closure is coupled to 0018 Finding 2. A reference-topology revision that
releases these corners makes the exception moot, and the corners must then
produce measured values.

The `ss_-40c` timing rows are included because the same envelope shows the
identical four errors at that corner (also raised on #376). The operator can
strike that corner from the exception without affecting the `sf_-40c` part.

## Alternatives considered

- **Redesign the `x3` reference (multi-diode stack or bandgap)** — not taken
  here. 0018 and 0020 both defer it as a separate piece of work with its own
  record and a full re-verification pass. 0020 also warns a resistor-only
  retune moves every corner's trip point together and could push `sf_-40c`
  or a third corner somewhere worse.
- **Amend 0018 or 0020 directly** — rejected. Ratified records are
  superseded, never rewritten (0020 set that precedent).
- **Cover `sf_-40c` only and leave `ss_-40c` timing rows open** — possible,
  but then the item-5 envelope would still fail on four rows whose cause is
  the same documented lockout. Kept as an operator option above.
- **Ignore the no-value rows** — rejected: an unexplained `error` hides a
  safety finding, and a bound with no guard lets an encoder over-except.

## Consequences

- Nothing changes while this is `proposed`. Item 5 of
  `verification/signoff/README.md` stays `unmet`/`check_failed`. Encoding
  the exception in the `klt sim` requests is issue #376's job and waits for
  ratification.
- If ratified, item 5 can cover these rows per corner, but it still cannot
  reach `met` until 0020's `ipeak_source_a` exception is also encoded and
  the 0016 stretch-rail sink exception is encoded.
- The false-trip lockout remains open: at `vdrv4p50v` two corners fail to
  drive `OUT` at all. This record bounds how the verification reports it. It
  is not a claim the block works there.
- Bad consequence: a ratified exception makes two corners stop failing the
  item-5 envelope even though the block cannot drive its load there. The
  locked-signature guard is what keeps that from widening.
