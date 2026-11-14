# Work Log

Chronological record of merged PRs and closed issues in this repository.
Maintained automatically by the Guide role's document maintenance phase.

## Archives

- [2026-09](work_log/WORK_LOG_2026-09.md)
- [2026-08](work_log/WORK_LOG_2026-08.md)

### 2026-11-13

- **PR #445**: fix: report a skipped reference cross-check instead of a 0.00 residual
- **Issue #442** (closed): Mismatch campaigns report a 0.00 reference residual when no reference log was found: make the skipped cross-check explicit and drop the ronw script's inline copy of control_table_rows
- **PR #444**: refactor: share the klt request process table and envelope, test all three generators
- **Issue #441** (closed): Consolidate the two klt gen_requests.py generators: UVLO copy duplicates the process table and request envelope and is outside the reproduction test
- **PR #440**: fix: extend the append-only evidence check to artifact manifests
- **Issue #437** (closed): Enforce the manifest append-only rule: an edited or deleted manifests/artifacts/*.manifest.json passes every CI check
- **PR #434**: test: convert script_helpers tests to unittest and run them in CI
- **Issue #429** (closed): Wire sim/test_harness_script_helpers.py into CI: 20 pytest-style tests that no CI step or stdlib runner ever executes
- **PR #438**: chore: gitignore klt's .klt/ working state, document the tracked batch receipt
- **Issue #435** (closed): Gitignore .klt/ (klt working state) and document the one tracked batch receipt in sim/uvlo-trip-verification/klt
- **PR #432**: refactor: route the Ron·W sample emitter through mc_to_yield's row selection
- **Issue #427** (closed): Consolidate the two samples-csv to klt-yield converters: derive_ronw_bound.py --emit-samples drifts from sim/mc_to_yield.py
- **PR #436**: chore: delete the retired ratification/ key trees
- **Issue #426** (closed): Remove the retired ratification/ key trees (follow-on from PR #389)
- **PR #433**: fix: call gen_requests.request() with its post-shard signature in the PEX generator
- **Issue #424** (closed): Repair or remove gen_pex_requests.py: calls gen_requests.request() with a stale signature and cannot run
- **PR #431**: chore: remove dead worktree:return npm script
- **Issue #428** (closed): Remove dead worktree:return npm script: its target .loom/scripts/worktree-return.sh no longer exists
- **PR #389**: docs: define ratification key non-author check as session separation
- **Issue #388** (closed): Ratification keys: non-author means a fresh session, not a distinct GitHub identity

### 2026-11-12

- **PR #421**: Bump Repo Skills 0.25.10 -> 0.26.1

### 2026-11-07

- **PR #418**: Bump Repo Skills 0.25.1 -> 0.25.10

### 2026-11-06

- **PR #416**: refactor: hoist duplicated reference_measurements and claim progress/sigma helpers into script_helpers
- **Issue #343** (closed): Hoist duplicated reference_measurements and claim progress/sigma helpers into script_helpers
- **PR #414**: sim: 3-diode stacked UVLO reference measured over 15 corners (negative), DR-0023 proposed
- **Issue #412** (closed): Prototype a stacked-diode UVLO reference and measure its 15-corner trip spread (DR-0018)

### 2026-11-02

- **PR #410**: refactor: remove unused report_stored helper from signoff_store
- **Issue #409** (closed): Remove report_stored: unused helper duplicated inline by its callers

### 2026-11-01

- **PR #392**: docs(decision-records): ratify 0021, Ron·W statistical row for item 6
- **PR #404**: Bump Repo Skills 0.24.7 -> 0.25.1

### 2026-10-30

- **PR #401**: refactor: hoist corner/control deck staging into run_corner_deck
- **Issue #394** (closed): Dedupe the corner/control deck-staging block across three sim scripts
- **PR #400**: docs: disclose klt pex error status and model_mismatch in item 7 note
- **Issue #397** (closed): Disclose pex report model_mismatch block (and top-level status=error) in signoff README Item 7
- **PR #396**: feat: record klt pex post-layout report and cite it as T1 item 7
- **Issue #369** (closed): T1 item 7 (Post-layout verification): klt pex report on the current gate_driver_core GDS
- **PR #393**: feat: grade Ron*W per-PVT bound with klt yield, closing item 6 gap
- **Issue #379** (closed): T1 item 6 (Monte Carlo): draft the Ron·W statistical-row decision for ratification and clear the ronw_nfet_06v0 gap

### 2026-10-28

- **PR #384**: feat(sim): shard item-5 requests to encode ratified DR-0016/0020 corner bounds
- **PR #383**: feat(signoff): grade uvlo and drive_rail rows of T1 item 5 as klt sim evidence
- **PR #381**: spec: draft record 0021 bounding low-line UVLO lockout timing rows
- **PR #380**: docs: draft Ron·W statistical-row decision 0021 and fix item 5-7 doc drift
- **Issue #376** (closed): T1 item 5 (corner verification): encode ratified exceptions 0016/0020 in the klt sim requests so item 5 grades the ratified spec
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

