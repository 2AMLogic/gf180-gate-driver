# Work Log

Chronological record of merged PRs and closed issues in this repository.
Maintained automatically by the Guide role's document maintenance phase.

### 2026-10-28

- **PR #383**: feat(signoff): grade uvlo and drive_rail rows of T1 item 5 as klt sim evidence
- **PR #381**: spec: draft record 0021 bounding low-line UVLO lockout timing rows
- **PR #380**: docs: draft Ron·W statistical-row decision 0021 and fix item 5-7 doc drift
- **Issue #377** (closed): T1 item 5 (corner verification): express the uvlo and drive_rail rows as graded klt sim evidence (remove the declared gaps)
- **Issue #378** (closed): T1 item 5 (corner verification): resolve the sf_-40c low-line UVLO lockout (no ratified exception)

### 2026-10-27

- **PR #373**: feat(signoff): cite klt sim corner envelopes for T1 item 5
- **PR #372**: feat(signoff): cite Monte Carlo mismatch campaigns as klt yield evidence for T1 item 6
- **Issue #367** (closed): T1 item 5 (Full corner verification): cite klt sim corner envelopes covering every ratified spec/gate-driver.md row
- **Issue #368** (closed): T1 item 6 (Monte Carlo): express the four local-mismatch campaigns as klt yield reports and cite them

### 2026-10-24

- **PR #345**: refactor(sim): share mismatch record-body sections via harness campaign
- **Issue #344** (closed): Dedupe mismatch record-body composers into harness/campaign.py
- **PR #364**: fix(layout): regenerate gate_driver_core DRC-clean under the 34-layer deck
- **PR #363**: docs: scope the DRC-clean claim and triage 1513 violations under the current deck
- **PR #361**: fix: count resistor cards in LVS negative-control device total
- **PR #360**: verify: record live artifact-broker run of the layout signoff writers
- **PR #357**: refactor: share klt report runner across layout check scripts
- **PR #356**: refactor: reuse script_helpers.run_ngspice in ronw-mismatch runner
- **PR #352**: feat(layout): store signoff report bytes in the artifact store, commit manifests
- **Issue #362** (closed): layout: fix SAB, tap-implant and S/D-implant DRC violations in gate_driver_core (1513 under current deck)
- **Issue #359** (closed): layout: lvs_negative_control.py asserts transistor-card count but klt reports total device count
- **Issue #358** (closed): layout: gate_driver_core DRC reports 1513 violations under current klt/deck (committed baseline: clean)
- **Issue #354** (closed): Dedupe klt report-runner skeleton across layout run_drc/run_erc/run_lvs/run_pex_extract
- **Issue #353** (closed): Verify layout signoff store writers against a real artifact broker (follow-up to #352)
- **Issue #349** (closed): Reuse script_helpers.run_ngspice in ronw-mismatch and share the corner-deck wrapper
- **Issue #348** (closed): Route signoff outputs (LVS/PEX/DRC/ERC reports) through the artifact store
- **PR #351**: sim: add first manifest-backed smoke-mv-inverter run with verified manifest
- **PR #347**: refactor(sim): remove unused device_write_record helper
- **Issue #346** (closed): Remove dead device_write_record helper in sim/harness/report.py
- **Issue #333** (closed): Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)
- **PR #334**: feat(sim): store new sim evidence in the artifact store, commit manifests only

### 2026-10-23

- **PR #341**: refactor(sim): share first_crossing and range_verdict across experiment scripts
- **Issue #340** (closed): Consolidate duplicated crossing/interpolation helpers across sim experiment scripts
- **PR #338**: fix(sim): make inb alias check compare vinb_max_v to raw mq6
- **Issue #337** (closed): Fix _confirm_inb_alias: docstring promises an alias-equality check, body only checks key presence
- **PR #339**: refactor(sim): reuse harness parse_dc_tables in run_uvlo_trip
- **Issue #336** (closed): Remove duplicate _parse_tables in run_uvlo_trip.py: copy of script_helpers.parse_dc_tables

### 2026-10-22

- **PR #331**: refactor(layout): share one klt-not-found guard across layout scripts
- **Issue #330** (closed): Consolidate 8 drifted copies of the klt-not-found guard in layout/ scripts
- **PR #329**: docs: state power_array_folded is kept on purpose for future power-stage growth
- **Issue #317** (closed): Remove unused folded power-array generator (power_array_folded.py): no consumer in repo

### 2026-10-21

- **PR #326**: refactor: hoist mismatch campaign main() into campaign.run_mismatch_main
- **Issue #323** (closed): Dedupe main() driver skeleton across four mismatch campaign scripts
- **PR #324**: refactor: share ngspice run and error-scan helper across sim scripts
- **Issue #322** (closed): Share ngspice run/error-check tail of _run_corner across sim experiment scripts (follow-up to #313)
- **PR #320**: refactor: share reference-log lookup and delta across mismatch campaigns
- **Issue #315** (closed): Dedupe reference-log lookup and reference_delta across mismatch campaigns
- **PR #319**: refactor: share per-outcome raw-log writer across mismatch runners
- **Issue #318** (closed): Dedup per-outcome raw-log writer across three mismatch campaign runners
- **PR #314**: refactor(sim): share corner_shim across experiment scripts
- **Issue #313** (closed): Share _corner_shim/_run_corner across sim experiment scripts (follow-up to #309)
- **PR #311**: refactor(sim): share build_points and claim sigma summary across mismatch campaigns
- **Issue #309** (closed): Consolidate helpers copy-pasted across sim/*/run_*.py experiment scripts
- **PR #310**: refactor(sim): share fmt/parse_dc_tables/column across experiment scripts
- **PR #307**: Bump Repo Skills 0.24.3 -> 0.24.7

### 2026-10-16

- **PR #303**: Bump Repo Skills 0.24.1 -> 0.24.3

### 2026-10-15

- **PR #299**: Bump Repo Skills 0.19.5 -> 0.24.1

### 2026-10-14

- **Issue #251** (closed): README: embed the fleet burndown chart (one line)

### 2026-10-13

- **PR #296**: chore(loom): drop onIdle [auditor] — follow the fleet idle-role setting

### 2026-10-09

- **PR #292**: README: status refresh, spec table, reproduction steps; attest T1 item 10 (#289)
- **Issue #289** (closed): README: add reproduction steps and refresh the stale status line (blocks T1 item 10)

### 2026-10-08

- **Issue #288** (closed): T1 items 1, 2, 9, 10: cite artifact-anchored evidence now that klt signoff can bind it (klayout-tools#2843)
- **PR #290**: feat(signoff): bind T1 items 1, 2, 9 to audited artifacts; move grader pin (#288)

### 2026-10-03

- **Issue #267** (closed): Guard telemetry: keep-flagged confirmation — force-op:protected / force-op:detached (2 single-occurrence ASKs, 2026-08-18)
- **Issue #278** (closed): Auditor: worktree-write-confinement denies Champion census — gh-cached cache in /tmp/gh-cache is a routine scratch write
- **Issue #277** (closed): Auditor: worktree-write-confinement-unresolved-var denies routine mktemp scratch-file writes (17 instances)

### 2026-10-01

- **Issue #256** (closed): T1 item 11: declare ties[] (both N-well rail classes + substrate) in the klt erc supply spec so erc.missing_tie is computed (bronze grant paused on this)
- **PR #286**: feat(erc): declare all four well/substrate tie classes in the supply spec

### 2026-09-30

- **Issue #257** (closed): CI: wire test-guard-catastrophic-body-prose.sh into the Hook regression suites step
- **PR #264**: ci: wire test-guard-catastrophic-body-prose.sh into the Hook regression suites step

### 2026-09-29

- **PR #285**: chore(loom): pin docs/guard-hooks.md in resync-ignore to unblock fleet-resync
- **Issue #282** (closed): 5 of 16 .loom/hooks/tests/ suites fail at setup: they cp from a defaults/ tree this consumer repo does not ship
- **PR #284**: fix(tests): source the 5 defaults/-pathed hook suites from .loom/hooks/
- **Issue #279** (closed): Auditor: guard self-tests and repro sessions pollute guard-decisions.log, drowning real telemetry
- **PR #281**: feat(guard): LOOM_GUARD_LOG_SUPPRESS to keep test/repro fixtures out of guard-decisions.log (#279)
- **Issue #276** (closed): Finish the #258 campaign extraction: fold run_ronw_mismatch.py's private campaign layer into harness/campaign.py
- **PR #280**: refactor(sim): fold ronw's campaign layer into harness/campaign.py
- **Issue #272** (closed): Guard telemetry: unresolved-var deny on scratch write inside a heredoc body (first post-#252 recurrence, 2026-09-29)
- **PR #275**: fix(guard): two false-deny routes in worktree-write-confinement (#272)
- **Issue #263** (closed): Guard telemetry: keep-flagged confirmation — uncommitted-loss ASK family (git checkout . / git clean -fd)
- **Issue #262** (closed): Guard telemetry: stash-scope:create-redirect on worktree-internal hygiene stash (low volume)
- **Issue #261** (closed): Guard telemetry: worktree-write-confinement-unresolved-var false-positive class (5 blocks, Sep 21-23)
- **Issue #260** (closed): Guard telemetry: force-push DENY fires on guard-regression test fixtures, not real pushes
- **PR #273**: fix(guard): mask assignment-literal force-push phrases in fixture commands
- **Issue #266** (closed): sim: committed corner logs contain run-to-run nondeterministic ngspice `Reference value` lines
- **PR #270**: docs(sim): characterize ngspice Reference value corner-log nondeterminism
- **Issue #268** (closed): Remove dead code: unused _fmt_mohmmm and baseline_worst helpers, unused sys import (~9 LOC)
- **PR #269**: chore: remove dead code (_fmt_mohmmm, baseline_worst, unused sys import)
- **Issue #258** (closed): Consolidate duplicated mismatch-campaign boilerplate into sim/harness
- **PR #265**: refactor(sim): consolidate duplicated mismatch-campaign boilerplate into sim/harness

### 2026-09-23

- **Issue #254** (closed): Reusable multi-row-folded power-array generator: single-layer cross-row ties do work (mirror + nest) — correcting the 'needs a second routing layer' conclusion
- **PR #255**: Add reusable folded, cross-row-tied power-array generator (#254)
- **Issue #249** (closed): mask_ask_positional_args() shares the escaped-quote close-scan defect fixed for the catastrophic tier in #247
- **PR #253**: fix: model escaped quotes in ask-tier positional and echo mask close scans
- **Issue #248** (closed): Guard decision review: worktree-write-confinement-unresolved-var blocks the mktemp/heredoc issue-filing path
- **PR #252**: fix: resolve direct writes to bare-mktemp file stand-ins in write confinement

### 2026-09-22

- **Issue #247** (closed): Guard decision review: force-push scan false-positives when trigger text is merely quoted (refine literal masking)
- **PR #250**: fix: model escaped quotes in catastrophic positional-arg mask close scan
- **Issue #244** (closed): Guard decision: force-push-to-main literal masking misses quoted for-loop string literals (post-#134 residual)
- **PR #246**: fix(guard): mask quoted for-loop word-list literals in force-push scan

### 2026-09-21

- **Issue #242** (closed): layout/erc: add a negative control for the supply-island ERC verdict
- **PR #243**: test(layout): add ERC supply-island negative control
- **Issue #239** (closed): Commit a klt signoff block manifest so this block's T1 state is graded, not hand-read
- **PR #240**: feat(signoff): grade this block's T1 state via a klt signoff manifest
- **Issue #238** (closed): T1 item 11 (power delivery, structural): no klt erc supply spec or report in this repo
- **PR #241**: feat(layout): add klt erc supply spec and item-11 ERC evidence

### 2026-09-15

- **Issue #237** (closed): Champion: Merge-Risk Hold Digest

### 2026-09-10

- **Issue #235** (closed): sim: post-layout re-verification of the level shifter's oxide-safety claims (spec §4 cascode clamp + §5 Exception 1 `inb` bound) against the extracted gate_driver_core DUT
- **PR #236**: test: post-layout PVT re-verification of level-shifter oxide safety

### 2026-09-09

- **Issue #233** (closed): docs: refresh design/gate-driver-characterization.md to cite the 2026-08-26 complete-block post-layout (with UVLO) records
- **PR #234**: docs: refresh gate-driver-characterization.md to cite 2026-08-26 complete-block post-layout (with UVLO) records
- **Issue #22** (closed): Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)

### 2026-09-08

- **Issue #232** (closed): Champion: Merge-Risk Hold Digest

### 2026-09-02

- **Issue #218** (closed): Champion: Merge-Risk Hold Digest

### 2026-08-26

- **Issue #226** (closed): UVLO addition causes an un-excepted nominal-rail ipeak_source_a miss at ss_-40c_vlogic2p97v-vdrv4p50v (spec §3)
- **Issue #223** (closed): [Parent #219] 3A-4: docs/chipalooza/challenge-5-proposal.md for the gate driver
- **Issue #222** (closed): [Parent #219] 3A-3: post-layout PVT re-verification of the complete gate-driver block
- **Issue #221** (closed): [Parent #219] 3A-2: extend layout/ to the complete gate-driver block (add UVLO), DRC-clean + LVS-matched
- **Issue #220** (closed): [Parent #219] 3A-1: UVLO sub-cell design + full-block schematic PVT verification
- **Issue #219** (closed): [Epic #542] 3A — gf180-gate-driver maturation + Challenge #5 brief

### 2026-08-21

- **Issue #216** (closed): Add Monte Carlo local-mismatch evidence for spec/low-side-power-switch.md's Ron·W table
- **Issue #211** (closed): Monte Carlo local-mismatch campaigns for spec/gate-driver.md Sec.5 Exceptions 1 and 2

### 2026-08-17

- **Issue #122** (closed): Guard decision: ask-tier git-clean-fd substring still fires on backtick-quoted example text inside a $(cat <<EOF …) --body heredoc
- **PR #131**: fix(guard): recognize escaped $(/backtick openers nested in a live heredoc body as inert (git-clean-fd ask tier)
- **Issue #104** (closed): T1 gap: physical layout for gate-driver block (checklist item 2)
- **PR #128**: feat(layout): generate gate_driver_core GDS from its netlist via klt

### 2026-08-16

- **Issue #112** (closed): Guard decision: git-clean-fd still false-asks on an escaped $(...) body with a ;-separated segment inside a double-quoted --body
- **PR #119**: fix(guard): delimit escaped double-quoted flag values the way bash does (#112)
- **Issue #98** (closed): T1 gap: capture a top-level gate-driver schematic instantiating level_shifter + output_stage (checklist item 1)
- **PR #116**: feat(design): capture gate_driver_core top cell wiring level shifter to output stage
- **Issue #106** (closed): Guard: BSD sed -i '' target-parsing bug causes systematic false worktree-write-confinement DENY on macOS
- **PR #117**: fix: resolve real file target for BSD sed -i '' in-place edits in the Bash write guard
- **Issue #97** (closed): Decompose the T1 re-read's failing items (#62) into dispatchable issues
- **Issue #110** (closed): Guard: BSD sed -i '' (macOS two-arg form) misparsed as write target by extract_write_targets(), false worktree-write-confinement DENY
- **Issue #101** (closed): T1 gap: aggregate a block-level characterization report against spec §3 (checklist item 8)
- **PR #108**: docs: aggregate block-level characterization report against spec §3
- **Issue #96** (closed): Guard-hook adversarial checklist (builder.md) missing a 4th boundary shape: command-substitution embedding
- **PR #103**: docs(builder): add command-substitution boundary shape to guard-hook adversarial checklist
- **Issue #102** (closed): perm test - delete me
- **Issue #90** (closed): Guard decision: ask-tier git-clean-fd pattern matches on substring in ANY command text, not just actual invocations
- **PR #92**: fix(guard): treat zero recognized git-clean-fd invocations as allow
- **Issue #89** (closed): Consolidate append-only write guard in report.py; write_device_netlist_snapshot silently skips it
- **PR #91**: refactor(sim): dedup append-only exists-guard across evidence writers
- **Issue #83** (closed): Dedup _git(): near-identical git subprocess wrapper in report.py and evidence_lint.py
- **PR #87**: refactor(sim): dedup _git() git subprocess wrapper
- **Issue #82** (closed): CI 'Hook regression suites' step doesn't run test-guard-heredoc-interpreter-masking.sh (guards today's #68 fix)
- **PR #86**: ci: run test-guard-heredoc-interpreter-masking.sh in Hook regression suites
- **Issue #79** (closed): Remove unused check:all npm script: byte-identical duplicate of check:ci
- **PR #81**: chore: remove unused check:all npm script

### 2026-08-15

- **Issue #74** (closed): Process pattern: guard-hook regex/scan changes repeatedly ship without adversarial boundary tests
- **PR #75**: docs(builder): require adversarial boundary tests for guard-hook regex/scan changes
- **Issue #58** (closed): Guard decision: catastrophic:rm false-denies heredoc test fixtures mentioning a dangerous-looking string as literal text
- **PR #60**: fix(guard): mask literal-delimiter heredoc bodies before catastrophic rm scan
- **Issue #68** (closed): Guard decision: worktree-write-confinement false-denies a quoted heredoc body containing a Python '>=' comparison
- **PR #73**: fix(guard): mask non-shell interpreter heredoc bodies in write-target scan
- **PR #71**: chore: remove dead klayout_dir property in sim/harness/pdk.py
- **Issue #70** (closed): Remove dead klayout_dir property in sim/harness/pdk.py
- **PR #66**: fix(guard): mask heredoc/echo prose from ASK-tier git-clean-fd scan (#41)
- **Issue #41** (closed): Guard decision: git-clean-fd ask-tier scan false-positives on prose mentioning the phrase outside a flag value
- **Issue #62** (closed): T1/bronze checklist re-read against current evidence (2026-08-15)
- **PR #64**: chore: remove unused OC_RATIOS constant in run_device_mv_fet.py
- **Issue #61** (closed): Remove unused OC_RATIOS constant in run_device_mv_fet.py
- **Issue #56** (closed): Guard decision: stash-scope:main-checkout false-asks on --body prose containing bash '\''-escaped apostrophes
- **PR #57**: fix(guard): make strip_literal_text() single-quote masking BSQ-aware
- **Issue #51** (closed): Guard decision: rm-scope-outside-repo blocks clearing a stale GitHub App installation-token cache
- **PR #53**: feat: add invalidate-cache subcommand to github-app-token.sh
- **Issue #48** (closed): Dedup _fmt(): identical scalar-formatter in cli.py and report.py
- **PR #49**: fix(guide): reorder WORK_PLAN.md label queries to run immediately before commit
- **Issue #44** (closed): Guide's WORK_PLAN.md 'PRs Awaiting Review' section missed an already-open PR
- **PR #47**: refactor: remove duplicate _fmt helper from cli.py, use report._fmt
- **Issue #45** (closed): Remove duplicate _fmt helper in cli.py: identical to report._fmt
- **PR #42**: fix: strip leaked worktree sch_path lines from committed netlists
- **Issue #39** (closed): Strip leaked local worktree paths from committed design netlists
- **PR #38**: chore(sim): remove dead deck/log fields on PointResult
- **Issue #36** (closed): Remove dead PointResult.deck/.log fields in sim/harness/runner.py
- **PR #33**: chore(sim): remove dead spec_window helper in run_device_mv_fet.py
- **Issue #32** (closed): Remove dead spec_window helper in run_device_mv_fet.py
- **Issue #34** (closed): Remove dead spec_window helper in run_device_mv_fet.py
- **PR #30**: chore(sim): remove dead _interp_y helper in run_device_mv_fet.py
- **Issue #29** (closed): Remove dead _interp_y helper in run_device_mv_fet.py

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
