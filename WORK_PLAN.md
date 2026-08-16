# Work Plan

This is a generated roadmap of the current GitHub label state, maintained
automatically by the Guide role's document maintenance phase. Everything
between the markers below is machine-generated and overwritten wholesale on
each update; do not hand-edit that region.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

_None._

## Urgent

Issues flagged as highest priority (`loom:urgent`).

- **#106**: Guard: BSD sed -i '' target-parsing bug causes systematic false worktree-write-confinement DENY on macOS
- **#98**: T1 gap: capture a top-level gate-driver schematic instantiating level_shifter + output_stage (checklist item 1)
- **#97**: Decompose the T1 re-read's failing items (#62) into dispatchable issues

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#112**: Guard decision: git-clean-fd still false-asks on an escaped $(...) body with a ;-separated segment inside a double-quoted --body
- **#111**: Remove unused check:ci npm script: byte-identical duplicate of lint
- **#109**: Guard: #5263 grep|head read-only fastpath disqualified by literal ERE alternation, causing false SQL_DDL_PATTERN deny
- **#106**: Guard: BSD sed -i '' target-parsing bug causes systematic false worktree-write-confinement DENY on macOS
- **#98**: T1 gap: capture a top-level gate-driver schematic instantiating level_shifter + output_stage (checklist item 1)
- **#97**: Decompose the T1 re-read's failing items (#62) into dispatchable issues
- **#94**: guard-destructive-generic.sh: recognized+confined invocation masks a coexisting hidden invocation elsewhere in the same command

## In Progress

Issues currently being built (`loom:building`).

_None._

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#112**: Guard decision: git-clean-fd still false-asks on an escaped $(...) body with a ;-separated segment inside a double-quoted --body *(curated)*
- **#111**: Remove unused check:ci npm script: byte-identical duplicate of lint *(curated)*
- **#109**: Guard: #5263 grep|head read-only fastpath disqualified by literal ERE alternation, causing false SQL_DDL_PATTERN deny *(curated)*
- **#106**: Guard: BSD sed -i '' target-parsing bug causes systematic false worktree-write-confinement DENY on macOS *(curated)*
- **#98**: T1 gap: capture a top-level gate-driver schematic instantiating level_shifter + output_stage (checklist item 1) *(curated)*
- **#97**: Decompose the T1 re-read's failing items (#62) into dispatchable issues *(curated)*
- **#94**: guard-destructive-generic.sh: recognized+confined invocation masks a coexisting hidden invocation elsewhere in the same command *(curated)*

## Proposed (Architect / Hermit)

- **#113**: Remove unused sim:list npm script: byte-identical duplicate of test *(hermit)*

## Epics

- **#22**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)

## Backlog Balance

| Tier | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Urgent | 3 |
| Ready (`loom:issue`) | 7 |
| In Progress (`loom:building`) | 0 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 7 |
| Architect / Hermit proposals | 1 |
| Active epics | 1 |
<!-- guide:plan-body:end -->
