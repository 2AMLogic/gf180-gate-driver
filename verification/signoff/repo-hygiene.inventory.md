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
| README: what the block is, spec table, reproduction | `README.md` | `sha256:98a37e7f59873ffe945b2a18792a2c8f7593cf70f420b006a8d09937d96da12c` |
| License (Apache-2.0) | `LICENSE` | `sha256:cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| Authoritative spec (source of the README's table) | `spec/gate-driver.md` | `sha256:fdc793507cb5d283b2a17b5519570a450016ed65af6b687851ebfaa44e84410c` |
| CI (lint + evidence-record checks, harness self-test, signoff freshness) | `.github/workflows/ci.yml` | `sha256:2df6f0eba0eabddea91efbd723025dc79ddfea7c8d1bcfee7bda8bfcd1d62560` |

Reproduction documents the README links to (read, hashed so a change forces a
re-audit of the links):

| document | sha256 |
|---|---|
| `design/README.md` | `sha256:57077ce9d683d9780c07559db7d28ffcc150d326c338942ad06160ddfc402b54` |
| `sim/README.md` | `sha256:80967abe117347d181575ff00b177e8a203aec5475a66bdd38842cc260097b7d` |
| `sim/harness/README.md` | `sha256:cf7e7a918d7018ac5280d79f2ad6ff59a8d7c508641f83aff1fc088c4bf03eb5` |
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
