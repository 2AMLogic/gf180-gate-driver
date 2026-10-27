# verification/signoff — the block's graded T1 state (issue #239)

This directory is how this block's gap to **T1 sim-validated** is stated from
here on: a [`klt signoff`](https://github.com/2AMLogic/klayout-tools/blob/main/docs/cli/signoff.md)
**block manifest** feeding the mechanical grader, with the graded output
committed beside it — **the verdict of record** (see the gap-to-T1 tracker,
issue #22), replacing the hand-maintained checkbox list in that issue's body.
A hand-read checklist goes stale silently the moment either the evidence or
the checklist itself moves (the 2026-09-17 eleventh item, klayout-tools#2025,
invalidated every prior hand-read in the fleet at a stroke); a manifest is
re-graded by a command, and CI re-grades it on every PR.

## Files

| file | what it is |
|---|---|
| `manifest.json` | The block manifest: `block` / `kind` and, per T1 item, the committed evidence envelope backing it, each pinned to the `content_hash` of the artifact the check actually ran against. Consumed as-is by fleet roll-ups ([2AMLogic/2am#956](https://github.com/2AMLogic/2am/issues/956)). |
| `tier-report.json` | The committed record of `klt signoff --manifest manifest.json --format json` — the graded item table. Regenerate after any evidence/manifest change; `check_tier_report.py` fails CI if it drifts from a fresh render. |
| `gate-driver-characterization.generic.json` | T1 item 8's opt-in `generic` evidence envelope wrapping `design/gate-driver-characterization.md` (the one item that names no `klt` verb). Its `provenance.input.content_hash` pins that report, so editing the report without refreshing this envelope renders the item stale. |
| `design-sources.generic.json`, `layout.generic.json`, `testbenches.generic.json` | The artifact-bound `generic` envelopes for T1 items **1**, **2** and **9** (klayout-tools#2843). Each declares `"t1_item": <n>` and names the audited artifact in `provenance.input.path` (`{"path", "scope": "repo"}`) with its `content_hash`; the manifest pins that same hash. |
| `repo-hygiene.generic.json`, `repo-hygiene.inventory.md` | T1 item **10** (issue #289): the artifact-bound `generic` envelope (`"t1_item": 10`) and the audited inventory it binds to, which lists `README.md`, `LICENSE`, `spec/gate-driver.md`, `.github/workflows/ci.yml` and the reproduction documents with their sha256 values. The manifest pins the inventory's hash. |
| `design-sources.inventory.md`, `testbenches.inventory.md` | The audited inventories items 1 and 9 bind to: every listed source/testbench with its sha256, the regeneration or cold-start command, and what the audit did and did not run. Read the "What was actually run" sections before quoting either `met`. |
| `check_tier_report.py` | The freshness gate run by the `signoff` CI job (and `npm run signoff:check`): anchors every manifest pin to the live tree's sha256, re-runs the grading, and diffs the fresh render against the committed report. Explicit `provenance.input.path` bindings are resolved with the grader's own semantics (string beside the envelope, repo-scoped object from the repo root; a malformed declared path fails, never falls back to `source`), and every `path` + `sha256:` pair an inventory lists is re-hashed. |
| `test_check_tier_report.py` | Stdlib regression tests for the checker (run by the `signoff` CI job): both path forms, malformed/missing/stale/wrong-item cases, `source` unable to redirect a binding, the legacy item-8 rule, compound item 11, inventory hashes. |

## Current graded state: 8/11 met, tier `null` — the honest state

Items **1 (design sources)**, **2 (layout)**, **3 (DRC clean)**, **4 (LVS
clean)**, **8 (characterization report)**, **9 (testbenches shipped)**, **10
(repo hygiene)** and **11 (power delivery, structural)** grade `met`; items
**5, 6 and 7** render `unmet` with a per-item `reason` in
`tier-report.json` (item 5: `check_failed`, see below; 6 and 7: `no_evidence`). Eight of eleven is not tier T1, and "met" on items 1, 2, 9
and 10 means what the next section says, no more. An `unmet` row with a `reason` is the machine-readable
statement of the gap (#239).

### Items 1, 2, 9, 10: artifact-bound attestations (issues #288, #289)

Since klayout-tools#2843 (merge `3a75c3ae`), `klt signoff` accepts a `generic`
envelope for items 1, 2, 9 and 10 (the last bound by #289) when it declares `t1_item`, names the audited
artifact in `provenance.input.path` with its `content_hash`, the manifest pins
the same hash, and the grader re-hashes the artifact
(`citation.artifact_binding.input_verified: true`). **That binds bytes, not
truth.** The grader does not regenerate a schematic, re-run a simulation or
re-audit a list; it proves the attestation names exactly these bytes and
turns `unmet` if they change. What each audit found:

- **Item 1** (binds to `design-sources.inventory.md`) — all four cells were
  re-netlisted with xschem 3.4.4 in a scratch export. Device lines and
  instantiated `.subckt` lines equal the committed netlists, but the files are
  **not byte-identical** (line wrapping, header blocks, a commented `**.subckt`
  port order, and `output_stage.spice`'s trailing `.end`). `.sym` files were
  not regenerated.
- **Item 2** (binds to `layout/gate_driver_core.gds`, the bytes items 3, 4 and
  11 already pin) — attested on **documented provenance**
  (`layout/gate_driver_core.provenance.json`: layout, source-netlist and
  generator hashes match the live tree) and, since issue #362, on
  **reproducibility**: re-running the generator with klt
  `0.7.1.dev2599+geaf26f00df36` into a scratch directory reproduced the
  committed bytes exactly (`cmp` identical, 2026-10-24). The previous GDS did
  not reproduce under later klt builds (2026-10-08, klt 0.6.0) and recorded
  klt `0.3.0+gc27f7eccf49c` on a dirty tree. The claim is tied to that klt
  build: a different `klt gen` can change the cells (as 0.3.0 → 0.7.1 did).
- **Item 9** (binds to `testbenches.inventory.md`) — every `sim/` experiment
  is listed with its manifest hash and cold-start invocation. `sim/pdk.json`
  pins the PDK *variant*; the *revision* (open_pdks `c6d73a35…`) is recorded
  per record, not machine-pinned. The report's primary post-layout records
  state they were taken on a dirty working tree. One invocation (the primary
  post-layout testbench, one process/temperature point set) was executed; the
  rest were checked by file existence and `run_corners.py --list`.
- **Item 10** (binds to `repo-hygiene.inventory.md`, issue #289) — the audit
  found `README.md` now states the block, carries the section 3 target/stretch
  table (hand-transcribed from `spec/gate-driver.md`, which stays
  authoritative; targets, not measured results) and gives root-relative
  reproduction instructions that separate validating committed evidence from
  generating new evidence; `LICENSE` is Apache-2.0; `.github/workflows/ci.yml`
  runs lint with evidence-record checks, the harness self-test and this
  signoff gate. The audit **read** those files and **executed** only
  `run_corners.py --check-env`/`--list`, `sim/check_records.py` and `npm run
  lint`; it did not re-run any simulation, netlisting or layout flow, did not
  observe CI run, and the README's "generate new evidence" commands were
  taken from the linked project documents, not exercised. Editing the
  README, license, spec, CI or a linked reproduction document without
  re-auditing and refreshing the inventory, envelope, manifest and report
  fails `check_tier_report.py`. Known gaps the README discloses: the layout
  GDS regeneration limitation above, and `sim/README.md`'s facet table
  omitting four on-disk experiments (`testbenches.inventory.md` is complete).

### Item 5: `klt sim` corner envelopes (issue #367)

Item 5 cites two `klt sim` envelopes, committed append-only under
`sim/gate-driver-core-drive-with-uvlo/klt/envelopes/`, from the **re-run
route** (nothing re-expressed from the old records): the schematic DUT
`design/netlist/gate_driver_core.spice` (sha256 `1d442503…`, pinned in each
envelope's `environment.netlist_closure`) at the 45-point ±10 % tied-rail
matrix (`…-nominal-rail.json`, ratified *target* bounds) and the 15-point
6 V stretch rail (`…-stretch-rail.json`, ratified *stretch* bounds for
current and propagation delay; rise/fall keep their only bound). Both ran on
the Spot batch fleet; the requests and the generator that emits them are in
`sim/gate-driver-core-drive-with-uvlo/klt/` (`gen_requests.py`, `body.spice`).
The rows are `peak_source_current`, `peak_sink_current`, `propagation_delay`
and `rise_fall_time` (each measurement carries its `spec_row` tag); `drive_rail`
and `uvlo` are declared `gap`s with their reasons in `manifest.json`.

Item 5 renders **`unmet`/`check_failed`, and that is the true result, not a
tooling problem**: no bound was relaxed and the ratified exceptions are not
encoded, so they fail in the envelopes exactly as the spec says they do.

- Stretch rail: `ipeak_sink_a` < 1 A at `ss_125c` (0.8776 A) and `sf_125c`
  (0.9221 A) — decision record 0016's two corners; 13/15 pass.
- Nominal rail: `ss_-40c_vlogic2p97v-vdrv4p50v` fails `ipeak_source_a`
  (0.49944 A < 0.5 A, decision record 0020's corner), and **two** corners at
  that low-line point are UVLO-locked so OUT never reaches 90 % and the
  rise/fall/propagation measurements produce no value: that `ss_-40c` corner
  and `sf_-40c` (0.69 A source, 0.91 A sink; its thresholds are not
  reached either). The harness record scored the locked `ss_-40c` point with
  swing-relative thresholds on a 0.24 V glitch; these envelopes use
  rail-normalised 10/50/90 % crossings, so a block that never switches reports
  *no value* rather than a flattering delay. The `sf_-40c` locked point has
  no ratified exception: it is a new observation of the open UVLO false-trip
  finding (spec §5, decision record 0018) at a second corner.
- 43/45 nominal corners pass every graded row; 13/15 stretch corners do.

Method differences from the harness bench (`testbench/tb.json`): thresholds
are on rail-normalised monitors rather than min/max-swing vectors, the IN
pulse is built from a unit pulse scaled by `v(VDD_LOGIC)` (`supply_v` alters
DC sources only), `reltol=1e-4` is a body-level `.options` card (the fleet
runner drops `options.ngspice_options`), and the inherited sanity bands
(`n*_min_v ≥ −50 mV` etc.) are not re-asserted — they are not §3 rows and the
harness records still carry them. `drive_rail`/`uvlo` stay gaps, so even a
clean re-run would grade `partial_coverage` until those are expressed.

The grader pin moved to `879d39ba` for this: `3a75c3ae` grades the
multi-envelope list + `spec_rows` form `invalid_evidence`. Re-rendered with the
new pin, no other item's `status`/`reason` changed (only report metadata and
descriptive text).

Why items 6 and 7 still say `no_evidence`:

- **6, 7** — the block has real Monte-Carlo and post-layout
  evidence, but as `sim/` markdown records from this repo's own harness —
  not in `klt yield`/`klt pex` envelope form. Item 7 additionally
  accepts **only** a `klt pex` report for an analog block; a clean DRC or a
  pre-layout sim renders `wrong_kind` by design. Converting a campaign to a
  `klt`-native envelope is a content decision each item's own issue tracks.

**Grading context.** `scope: "repo"` paths are resolved by the grader from the
git repository root, so grading a copy of the tree that has no `.git`
directory renders items 1, 2, 9 and 10 `unmet`. CI's checkout has one.

## Claimant-enforced disclosures (read before quoting a `met`)

`klt signoff` grades, it does not adjudicate everything the checklist's prose
asks for. These are the disclosures the checklist texts make the claimant's
responsibility for the two layout legs:

- **Item 3 (DRC, `20261024-090822-de97a29.drc.json`, klt
  `0.7.1.dev2599+geaf26f00df36`, klayout 0.30.12, unreleased deck
  `0eb6df1b…`, 34 layers)** — `status: clean`, 0 violations **within the
  deck's own scope** (issue #362; the earlier 18-layer-deck `clean` report
  `20260826-044706-fdf17d9` and #358's 1513-violation report stay in
  `layout/drc/reports/` as append-only history), quoted from the envelope's
  `coverage` block:
  - `deck_scope` (the DRM chapters the deck transcribes at all): 7.4 Nwell,
    7.5 Comp, 7.7 Poly2, 7.8 Nplus, 7.9 Pplus, 7.12 Contact, 7.13 Metaln, 7.14
    Vian, 7.15 MetalTop, 9.1 Bond Pad, 10.4.2 MIM Option B, 10.7 DRC_BJT Mark
    Layer, plus the ESD, GR, OFFGRID and SB (SAB) groups.
  - `layers_in_stream_without_rules` (drawn here, no rule in the deck):
    `36/10`.
  - `unmodeled_rules`: the `_MV` columns (`DF.6_MV`, `DV.*`, `NW.*_MV`,
    `LPW.*_MV`, `PL.*_MV`, …) are not transcribed, so 3.3 V thresholds apply
    to thick-oxide geometry: **this is not a medium-voltage DRC signoff.**
  - `rules_skipped`: 27 rules the deck carries that have no applicable
    geometry in this layout (`inapplicable`, reason `no_applicable_geometry`).
- **Item 4 (LVS, `20261024-090826-de97a29.lvs.json`, same klt/klayout/deck
  as item 3)** — `status: match`, 2044/2044 devices, 295/295 nets, 25/25 pins,
  and:
  - three **warning-only** findings (two `device.geometry_not_compared`
    notes for the capacitor and resistor classes, whose geometry parameters
    KLayout compares as secondary, and one topology note: "device class has no
    counterpart on the other side, but no devices of this class were extracted
    either — not a real topology mismatch") — the same three as the pre-#362
    run `20261024-075048-f4914d9`;
  - `body_verification.status: "verified"` — body ties were part of the
    compare, not assumed;
  - `power_connectivity.status: "unchecked"`, reason: the reference is
    `plain-element`, whose netlist carries its own power/ground nets in the
    ordinary compare, so the per-standard-cell `power_connectivity` check
    does not apply — a supply-islands claim is item 11's subject (#238),
    not this verdict's.
- Both layout legs pin the same committed GDS:
  `sha256:15fa5b64…` = `layout/gate_driver_core.gds` (regenerated by issue
  #362).
- **Item 11 (power delivery, structural, `20261024-090832-de97a29.erc.json`,
  klt 0.7.1.dev2599+geaf26f00df36)** — the one **compound** citation in the
  manifest (a list, because no single artifact proves this item): the `erc`
  envelope plus the item-4 LVS report above as the supply-continuity half.
  The `erc_status: clean` verdict rests on the `ties[]` declaration #256
  added to `layout/erc-supply-spec.json` — all four well/substrate classes
  grade `checked` with none `skipped` and zero `erc.missing_tie` — and the
  citation itself discloses which ties rested on the caller's word about
  the well side: `ties_checked_by_well_assertion` names the
  native-substrate tie (`well_layer: null` + `well_boxes`, the
  klayout-tools#2255 form). Quote that list beside any `met` claim; the
  item-4 disclosures above apply to the LVS half.

## Refresh procedure

When evidence moves (design, layout, characterization report), the manifest
must move with it, and CI enforces that:

1. Refresh the evidence itself with this repo's own flows —
   `python3 layout/drc/run_drc.py layout/gate_driver_core.gds`,
   `python3 layout/lvs/run_lvs.py layout/gate_driver_core.gds` (append-only
   report records), etc.
2. Update the cited file paths and pinned `content_hash` in `manifest.json`
   (and item 8's envelope + pin if the characterization report changed). For
   items 1, 2 and 9, re-audit the inventory first (an edit to any listed
   schematic, netlist, `tb.json`, `sim/pdk.json` or the GDS fails
   `check_tier_report.py` until the inventory and its envelope's
   `provenance.input.content_hash` are refreshed).
3. Regenerate the committed record:

   ```bash
   klt signoff --manifest verification/signoff/manifest.json --format json \
     > verification/signoff/tier-report.json
   ```

4. `python3 verification/signoff/check_tier_report.py` locally (CI reruns it):

   ```bash
   npm run signoff:check
   ```

`klt` install for grading-only (no klayout, no PDK — this is what the
`signoff` CI job does). The pin is the exact source commit the committed
report was graded with (klayout-tools merge `879d39ba…`, moved from `3a75c3ae…` by issue #367); the PyPI
`0.5.0` wheel predates it (it bundles the 10-item tiers doc and lacks the
`source_doc_content_hash` report field, so its render can never match
`tier-report.json`). `jsonschema` is required
because `klt`'s CLI entry imports it eagerly:

```bash
pip install --no-deps "git+https://github.com/2AMLogic/klayout-tools@879d39bad82b67abbcc02e482a2c05f17140d18e"
pip install 'jsonschema>=4.0'
```

## Grader pin move, 21b0cc1d to 3a75c3ae (issue #288)

Rendered first with the unchanged manifest and compared with the committed
report: no item's `status`, `reason` or `citation` changed. Only report
metadata (`source_doc_content_hash`, `tool.version`, `git_commit`,
`grading_ruleset_id`) and descriptive text (items 6 and 8 `text`, item 11
`notes`) differ. The four added citations were then rendered separately.
