# Work Log

Chronological record of merged PRs and closed issues in this repository.
Maintained automatically by the Guide role's document maintenance phase.

### 2026-08-12

- **PR #27**: fix(guard): restore PR #19/#20 fixes dropped by Loom surface resync
- **Issue #25** (closed): Regression: guard-destructive-generic.sh resync (c7ba31d) silently reverted PR #19 and #20 fixes
- **PR #26**: docs: narrow gate-driver overvoltage claim for output-stage taper-node ceiling excursion
- **Issue #24** (closed): Resolve output-stage §2.3 gate-ceiling shortfall at the 6V stretch rail (decision record 0004)
- **PR #23**: feat: capture and size the low-side output stage (closes #6)
- **Issue #6** (closed): Capture and size the low-side output stage to the spec's drive targets

### 2026-08-11

- **Issue #21** (closed): Guard decision: confirm stash-scope:worktree-collision ASK on git stash pop from linked worktree
- **Issue #16** (closed): Guard decision: confirm worktree-write-confinement DENY on unscoped write to main checkout

### 2026-08-08

- **PR #19**: guard: auto-allow git clean -fd scoped to own worktree's sim/**
- **Issue #15** (closed): Guard decision: allowlist scoped 'git clean -fd' on sim output dirs within own worktree
- **PR #20**: fix(guard): resolve quoted worktree-scoped write targets in guard-destructive-generic.sh
- **Issue #17** (closed): Guard decision: worktree-write-confinement-unresolved-var false positive on properly $WORKTREE_ABS-scoped writes
- **PR #18**: docs(spec): scope oxide-safety claim to a documented pre-driver exception
- **Issue #13** (closed): level_shifter pre-driver inverter overshoots 3.63V thin-oxide ceiling at VDD_LOGIC=+10%
- **PR #14**: Capture cascode/clamped level shifter, prove the 3.63V thin-oxide ceiling (partial)
- **Issue #7** (closed): Capture the cascode/clamped level shifter and prove the 3.63 V thin-oxide ceiling
- **PR #12**: sim: characterize gf180mcu medium-voltage FETs against PDK elec-specs
- **Issue #5** (closed): Characterize the medium-voltage devices against the PDK's published electrical specs
- **PR #11**: chore: remove dead pdk_available() helper
- **Issue #10** (closed): Remove dead code: pdk_available() in sim/harness/pdk.py
- **PR #9**: feat: bootstrap the two-rail ngspice PVT sim harness from gf180-bandgap
- **Issue #3** (closed): Bootstrap the sim harness, PDK environment, and evidence CI from gf180-bandgap
- **PR #8**: docs(spec): add decision record for block interface and UVLO parameters
- **Issue #4** (closed): Spec gap: UVLO is in scope with no parameters, and the block has no defined interface

### 2026-08-05

- **PR #2**: docs: ratify gate-driver target spec with decision records
- **Issue #1** (closed): Ratify the target spec
