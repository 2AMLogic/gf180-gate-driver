# Work Plan

This is a generated roadmap of the current GitHub label state, maintained
automatically by the Guide role's document maintenance phase. Everything
between the markers below is machine-generated and overwritten wholesale on
each update; do not hand-edit that region.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#370**: Track the gap to T1 sim-validated / bronze (graded: 8 of 11, items 5-7 open)
- **#456**: Regenerate the extracted netlists from the current GDS and re-run the oxide-safety post-layout facet
- **#458**: Complete the sim/README.md facet table and fix the stale post-layout row in layout/README.md

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#477**: sim/mc_to_yield.py re-types the ratified gate ceiling and both exception bounds now that script_helpers.py is their one home
- **#492**: layout/README.md pinning section tells agents to run `uv tool install`, which the fleet host rules forbid

## In Progress

Issues currently being built (`loom:building`).

- **#449**: Remove sim/harness/report.py write_record(): dead bootstrap path that bypasses the evidence store
- **#450**: Share one device-runner driver in harness/campaign.py: three hand-rolled main() copies and a dead write_device_corner_log alias
- **#451**: Route the two hand-rolled klt draw calls through klt_report.run_klt: both ignore the resolved klt binary
- **#456**: Regenerate the extracted netlists from the current GDS and re-run the oxide-safety post-layout facet
- **#458**: Complete the sim/README.md facet table and fix the stale post-layout row in layout/README.md
- **#460**: Share the mismatch Statistical-convention head (4 copies) and route ronw through convention_tail: its inline tail drops the control's defining property
- **#467**: power_array_folded keeps three duplicate copies of the generator's shape helpers: one drops _rect's rounding, and _vbar's argument order is swapped
- **#468**: Share the negative-control pass/fail epilogue: 4 copies in layout/, already drifted in loop placement
- **#472**: Collapse run_klt_report onto run_klt: duplicated failure block, and the --format text leg's exit code is discarded into committed evidence
- **#479**: Disambiguate the two sim-harness fmt() helpers: one name, two incompatible number formats
- **#482**: Make npm test run the test suite, or remove it: it runs sim/run_corners.py --list and exits 0 having run zero tests

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#473**: refactor(layout): check both klt report legs through one failure block
- **#478**: refactor: route power_array_folded's shape helpers through the generator's
- **#484**: refactor(sim): drop unused write_record() record writer from report.py
- **#493**: fix: make npm test run the tracked test suite instead of printing the sim catalogue
- **#494**: refactor: rename the two colliding sim-harness fmt() formatters to fixed() and sigfig()
- **#496**: refactor(sim): share the mismatch Statistical-convention head via campaign.convention_head and route ronw through convention_tail

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#456**: Regenerate the extracted netlists from the current GDS and re-run the oxide-safety post-layout facet *(curated)*
- **#458**: Complete the sim/README.md facet table and fix the stale post-layout row in layout/README.md *(curated)*
- **#459**: ronw mismatch runner keeps two inline copies the shared campaign helpers already cover (ERROR verdict line, context-table loop) *(curated)*
- **#464**: Wire up montecarlo.py's MISMATCH_FAMILIES into the record prose that re-types the same six wrapper names *(curated)*
- **#477**: sim/mc_to_yield.py re-types the ratified gate ceiling and both exception bounds now that script_helpers.py is their one home *(curated)*
- **#486**: run_lvs.py and run_pex_extract.py have no --klt flag, so pinning a klt build for an extraction is PATH-only *(curated)*
- **#492**: layout/README.md pinning section tells agents to run `uv tool install`, which the fleet host rules forbid *(curated)*

## Proposed (Architect / Hermit)

- **#480**: Promote the generator's private _klt out of gen_gate_driver_core.py: 14 call sites in 3 modules reach it by private name, bypassing klt_env *(hermit)*
- **#483**: Route the ronw mismatch runner's private main() onto a shared campaign envelope: 46 of its 101 lines already exist in run_mismatch_main *(hermit)*
- **#487**: Remove parse_netlist(): its MOS-only rationale no longer has a consumer *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 3 |
| Ready (`loom:issue`) | 2 |
| In Progress (`loom:building`) | 11 |
| PRs awaiting review | 6 |
| Approved PRs awaiting merge | 0 |
| Curated | 7 |
| Architect / Hermit proposals | 3 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
