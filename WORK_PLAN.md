# Work Plan

This is a generated roadmap of the current GitHub label state, maintained
automatically by the Guide role's document maintenance phase. Everything
between the markers below is machine-generated and overwritten wholesale on
each update; do not hand-edit that region.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#514**: chore(loom): resync installed Loom to v0.19.1302

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#502**: layout: provenance generator.sha256 stale after #478's generator refactor (signoff CI red on main)

## Important

`loom:important`; taken before unlabelled work.

- **#370**: Track the gap to T1 sim-validated / bronze (graded: 8 of 11, items 5-7 open)
- **#458**: Complete the sim/README.md facet table and fix the stale post-layout row in layout/README.md

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#450**: Share one device-runner driver in harness/campaign.py: three hand-rolled main() copies and a dead write_device_corner_log alias
- **#480**: Promote the generator's private _klt out of gen_gate_driver_core.py: 14 call sites in 3 modules reach it by private name, bypassing klt_env
- **#486**: run_lvs.py and run_pex_extract.py have no --klt flag, so pinning a klt build for an extraction is PATH-only
- **#499**: run_tests.py: flush the per-module == header so it labels its module in captured output
- **#500**: Reconcile docs/ROADMAP.md "Now" list: four of five items are complete
- **#515**: Dedupe hand-written ngspice .control preambles in sim run scripts (device-mv-fet lacks num_threads=1)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#514**: chore(loom): resync installed Loom to v0.19.1302

## Proposed

Issues carrying `loom:curated`.

- **#458**: Complete the sim/README.md facet table and fix the stale post-layout row in layout/README.md *(curated)*
- **#486**: run_lvs.py and run_pex_extract.py have no --klt flag, so pinning a klt build for an extraction is PATH-only *(curated)*
- **#499**: run_tests.py: flush the per-module == header so it labels its module in captured output *(curated)*
- **#500**: Reconcile docs/ROADMAP.md "Now" list: four of five items are complete *(curated)*
- **#502**: layout: provenance generator.sha256 stale after #478's generator refactor (signoff CI red on main) *(curated)*
- **#510**: mk_extracted_dut.py renders the extract report's `file` field as a dict repr in the generated netlist header *(curated)*
- **#511**: verification/signoff hash chain serializes every PR that touches an inventory-listed file (PR #461 conflicted 3x in 12h) *(curated)*

## Proposed (Architect / Hermit)

- **#483**: Route the ronw mismatch runner's private main() onto a shared campaign envelope: 46 of its 101 lines already exist in run_mismatch_main *(hermit)*
- **#487**: Remove parse_netlist(): its MOS-only rationale no longer has a consumer *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 1 |
| Important | 2 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 6 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 1 |
| Curated | 7 |
| Architect / Hermit proposals | 2 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
