# Repository hygiene inventory (T1 item 10)

Bound by `repo-hygiene.generic.json` (T1 item 10). Audited 2026-10-09
(issue #289) against `origin/main` at `ceea0e2`. `klt signoff` hashes **this
file's bytes**; it does not read the README, run CI or judge the audit.
`check_tier_report.py` re-hashes every `path` + `sha256:` pair listed below
against the live tree, so editing a listed file without re-auditing and
refreshing this inventory (and its envelope and manifest pins) fails.

## The requirement

T1 item 10 asks for: a README stating what the block is, its spec table, and
how to reproduce every result; a license; and CI that at minimum keeps the
harness and evidence formats valid.

## Artifacts audited

| requirement | artifact | sha256 |
|---|---|---|
| README: what the block is, spec table, reproduction | `README.md` | `sha256:fc9e1a784d47150911b2be899addbac62067c72c4546b3a25cfa5c84c4de6f93` |
| License (Apache-2.0) | `LICENSE` | `sha256:cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| Authoritative spec (source of the README's table) | `spec/gate-driver.md` | `sha256:fdc793507cb5d283b2a17b5519570a450016ed65af6b687851ebfaa44e84410c` |
| CI (lint + evidence-record checks, harness self-test, signoff freshness) | `.github/workflows/ci.yml` | `sha256:d03ca3f5fce84882f73cfed8859b8522938c2934c295bdd4e134dec35aa6ec3b` |

Reproduction documents the README links to (read, hashed so a change forces a
re-audit of the links):

| document | sha256 |
|---|---|
| `design/README.md` | `sha256:57077ce9d683d9780c07559db7d28ffcc150d326c338942ad06160ddfc402b54` |
| `sim/README.md` | `sha256:8659ba36577da6d9bfc6729cebeda93de188ceb1a5745204a739037820a9815c` |
| `sim/harness/README.md` | `sha256:a8038d3738e5899cab8d934312895dac9689a9e87083bda3580b406d32103106` |
| `layout/README.md` | `sha256:5b75a49d3e9705c0c2574c848fae848745f1a172ea2069e7bdc54969416ed7b4` |
| `design/gate-driver-characterization.md` | `sha256:200edaf4b47b2b63214b08ed77f574a4ebbf089a2029e4f345bddbf5c81361f9` |

## Findings

- **README states what the block is**: yes (opening paragraph, "Why this
  block", the two-facet scope section).
- **Spec table**: the README carries the target/stretch table of
  `spec/gate-driver.md` section 3, transcribed by hand (the check was a
  row-by-row visual comparison, not a mechanical diff; `>=` replaces the
  spec's U+2265, `--` replaces its dash). It links the spec as authoritative,
  labels the table as targets rather than results, and names the two ratified
  bounded exceptions (decision records 0016 and 0020).
- **Status line**: the stale "schematic capture underway" statements were
  replaced with a statement tied to committed evidence, listing the open UVLO
  finding and that the block is not tier T1 or tapeout-ready.
- **Reproduction**: the README gives root-relative commands that separate
  "validate committed evidence" from "generate new evidence", covers
  netlisting, schematic simulation, layout generation, DRC/LVS/extraction/ERC,
  no-RC versus RC post-layout runs, and the dedicated characterization and
  Monte Carlo scripts, and links the documents hashed above. It discloses the
  layout-regeneration byte-identity limitation recorded in
  `verification/signoff/README.md`.
- **License**: `LICENSE` is the Apache License 2.0 text, matching the README's
  license statement.
- **CI**: `.github/workflows/ci.yml` defines `lint` (runs
  `.github/scripts/lint.sh --require-shellcheck --require-append-only`,
  which includes the evidence-record format and append-only check), a harness
  self-test job, and the `signoff` job (checker regression tests and the
  freshness gate).

## What was actually read and run

- **Read** (not executed): all files in the two tables above, and the
  `layout/README.md` Status and Regenerating sections. Link targets in the
  README were checked for existence on disk with a shell loop.
- **Executed**: `python3 sim/run_corners.py --check-env` (ngspice-42 and the
  gf180mcuD PDK, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, found),
  `python3 sim/run_corners.py --list`, `python3 sim/check_records.py`, and the
  lint, checker and signoff commands named in the PR.
- **Not executed**: no simulation campaign, no netlisting, no layout
  generation, DRC, LVS, extraction or ERC run was performed for this audit, so
  none of the README's "Generate new evidence" commands was verified end to
  end here. CI was not run remotely as part of the audit; the workflow was
  read, not observed to pass. The README's command lines were taken from the
  linked project documents, not exercised.
- **Known limitations the README repeats**: the layout generator's
  byte-identical regeneration claim did not hold on the 2026-10-08 audit
  (see `verification/signoff/README.md`); cited post-layout records
  state they were taken on a dirty working tree; the audit host has
  ngspice-42 while the primary record states ngspice-46.

## Re-audit for issue #333 (2026-10-23)

Two listed files changed on the issue #333 branch (`feature/issue-333`, on top
of `origin/main` at `9ed9ed8`) and were re-read against the findings above;
their hashes are refreshed in the tables:

- `.github/workflows/ci.yml` (**read** the diff): adds a `Stored-evidence
  manifests` step to `lint` (`scripts/check_artifact_manifests.py check`) and
  an `Evidence-store and manifest-check unit tests` step to `test`. `lint`
  (with the evidence-record check), the harness self-test and the `signoff`
  job are unchanged, so the CI finding still holds. CI was read, not observed
  to pass here.
- `sim/README.md` (**read** the diff): adds the "Stored evidence" section and
  marks the existing directory layout as the legacy one. The facet-table
  omission disclosed above is unchanged. The root `README.md`'s reproduction
  commands were not re-read or edited for this change, so they do not yet
  describe the manifest-backed layout.

The other listed files are unchanged. No simulation, netlisting or layout flow
was run for this re-audit.

## Re-audit for issue #348 (2026-10-24)

Two listed files changed on the issue #348 branch (`feature/issue-348`) and
were re-read against the findings above; their hashes are refreshed in the
tables:

- `.github/workflows/ci.yml` (**read** the diff): adds a `Signoff-store unit
  tests` step to `test` (`python3 layout/common/test_signoff_store.py`) and the
  matching row in the header table. `lint`, the harness self-test and the
  `signoff` job are unchanged, so the CI finding still holds. CI was read, not
  observed to pass here.
- `layout/README.md` (**read** the diff): adds the "Stored vs committed signoff
  outputs (#348)" section under the verification flow. It documents which
  layout outputs go to the artifact store and which stay in git; the
  reproduction commands and the stale "Post-layout simulation" status row noted
  above are unchanged. The root `README.md`'s reproduction commands were not
  re-read or edited for this change, so they do not yet describe the
  store-backed layout runners (which now exit `10` without
  `KLT_ARTIFACT_BROKER`).

The other listed files are unchanged. No simulation, netlisting or layout flow
was run for this re-audit.

Artifact binding verifies the bytes listed here, not the truth of this audit.

## Re-audit for issue #358 (2026-10-24)

Two listed files changed on the issue #358 branch (`feature/issue-358`) and
were re-read against the findings above; their hashes are refreshed in the
tables:

- `README.md` (**read** the diff): the status line and the Layout bullet now
  say DRC is not clean under the current deck (1513 violations) instead of
  quoting the old `status: clean`. Reproduction commands are unchanged.
- `layout/README.md` (**read** the diff): the DRC status heading, table row,
  "Latest report" paragraph and Known-gaps bullet now state the current
  violations and scope the old clean report as historical. Reproduction
  commands are unchanged.

The other listed files are unchanged. No simulation, netlisting or layout flow
was run for this re-audit beyond the DRC re-run recorded in
`layout/drc/triage_sab_implant.md`.

## Re-audit for issue #362 (2026-10-24)

Two listed files changed on the issue #362 branch (`feature/issue-362`) and
were re-read against the findings above; their hashes are refreshed in the
tables:

- `README.md` (**read** the diff): the status line and the Layout bullet now
  say DRC is clean under the current curated deck (not a medium-voltage
  signoff) and that the post-layout PVT records were not re-run on the
  regenerated GDS, instead of quoting 1513 violations. Reproduction commands
  are unchanged.
- `layout/README.md` (**read** the diff): the DRC status heading, table row,
  "Current status" paragraph, `dnwell_partition` description, LVS "Latest
  report" line, Known-gaps bullet and "Post-layout simulation" row now describe
  the regenerated GDS and its fresh DRC/LVS/ERC reports. Reproduction commands
  are unchanged.

The other listed files are unchanged. The layout flow was run for the change
itself (`gen_gate_driver_core.py`, `check_gate_driver_core.py`, `run_drc.py`,
`run_lvs.py`, `run_erc.py`), not as part of this audit; no simulation or
netlisting was run.

## Re-audit for issue #368 (2026-10-27)

`.github/workflows/ci.yml` changed and was re-read against the findings above;
its hash is refreshed in the table:

- adds a `Monte Carlo CSV to klt-yield converter unit tests` step to `test`
  (stdlib unittest, no ngspice or PDK) and moves the `signoff` job's klt pin
  from `3a75c3ae` to `879d39ba` (see `verification/signoff/README.md`, "Grader
  pin move, 3a75c3ae to 879d39ba"). `lint`, the harness self-test and the
  signoff job's steps are otherwise unchanged, so the CI finding still holds.
  CI was read, not observed to pass here.

The other listed files are unchanged for #368.

## Re-audit for issue #367 (2026-10-27)

One listed file changed on the issue #367 branch (`feature/issue-367`, on top of
`origin/main` at `03685aa`) and was re-read against the findings above; its
hash is refreshed in the table:

- `.github/workflows/ci.yml` (**read** the diff): the `signoff` job's grader pin
  moves from klayout-tools `3a75c3ae` to `879d39ba` (the older build grades
  item 5's multi-envelope + `spec_rows` form `invalid_evidence`), with the
  explanatory comment updated. `lint`, `test` and the harness self-test are
  unchanged, so the CI finding still holds. CI was read, not observed to pass
  here.

The other listed files are unchanged. `klt sim` corner envelopes were produced
for item 5 (see `verification/signoff/README.md`); no simulation (beyond those
envelopes, run on the batch fleet), netlisting or layout flow
was run for this re-audit.

## Re-audit for issue #379 (2026-10-28)

One listed file changed on the issue #379 branch (`feature/issue-379`, on top
of `origin/main` at `d7a2b69`) and was re-read against the findings above; its
hash is refreshed in the table:

- `README.md` (**read** the diff): the "Signoff" bullet now describes items 5-7
  as the report grades them (item 5 `check_failed`, item 6 `partial_coverage`,
  item 7 no `klt pex` envelope) instead of "no `klt`-native sim/yield/pex
  envelopes". Reproduction commands are unchanged.

The other listed files are unchanged. No simulation, netlisting or layout flow
was run for this re-audit.

## Re-audit for issue #424 (2026-11-13)

One listed file changed on the issue #424 branch (`feature/issue-424`, on top
of `origin/main` at `06ea774`) and was re-read against the findings above; its
hash is refreshed in the table:

- `.github/workflows/ci.yml` (**read** the diff): adds a `klt request-generator
  reproducibility tests` step to `test` (stdlib unittest, no ngspice, no PDK,
  writes nothing under `sim/`) and the matching row to the job table in the
  file's header comment. `lint`, the `signoff` job and every other `test` step
  -- including the grader pin -- are unchanged, so the CI finding still holds.
  CI was read, not observed to pass here.

The other listed files are unchanged. The new step exists because
`sim/gate-driver-core-drive-with-uvlo/klt/pex/gen_pex_requests.py` had been
calling `gen_requests.request()` with its pre-shard signature since `26ea6de`
and could not run, which broke the first line of item 7's documented
reproduction command; neither file is listed in this inventory, and no
committed request, bound or evidence file changed. No simulation, netlisting or
layout flow was run for this re-audit.

## Re-audit for issue #429 (2026-11-13)

One listed file changed on the issue #429 branch (`feature/issue-429`, on top
of `origin/main` at `fef935d`) and was re-read against the findings above; its
hash is refreshed in the table:

- `.github/workflows/ci.yml` (**read** the diff): adds a `run_*.py
  shared-helper unit tests` step to `test`, running
  `sim/test_harness_script_helpers.py` (stdlib unittest; its three ngspice
  tests put a two-line `/bin/sh` stub on `PATH`, so the step needs no
  simulator and no PDK and belongs on the PDK-free runner), plus the matching
  row in the job table in this file's header comment. The `signoff` job --
  including the grader pin -- and every other `test` step are unchanged, as is
  the `lint` job's own definition, so the CI finding above still holds. CI was
  read, not observed to pass here.

The `lint` job's behaviour does change, through the script it invokes rather
than through the workflow: `.github/scripts/lint.sh` gains a step 5/5 that
fails any tracked `test_*.py` which no non-comment line of the workflow names.
That script is not listed in this inventory and carries no hash here, so the
change is recorded but not pinned; the evidence-record format and append-only
checks it also runs, which the CI finding cites, are unchanged.

The other listed files are unchanged. Both changes exist because
`sim/test_harness_script_helpers.py` was written pytest-style in a stdlib-only
repo, so `python3 -m unittest` collected nothing from it and no CI step named
it -- its pins had never been enforced (issue #429). No simulation, netlisting
or layout flow was run for this re-audit.

## Re-audit for issue #437 (2026-11-13)

One listed file changed on the issue #437 branch (`feature/issue-437`, on top
of `origin/main` at `dffd337`) and was re-read against the findings above; its
hash is refreshed in the table:

- `sim/README.md` (**read** the diff): the append-only section gains one
  paragraph stating that the same check now covers
  `manifests/artifacts/*.manifest.json`, because for a manifest-backed record
  the manifest stands in for the netlist snapshot and per-corner logs that are
  not committed, and that a stored run is superseded by storing a fresh run and
  committing its manifest rather than by rewriting the old one. Nothing else
  moved: the "Stored evidence" section, the facet table (whose four-experiment
  omission disclosed above is unchanged) and every reproduction command are
  untouched, so the Reproduction finding still holds.

The other listed files are unchanged; in particular `.github/workflows/ci.yml`
is untouched by this branch, so the CI finding still holds. The `lint` job's
behaviour does broaden, through a module the workflow invokes rather than
through the workflow itself: `sim/harness/evidence_lint.py` (reached via
`sim/check_records.py --require-append-only`) now also refuses a modified or
deleted `manifests/artifacts/*.manifest.json`, with a distinct remedy string.
That module and `manifests/artifacts/README.md`, which gained the matching
prose, are not listed in this inventory and carry no hash here, so the change
is recorded but not pinned.

Both edits exist because the append-only guarantee was documented and enforced
for `sim/` records only, while the stored-run manifests that stand in for their
uncommitted bytes were editable (issue #437). No simulation, netlisting or
layout flow was run for this re-audit.

## Re-audit for issue #441 (2026-11-13)

Two listed files changed on the issue #441 branch (`feature/issue-441`, on top
of `origin/main` at `1a74908`) and were re-read against the findings above;
their hashes are refreshed in the tables:

- `.github/workflows/ci.yml` (**read** the diff): the `test` job's `klt
  request-generator reproducibility tests` step changes the path it runs from
  `sim/gate-driver-core-drive-with-uvlo/klt/test_gen_requests.py` to
  `sim/test_gen_requests.py` (the same test, moved up because it now covers
  generators under two testbenches rather than one), and its comment is
  rewritten to describe the widened coverage. No job, trigger, permission,
  concurrency setting or other step moved; `lint` (with the evidence-record and
  append-only checks), the harness self-test steps and the `signoff` job are
  unchanged, so the CI finding still holds. The header table's row for this
  step names no path and is unchanged. CI was read, not observed to pass here.
- `sim/harness/README.md` (**read** the diff): adds one section, "`klt sim`
  requests: `harness/klt_request.py`", before "smoke-mv-inverter", documenting
  the module the `sim/*/klt/` request generators now share and noting that
  editing `corners.CORNERS` for tt/ff/ss/fs/sf fails the generator test. The
  Quick start, Prerequisites, PVT grid, testbench-authoring, "What a run
  writes", Monte Carlo and xschem sections are untouched, so every reproduction
  command this inventory's Reproduction finding relies on is unchanged.

The other listed files are unchanged; in particular `README.md`, `LICENSE` and
`spec/gate-driver.md` are untouched by this branch, so those findings still
hold. Recorded but **not** pinned here: the new `sim/harness/klt_request.py`,
the relocated `sim/test_gen_requests.py`, the two `klt/` generators now
importing that module, and the two `sim/*/klt/README.md` files -- none is
listed in this inventory and none carries a hash in it. The committed
`request-*.json` files under both `klt/` directories are byte-identical before
and after (they are inputs of cited item-5 and item-7 evidence), which is what
the relocated test asserts.

Both edits exist because the UVLO request generator duplicated the process
table and request envelope of the item-5 core-drive generator and was the one
generator outside the reproduction test added for issue #424 (issue #441). No
simulation, netlisting or layout flow was run for this re-audit.

## Re-audit for issue #456 (2026-11-14)

One listed file changed on the issue #456 branch (`feature/issue-456`, on top
of `origin/main` at `cbf0cd4`) and was re-read against the findings above; its
hash is refreshed in the table:

- `.github/workflows/ci.yml` (**read** the diff): the "Extracted post-layout
  DUT netlists are in sync with their reports" step's two `mk_extracted_dut.py
  --check` invocations now point at the two extraction reports issue #456
  promoted from the current GDS (`20261114-194101-cbf0cd4.extract.json` and
  `20261114-194121-cbf0cd4.pex-extract.json`) instead of the 2026-08-26 pair.
  Both `--check` re-derivations pass byte-for-byte against the regenerated
  committed netlists. No job, step, trigger, permission or pin moved — the
  `lint`, `test` and harness self-test jobs and the signoff job's grader pin
  are unchanged, so every finding above still holds. CI was read, not observed
  to pass here.

The other listed files are unchanged; in particular `README.md`, `LICENSE` and
`spec/gate-driver.md` are untouched by this branch, so those findings still
hold. Recorded but **not** pinned here: `layout/lvs/mk_extracted_dut.py` and
the regenerated netlists/reports themselves — none is listed in this inventory
and none carries a hash in it. The extraction re-run and both oxide-safety
simulation runs happened for the change itself, not as part of this audit; no
additional simulation was run for this re-audit.

## Re-audit for issue #468 (2026-11-15)

Two listed files changed on the issue #468 branch (`feature/issue-468`, on top
of `origin/main` at `0f25e3c`) and were re-read against the findings above;
their hashes are refreshed in the tables:

- `.github/workflows/ci.yml` (**read** the diff): the `test` job's coverage
  comment gains one row (`layout/common/test_control_verdict.py`) and the job
  gains one step, `Negative-control verdict unit tests`, running
  `python3 layout/common/test_control_verdict.py` on the same PDK-free runner
  (pure stdlib; the controls themselves need klt + the PDK). No job, trigger,
  permission, concurrency setting or other step moved; `lint` (with the
  evidence-record and append-only checks), the harness self-test steps and the
  `signoff` job are unchanged, so the CI finding still holds. CI was read,
  not observed to pass here.
- `layout/README.md` (**read** the diff): adds two lines to the `common/`
  part of the directory tree, listing `common/control_verdict.py` (the one
  pass/fail epilogue all four negative controls now return through) and
  `common/test_control_verdict.py` (its unit tests, PDK-free CI). The Status
  and Regenerating sections and every reproduction command are untouched, so
  the listing the Reproduction finding relies on stays accurate.

The other listed files are unchanged; in particular `README.md`, `LICENSE` and
`spec/gate-driver.md` are untouched by this branch, so those findings still
hold. Recorded but **not** pinned here: the new
`layout/common/control_verdict.py` and `layout/common/test_control_verdict.py`
and the four negative controls now returning through the shared epilogue
(`layout/drc/deck_negative_control.py`, `layout/erc/erc_negative_control.py`,
`layout/ground_rail_negative_control.py`,
`layout/lvs/lvs_negative_control.py`) -- none is listed in this inventory and
none carries a hash in it.

Both edits exist because the four layout negative controls each carried their
own copy of the pass/fail epilogue and could drift apart (issue #468). No
simulation, netlisting or layout flow was run for this re-audit.

## Re-audit for issue #458 (2026-11-14)

Three listed files changed on the issue #458 branch (`feature/issue-458`, on
top of `origin/main` at `cbf0cd4`) and were re-read against the findings
above; their hashes are refreshed in the tables:

- `README.md` (**read** the diff): removes both workarounds this audit's
  findings recorded — the sentence disclosing that `sim/README.md`'s facet
  table omits four on-disk experiments (the table now lists all sixteen) and
  the parenthesis calling `layout/README.md`'s "Post-layout simulation" status
  row stale (the row now states the committed complete-block evidence, the
  pre-#362 extraction it ran against and the re-run's owner, issue #456).
  Reproduction commands are unchanged.
- `sim/README.md` (**read** the diff): the "Facets in this repo" table gains
  the five missing experiment rows (`gate-driver-core-drive-with-uvlo`,
  `uvlo-trip-verification`, `level-shifter-inb-mismatch`,
  `output-stage-taper-mismatch`, `uvlo-reference-study`) and the entry-count
  sentence is corrected to the new count, date-stamped. Reproduction commands
  are unchanged.
- `layout/README.md` (**read** the diff): the "Post-layout simulation" status
  row now states the committed complete-block records, the committed
  pre-#362-extraction DUTs they ran against, the primary record's dirty-tree
  provenance and the outstanding re-run's owner (issue #456); the
  "### Post-layout simulation" section note's #222 citation is updated to
  #456 and its substantive claim (nothing below the note has been
  re-verified against the current `gate_driver_core.gds`) is unchanged.
  Reproduction commands are unchanged.

This re-audit also corrected the two known-gap statements above that the same
edits close — the Reproduction finding's facet-omission disclosure and the
"Known limitations" bullet's stale-status-row clause — which is why this
inventory's own hash moved and its downstream pins are refreshed. The other
listed files are unchanged. No simulation, netlisting or layout flow was run
for this re-audit.

## Re-audit for issue #470 (2026-11-14)

One listed file changed on the issue #470 branch (`feature/issue-470`, on top
of `origin/main` at `cbf0cd4`) and was re-read against the findings above; its
hash is refreshed in the table:

- `layout/README.md` (**read** the diff): the Supply-island ERC section's
  "Latest report" line now cites the fresh envelope `20261114-193042-cbf0cd4`
  (the one item 11 pins) instead of the unpinned `20260921-155739`, the GDS
  hash it quotes is corrected from the pre-#362 `54f02626…` to the committed
  `15fa5b64…`, and a "Tool-drift history of this verdict" paragraph is added
  stating what klt ≥ 0.9 made of the pre-#470 committed ERC envelope and how
  the `substrate_gnd_logic` `well_boxes` correction (#470) restores the
  `erc_status: clean` verdict under the current build. A review-feedback fix
  on this branch (PR #488) also corrects that section's report-producer
  paragraph: it now names the repinned envelope's actual producing build
  (`klt 0.9.2.dev1029+g76f47afa48f1`, git rev `76f47afa48f1`) instead of the
  superseded `0.5.0`/`b15edf5e` one, gives the reproduction command in the
  `uvx --from`/scratch-venv form, and drops the stale "PATH-installed pin
  predates `--deck`" sentence — so the section's reproduction command *did*
  change; the Reproduction finding itself (the root README's
  validate-vs-generate command structure) is untouched and still holds. The
  "Post-layout simulation" status row this audit already disclosed
  as stale is untouched (issue #458 owns it).

The other listed files are unchanged; in particular `README.md`, `LICENSE`,
`spec/gate-driver.md` and `.github/workflows/ci.yml` are untouched by this
branch, so those findings still hold. Recorded but **not** pinned here:
`layout/erc-supply-spec.json` (its `well_boxes` correction and `_comment`
provenance are issue #470's own deliverable) and the fresh ERC envelope and
negative-control manifests, which item 11 pins through
`verification/signoff/manifest.json` instead. The ERC re-run and the
negative-control run happened for the change itself, not as part of this
audit; no simulation or netlisting was run.

## Re-audit for issue #463 (2026-11-15)

Two listed files changed on the issue #463 branch (`feature/issue-463`, on
top of `origin/main` at `f4f0cb4`) and were re-read against the findings
above; their hashes are refreshed in the table:

- `.github/workflows/ci.yml` (**read** the diff): the `signoff` job gains a
  "Layout provenance freshness" step running the new stdlib-only
  `layout/test_check_layout_provenance.py` and
  `layout/check_layout_provenance.py` beside the existing checker regression
  tests. The job's charter (CI keeps the harness and evidence formats valid)
  is extended, not changed -- the new step is a freshness check of the same
  class as the signoff re-grading already in the job, and it needs no klt
  generation install and no PDK. No other job or step moves.
- `layout/README.md` (**read** the diff): the "Reproducibility: pin the klt
  install (#190)" section gains a closing block recording the
  generated-layout drift class (#463): klt >= 0.9.2 renames generated
  sub-cells, so byte-equality against the committed GDS is not the
  reproducibility test on a drifted host (the same-klt comparison is); T1
  item 2's live claim rests on the criterion's documented-provenance arm;
  `check_layout_provenance.py` re-hashes the three recorded pins in CI with
  an advisory klt-version arm; and the upstream filing
  (klayout-tools#5808) is linked. The DRC/LVS status sections and the
  reproduction instructions the audit findings rest on are untouched.

The other listed files are unchanged, so those findings still hold. As with
the #470 re-audit, the envelope, manifest item 10 and tier-report citation
pins are refreshed for the new inventory bytes. No simulation, netlisting,
layout flow or generator re-run happened as part of this audit; the same-klt
generator comparison the refreshed `generator.sha256` pin rests on was run
into scratch directories outside the tree.

## Re-audit for the PR #471 merge (2026-11-15)

Two listed files changed in the merge of `origin/main` into
`feature/issue-468` (PR #471's conflict resolution) and were re-read against
the findings above; their hashes are refreshed in the tables:

- `.github/workflows/ci.yml` (**read** both diffs against the branch's last
  main-merge point): both sides had edited it, and the merged file carries
  each side's change in full — this branch's re-audited state (the #468
  re-audit above) plus main's signoff job "Layout provenance freshness"
  step (the #463 re-audit above). No other job, step, trigger, permission
  or pin moved, so the findings above still hold.
- `layout/README.md` (**read** both diffs): both sides had edited it, and
  the merged file carries each side's change in full — main's #458
  facet-table/status-row corrections and this branch's #468 re-audit
  refresh. The audit findings that lean on its Status/Regenerating
  sections still hold.

The other listed files are unchanged, so those findings still hold. CI was
read, not observed to pass here. No simulation, netlisting or layout flow
was run for this re-audit.


## Re-audit for the PR #489 merge (2026-11-15)

One listed file changed in the merge of `origin/main` into
`feature/issue-456` (PR #489's conflict resolution) and was re-read against
the findings above; its hash is refreshed in the table:

- `.github/workflows/ci.yml` (**read** both diffs against the merge base
  `cbf0cd4`): both sides had edited it, and the merged file carries each
  side's change in full — the "Extracted post-layout DUT netlists are in
  sync with their reports" step's two `mk_extracted_dut.py --check`
  invocations re-pointed at the 20261114 reports (the #456 re-audit above),
  and the signoff job's "Layout provenance freshness" step (the #463
  re-audit above). Nothing else moved: no job, trigger, permission or pin
  changed on either side, so every finding above still holds. CI was read,
  not observed to pass here.

All nine listed hashes were re-computed against the merged tree and match
the tables (the #458/#470 refreshes of the README set still hold — this
branch touched none of those files). The other findings are unchanged. No
simulation, netlisting or layout flow was run for this re-audit.
## Re-audit for issue #479 (2026-11-15)

One listed file changed on the issue #479 branch (`feature/issue-479`,
authored on top of `origin/main` at `5f0632d`, since merged forward) and was
re-read against the findings above; its hash is refreshed in the table:

- `sim/harness/README.md` (**read** the diff): renames one helper in the
  campaign API bullet list — `fmt` is now `sigfig` — because
  `sim/harness/campaign.py`'s significant-figures formatter and
  `sim/harness/script_helpers.py`'s fixed-decimal formatter both exported the
  name `fmt` (issue #479); the two behaviours are kept, only the names moved.
  The Quick start, Prerequisites, PVT grid, testbench-authoring, "What a run
  writes", Monte Carlo and xschem sections are untouched, so every
  reproduction command this inventory's Reproduction finding relies on is
  unchanged.

The other listed files are unchanged; in particular `README.md`, `LICENSE`,
`spec/gate-driver.md` and `.github/workflows/ci.yml` are untouched by this
branch, so those findings still hold. The renamed helpers are recorded but
**not** pinned here: `sim/harness/campaign.py`,
`sim/harness/script_helpers.py` and the seven bench runners that call them
carry no hash in this inventory. No simulation, netlisting or layout flow was
run for this re-audit; the rename is a pure name change with byte-identical
formatter output, verified by the harness test suites and an old-vs-new
equivalence battery on the PR (210 calls, 0 mismatches).

## Re-audit for issue #502 (2026-11-15)

One listed file changed on the issue #502 branch (`feature/issue-502`, on
top of `origin/main` at `89390e0`) and was re-read against the findings
above; its hash is refreshed in the table:

- `layout/README.md` (**read** the diff): the "Generated layout drifts the
  same way, and #463 made it checked" paragraph gains a dated same-klt
  comparison record for the #467 generator refactor (merged as PR #478):
  regeneration from pre-#478 main (`d46e492`) and from main (`89390e0`)
  under one host `klt 0.9.3.dev3+gd5d57daf9a14` produced byte-identical
  GDS output (`cmp`: identical, both `736c92bb…`), so the refactor is
  GDS-neutral and `gate_driver_core.provenance.json`'s `generator.sha256`
  moved to the post-#467 generator with the committed GDS untouched
  (issue #502). The DRC/LVS status sections and the reproduction
  instructions the audit findings rest on are untouched.

The other listed files are unchanged; in particular `README.md`, `LICENSE`,
`spec/gate-driver.md` and `.github/workflows/ci.yml` are untouched by this
branch, so those findings still hold. As with the #463 re-audit, the
envelope, manifest item 10 and tier-report citation pins are refreshed for
the new inventory bytes. No simulation, netlisting, layout flow or
generator re-run happened as part of this audit; the same-klt generator
comparison summarized above was run into scratch directories outside the
tree and is recorded in `layout/README.md` and the issue #502 commit.

## Re-audit for the second PR #471 merge (2026-11-15)

Two listed files changed in the merge of `origin/main` (`5c051fde`) into
`feature/issue-468` (PR #471's second conflict resolution) and were re-read
against the findings above; their hashes are refreshed in the table:

- `sim/harness/README.md`: changed on main only — the #479 `fmt`→`sigfig`
  helper rename, already recorded in the #479 re-audit above. The merge
  takes main's side verbatim (re-hash matches), so that re-audit's
  findings hold unchanged here.
- `layout/README.md` (**read** the merged result against both sides): the
  merged file is a disjoint-section union of the three edits — this
  branch's #468 `common/` listing additions
  (`common/control_verdict.py` + its test, verifiable in the merged
  listing), main's #458 facet-table/status-row corrections, and main's
  #502 same-klt generator comparison record (the `736c92bb…` paragraph).
  `git diff origin/main -- layout/README.md` reduces to exactly the two
  #468 listing entries, so no main-side content was dropped or altered.
  The audit findings that lean on its Status/Regenerating sections still
  hold.

Every pinned file in both tables was re-hashed against the merged tree;
the other seven rows are byte-identical to their pins, so those findings
hold. CI was read, not observed to pass here. No simulation, netlisting or
layout flow was run for this re-audit; the ERC-control equivalence
re-establishment that accompanied this merge is recorded in the PR
conversation, not here (it touches no pinned file).

## Re-audit for issue #492 (2026-11-15)

One listed file changed on the issue #492 branch (`feature/issue-492`,
authored on top of `origin/main` at `ec0ee77`) and was re-read against the
findings above. Its hash is refreshed in the table for the **merged** bytes:
this re-audit was re-derived while resolving the branch's merge with a main
that had since taken #479 and #502, so the pinned `layout/README.md` is the
merge of this branch's change with #502's same-klt comparison paragraph
(recorded in the #502 re-audit above):

- `layout/README.md` (**read** the diff): the "Reproducibility: pin the klt
  install (#190)" section's pinned-install recipe is restated in the
  throwaway-environment form the ERC section already uses
  (`uvx --from "git+https://github.com/2AMLogic/klayout-tools@<rev>" klt …`,
  or a scratch `uv venv` from the same pinned source) instead of a bare
  `uv tool install --from` into the host's shared tool paths — a
  host-mutating step agents working on this repo are not permitted to run —
  and the before-trusting-a-re-run sentence now names both
  `provenance.deck.content_hash` and `provenance.klt_version`. The
  section's point (pin the revision; a content-hash mismatch means the deck
  build moved, not the layout), the klayout-tools#1149/#1154 history and
  the `sha256:6a323622…` reference triple are unchanged, and line 576's
  bare-install mention survives only as the drift hazard it always was.
  `verification/signoff/README.md` (mentioned in prose above, not pinned in
  the hash table) also gained a sentence directing shared-host grading
  installs into a throwaway venv or `uvx` — no cascade cost. No findings
  change.

The other listed files are unchanged relative to the merged tree
(`sim/harness/README.md` carries #479's recorded rename and nothing from this
branch), so those findings still hold. The envelope, manifest item 10 and
tier-report citation pins are refreshed for the new inventory bytes. No
simulation, netlisting, layout flow or generator re-run happened as part of
this audit.
## Re-audit for the PR #489 second merge (2026-11-15)

`origin/main` moved again after the first PR #489 conflict-resolution merge
above, and this second merge brings the issue #479 and issue #502 re-audit
sections (and their hash-table refreshes) into this inventory from main.
The merged tree was re-checked against the findings above:

- `.github/workflows/ci.yml` did **not** change on the main side of this
  second merge — branch-vs-main the only difference remains the AC 4
  re-point recorded in the first PR #489 merge section above, so its table
  hash is unchanged and still matches.
- The issue #479 (`sim/harness/README.md`) and issue #502
  (`layout/README.md`) table rows this merge brings in were re-computed
  against the merged tree and match.

All nine listed hashes were re-computed against the final merged tree and
match the tables. The other findings are unchanged. No simulation,
netlisting or layout flow was run for this re-audit.

## Re-audit for issue #472 / the PR #473 merge (2026-11-15)

Two listed files changed — one by the issue #472 branch, one via the merge
of `origin/main` into it (merge base `0f25e3c9`) — and were re-read against
the findings above; their hashes are refreshed in the tables:

- `.github/workflows/ci.yml` (**read** the diff): the issue #472 branch adds
  a `klt report-runner unit tests` step to `test`
  (`python3 layout/common/test_klt_report.py`) and the matching row in the
  header table — the shared `klt` runner every layout/ signoff script goes
  through now has both legs checked against the caller's `ok_codes`, with one
  copy of the failure block (issue #472). The merge carries main's side in
  full: the signoff job's "Layout provenance freshness" step (the issue #463
  re-audit above). The job's charter is extended with one more PDK-free
  unit-test step of the same class as the existing ones; the CI finding above
  (what the workflow checks) still holds and now covers one more PDK-free
  test. CI was read, not observed to pass here.
- `layout/README.md` (**read** the diff, via the merge): the issue #502
  re-audit section above records the same-klt generator comparison paragraph
  this merge brings in; the merged file's hash matches that section's table
  row, and this branch made no edit of its own to the file (as of this
  merge — the issue #492 branch's own restate of the pinning recipe edits
  the same file, recorded and pinned in the issue #492 re-audit above and
  the second merge section below).

The other listed files are unchanged by the branch; the merge's updates to
`README.md`, `sim/README.md` and `sim/harness/README.md` (the issue #479
`fmt` -> `sigfig` rename) are the versions the existing table rows already
name, re-computed against the merged tree and matching. No simulation,
netlisting or layout flow was run for this re-audit.

## Re-audit for the PR #489 third merge (2026-11-16)

`origin/main` moved again after the PR #489 second merge above — PR #473
(issue #472) landed on main carrying the `klt report-runner unit tests`
step — so the second-merge section's statement that `ci.yml` did not change
on the main side held for that merge but does not hold for this one, and
the merged `.github/workflows/ci.yml` was re-read (**read** both diffs
against the merge base `5c051fd`): it now carries each side's change in
full — the "Extracted post-layout DUT netlists are in sync with their
reports" step's two `mk_extracted_dut.py --check` invocations re-pointed at
the 20261114 reports (the #456 re-audit above) on the branch side, and the
`klt report-runner unit tests` step plus its header-table row
(`layout/common/test_klt_report.py`, issue #472) on the main side. Nothing
else moved: no job, trigger, permission or pin changed on either side, and
the new step is one more PDK-free unit test of the same class as the
existing ones, so the findings above still hold and the CI table row is
re-pinned for the merged bytes (the hash above supersedes both the second
PR #489 merge's value and main's pre-merge value). CI was read, not
observed to pass here.

All nine listed hashes were re-computed against the final merged tree and
match the tables, including the refreshed `ci.yml` row. The other findings
are unchanged. No simulation, netlisting or layout flow was run for this
re-audit.

## Re-audit for the issue #492 second merge (2026-11-16)

`origin/main` moved again after the issue #492 re-audit above resolved this
branch's first conflict-resolution merge — PR #473 (issue #472) landed on
main carrying the `klt report-runner unit tests` step, and the PR #489
record gained its third-merge section — so the four signoff cascade files
(`repo-hygiene.inventory.md`, `repo-hygiene.generic.json`, `manifest.json`,
`tier-report.json`) conflicted again. The merged tree was re-checked against
the findings above:

- `.github/workflows/ci.yml` changed on the main side only (this branch has
  never edited it): the merged file is byte-identical to `origin/main`'s and
  carries each side's history in full — the #456 report re-point and #472's
  test step — so its table row already names the merged bytes; re-computed
  against the final merged tree, it matches.
- `layout/README.md` did not change on the main side of this merge: the
  merged bytes are exactly the ones the issue #492 re-audit above pinned
  (this branch's recipe restate merged with #502's same-klt paragraph), and
  its row re-computed against the final merged tree matches. The issue #472
  re-audit's "no edit of its own" claim above is scoped to that merge's
  pre-#492 state.
- `repo-hygiene.inventory.md` itself: both sides appended dated re-audit
  sections and both are kept (this branch's issue #492 section and main's
  second/third merge and issue #472 sections, all above); this section is
  the only new prose on the branch side.

The other listed files are unchanged by both sides of this merge; all nine
listed hashes were re-computed against the final merged tree and match the
tables. The other findings are unchanged. The envelope, manifest item 10 and
tier-report citation pins are refreshed for the new inventory bytes. No
simulation, netlisting or layout flow was run for this re-audit.

## Re-audit for the third PR #471 merge (2026-11-16)

`origin/main` moved again after the second PR #471 merge above, and the four
signoff cascade files (`repo-hygiene.inventory.md`, `repo-hygiene.generic.json`,
`manifest.json`, `tier-report.json`) conflicted again. Two listed files changed
in the merge of `origin/main` (at `592292f3`) into `feature/issue-468` and were
re-read against the findings above; their hashes are refreshed in the tables:

- `.github/workflows/ci.yml` (**read** both diffs against the merge base
  `5c051fde`): both sides had edited it — this branch's
  `Negative-control verdict unit tests` step (the issue #468 re-audit above)
  and main's `klt report-runner unit tests` step plus its header-table row
  (the issue #472 / PR #473 merge re-audit above). The merged file carries
  each side's change in full; no job, trigger, permission, concurrency
  setting or pin moved, so the findings above still hold. CI was read,
  not observed to pass here.
- `layout/README.md` (**read** the merged result against both sides): the
  merged file is a disjoint-section union of this branch's #468 `common/`
  listing additions (`git diff origin/main -- layout/README.md` reduces to
  exactly the two #468 listing entries) and main's side — the #458
  facet-table/status-row corrections, #502's same-klt generator comparison
  paragraph and #492's throwaway-environment restate of the pinned-install
  recipe, all recorded in the re-audits above. The audit findings that lean
  on its Status/Regenerating sections still hold.

Every pinned file in both tables was re-hashed against the final merged
tree; the other listed rows are byte-identical to their pins, so those
findings hold. The envelope, manifest item 10 and tier-report citation pins
are refreshed for the new inventory bytes. No simulation, netlisting or
layout flow was run for this re-audit.
