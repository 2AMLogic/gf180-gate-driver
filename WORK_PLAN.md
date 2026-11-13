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

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#424**: Repair or remove gen_pex_requests.py: calls gen_requests.request() with a stale signature and cannot run
- **#427**: Consolidate the two samples-csv to klt-yield converters: derive_ronw_bound.py --emit-samples drifts from sim/mc_to_yield.py
- **#428**: Remove dead worktree:return npm script: its target .loom/scripts/worktree-return.sh no longer exists
- **#429**: Wire sim/test_harness_script_helpers.py into CI: 20 pytest-style tests that no CI step or stdlib runner ever executes

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

_None._

## Proposed (Architect / Hermit)

_None._

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 1 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 4 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 0 |
| Architect / Hermit proposals | 0 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
