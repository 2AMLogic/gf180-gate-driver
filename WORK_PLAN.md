# Work Plan

This is a generated roadmap of the current GitHub label state, maintained
automatically by the Guide role's document maintenance phase. Everything
between the markers below is machine-generated and overwritten wholesale on
each update; do not hand-edit that region.

<!-- guide:plan-body:start -->
_Generated: 2026-11-23T14:45:00Z (snapshot; compare against live labels)_
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#370**: Track the gap to T1 sim-validated / bronze (graded: 8 of 11, items 5-7 open)
- **#557**: T1 item 7: re-run klt pex on a current klt and attribute the layout-induced stretch sink-current miss (ss / 27 C, 0.9996 A vs >= 1 A)

## Ready

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

- **#557**: T1 item 7: re-run klt pex on a current klt and attribute the layout-induced stretch sink-current miss (ss / 27 C, 0.9996 A vs >= 1 A)

## In Progress

Issues currently being built (`loom:building`).

- **#510**: mk_extracted_dut.py renders the extract report's `file` field as a dict repr in the generated netlist header
- **#567**: uvlo-reference-study: state that the quoted klt yield figures are conditional on value-producing draws
- **#569**: DR-0026 cites DR-0025's per-corner trip sigma as 0.48-0.57 V; the measured value is 0.471-0.570 V

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#572**: uvlo-reference-study: state that the quoted klt yield figures are conditional on value-producing draws
- **#583**: DR-0026 cites DR-0025's per-corner trip sigma as 0.48-0.57 V; the measured value is 0.471-0.570 V

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#510**: mk_extracted_dut.py renders the extract report's `file` field as a dict repr in the generated netlist header *(curated)*
- **#567**: uvlo-reference-study: state that the quoted klt yield figures are conditional on value-producing draws *(curated)*
- **#569**: DR-0026 cites DR-0025's per-corner trip sigma as 0.48-0.57 V; the measured value is 0.471-0.570 V *(curated)*

## Proposed (Architect / Hermit)

- **#570**: Let pip resolve the pinned signoff grader’s dependencies *(hermit)* *(held)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`, net of holds/building/merge-pending) | 1 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 2 |
| Approved PRs awaiting merge | 0 |
| Curated | 3 |
| Architect / Hermit proposals | 1 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
