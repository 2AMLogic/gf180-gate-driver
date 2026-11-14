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

- **#470**: bug: erc_negative_control's deck-clean arm grades 'violations' on main under klt 0.9.2 — the ERC control fails closed

## Important

`loom:important`; taken before unlabelled work.

- **#370**: Track the gap to T1 sim-validated / bronze (graded: 8 of 11, items 5-7 open)
- **#456**: Regenerate the extracted netlists from the current GDS and re-run the oxide-safety post-layout facet
- **#463**: T1 item-2 GDS reproducibility attestation no longer holds under the host klt (0.9.2 renames generated sub-cells)

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#449**: Remove sim/harness/report.py write_record(): dead bootstrap path that bypasses the evidence store
- **#456**: Regenerate the extracted netlists from the current GDS and re-run the oxide-safety post-layout facet
- **#458**: Complete the sim/README.md facet table and fix the stale post-layout row in layout/README.md
- **#460**: Share the mismatch Statistical-convention head (4 copies) and route ronw through convention_tail: its inline tail drops the control's defining property

## In Progress

Issues currently being built (`loom:building`).

- **#447**: indrv mismatch runner's ngspice-version Finding is emitted from a partial reference cross-check without disclosing coverage
- **#450**: Share one device-runner driver in harness/campaign.py: three hand-rolled main() copies and a dead write_device_corner_log alias
- **#451**: Route the two hand-rolled klt draw calls through klt_report.run_klt: both ignore the resolved klt binary
- **#454**: Wire up (or retire) four declared-but-unread constants; DR-0001 typ targets are typed twice
- **#465**: Dedupe the taper-node worst-case loop and three ratified constants shared by the indrv and taper mismatch runners
- **#467**: power_array_folded keeps three duplicate copies of the generator's shape helpers: one drops _rect's rounding, and _vbar's argument order is swapped
- **#468**: Share the negative-control pass/fail epilogue: 4 copies in layout/, already drifted in loop placement
- **#469**: Share evidence_store's staging core and fail-closed epilogue: signoff_store's copied manifest guard drifted to .exists(), epilogue has 3 copies
- **#472**: Collapse run_klt_report onto run_klt: duplicated failure block, and the --format text leg's exit code is discarded into committed evidence

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#461**: refactor(layout): draw both negative-control fixtures with the resolved klt
- **#462**: refactor(sim): share one device-runner driver via campaign.run_device_main
- **#466**: refactor: read DR-0001 typ targets and the guard-ring stroke count from their constants
- **#471**: refactor(layout): share the negative-control pass/fail epilogue across the four controls
- **#473**: refactor(layout): check both klt report legs through one failure block
- **#478**: refactor: route power_array_folded's shape helpers through the generator's

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#452**: fix: disclose partial reference coverage in indrv's ngspice-version finding
- **#474**: refactor: share the per-node worst-case reduction and three ratified spec values
- **#476**: refactor: share evidence_store's staging core and fail-closed epilogue across signoff_store and cli

## Proposed

Issues carrying `loom:curated`.

- **#447**: indrv mismatch runner's ngspice-version Finding is emitted from a partial reference cross-check without disclosing coverage *(curated)*
- **#456**: Regenerate the extracted netlists from the current GDS and re-run the oxide-safety post-layout facet *(curated)*
- **#458**: Complete the sim/README.md facet table and fix the stale post-layout row in layout/README.md *(curated)*

## Proposed (Architect / Hermit)

- **#479**: Disambiguate the two sim-harness fmt() helpers: one name, two incompatible number formats *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 3 |
| Ready (`loom:issue`) | 4 |
| In Progress (`loom:building`) | 9 |
| PRs awaiting review | 6 |
| Approved PRs awaiting merge | 3 |
| Curated | 3 |
| Architect / Hermit proposals | 1 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
