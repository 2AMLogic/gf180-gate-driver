# Work Plan

This is a generated roadmap of the current GitHub label state, maintained
automatically by the Guide role's document maintenance phase. Everything
between the markers below is machine-generated and overwritten wholesale on
each update; do not hand-edit that region.

<!-- guide:plan-body:start -->
_Generated: 2026-11-20T18:51:47Z (snapshot; compare against live labels)_
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#370**: Track the gap to T1 sim-validated / bronze (graded: 8 of 11, items 5-7 open)

## Ready

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

- **#556**: UVLO Vbe/dVbe reference: startup-path verification and layout cost estimate (decision record 0024 adoption gates 3 and 4)

## In Progress

Issues currently being built (`loom:building`).

- **#560**: Generate nominal and stretch fleet requests for both post-layout drive benches

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#510**: mk_extracted_dut.py renders the extract report's `file` field as a dict repr in the generated netlist header *(curated)* *(held)*
- **#555**: UVLO Vbe/dVbe reference: PDK-resistor re-measurement and local-mismatch Monte Carlo over the 15 corners (DR-0024 adoption gates 2 and 1) *(curated)*
- **#556**: UVLO Vbe/dVbe reference: startup-path verification and layout cost estimate (decision record 0024 adoption gates 3 and 4) *(curated)*
- **#557**: T1 item 7: re-run klt pex on a current klt and attribute the layout-induced stretch sink-current miss (ss / 27 C, 0.9996 A vs >= 1 A) *(curated)*
- **#559**: Qualify the oxide-safety fleet run against both extracted DUT baselines *(curated)*
- **#560**: Generate nominal and stretch fleet requests for both post-layout drive benches *(curated)*

## Proposed (Architect / Hermit)

- **#487**: Remove parse_netlist(): its MOS-only rationale no longer has a consumer *(hermit)* *(held)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 1 |
| Ready (`loom:issue`, net of holds/building/merge-pending) | 1 |
| In Progress (`loom:building`) | 1 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 6 |
| Architect / Hermit proposals | 1 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
