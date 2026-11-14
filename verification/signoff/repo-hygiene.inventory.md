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
| README: what the block is, spec table, reproduction | `README.md` | `sha256:1142f2042b5802f9b363dc831d4274f49556621e0712be52cca265caab8a61c9` |
| License (Apache-2.0) | `LICENSE` | `sha256:cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| Authoritative spec (source of the README's table) | `spec/gate-driver.md` | `sha256:fdc793507cb5d283b2a17b5519570a450016ed65af6b687851ebfaa44e84410c` |
| CI (lint + evidence-record checks, harness self-test, signoff freshness) | `.github/workflows/ci.yml` | `sha256:a21c8825ac5e1fa711074f8bb0d5bd834d5e81674d7f06de991a00adb1058db2` |

Reproduction documents the README links to (read, hashed so a change forces a
re-audit of the links):

| document | sha256 |
|---|---|
| `design/README.md` | `sha256:57077ce9d683d9780c07559db7d28ffcc150d326c338942ad06160ddfc402b54` |
| `sim/README.md` | `sha256:c7364e64721184a28c4857aaa684c432d810845491c095c93731ec5d9ea91242` |
| `sim/harness/README.md` | `sha256:620e74b19d0bee9a5895dcb86fd48c923d913ae1d80a1d5705add7943a225edb` |
| `layout/README.md` | `sha256:62c0849311b0452ab758c4ceb9437fd30c6c5b027a0f07566cc8047a6718166a` |
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
  Monte Carlo scripts, and links the documents hashed above. It discloses that
  `sim/README.md`'s facet table omits four on-disk experiments (the complete
  list is `testbenches.inventory.md`) and the layout-regeneration
  byte-identity limitation recorded in `verification/signoff/README.md`.
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
  (see `verification/signoff/README.md`); `layout/README.md`'s "Post-layout
  simulation" status row is stale against the committed complete-block
  post-layout records (not edited by this issue); cited post-layout records
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
