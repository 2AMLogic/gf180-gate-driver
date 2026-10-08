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
| `design-sources.inventory.md`, `testbenches.inventory.md` | The audited inventories items 1 and 9 bind to: every listed source/testbench with its sha256, the regeneration or cold-start command, and what the audit did and did not run. Read the "What was actually run" sections before quoting either `met`. |
| `check_tier_report.py` | The freshness gate run by the `signoff` CI job (and `npm run signoff:check`): anchors every manifest pin to the live tree's sha256, re-runs the grading, and diffs the fresh render against the committed report. Explicit `provenance.input.path` bindings are resolved with the grader's own semantics (string beside the envelope, repo-scoped object from the repo root; a malformed declared path fails, never falls back to `source`), and every `path` + `sha256:` pair an inventory lists is re-hashed. |
| `test_check_tier_report.py` | Stdlib regression tests for the checker (run by the `signoff` CI job): both path forms, malformed/missing/stale/wrong-item cases, `source` unable to redirect a binding, the legacy item-8 rule, compound item 11, inventory hashes. |

## Current graded state: 7/11 met, tier `null` — the honest state

Items **1 (design sources)**, **2 (layout)**, **3 (DRC clean)**, **4 (LVS
clean)**, **8 (characterization report)**, **9 (testbenches shipped)** and
**11 (power delivery, structural)** grade `met`; items **5, 6, 7 and 10**
render `unmet` with a per-item `reason` in `tier-report.json`. Seven of eleven
is not tier T1, and "met" on items 1, 2 and 9 means what the next section
says, no more. An `unmet` row with a `reason` is the machine-readable
statement of the gap (#239).

### Items 1, 2, 9: artifact-bound attestations (issue #288)

Since klayout-tools#2843 (merge `3a75c3ae`), `klt signoff` accepts a `generic`
envelope for items 1, 2, 9 and 10 when it declares `t1_item`, names the audited
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
  generator hashes match the live tree), **not on reproducibility**.
  `layout/README.md` says the generator reproduces the GDS byte for byte;
  re-running it on 2026-10-08 with klt 0.6.0 (both the old and the new pin)
  produced different bytes, and the committed GDS records klt
  `0.3.0+gc27f7eccf49c` on a dirty tree.
- **Item 9** (binds to `testbenches.inventory.md`) — every `sim/` experiment
  is listed with its manifest hash and cold-start invocation. `sim/pdk.json`
  pins the PDK *variant*; the *revision* (open_pdks `c6d73a35…`) is recorded
  per record, not machine-pinned. The report's primary post-layout records
  state they were taken on a dirty working tree. One invocation (the primary
  post-layout testbench, one process/temperature point set) was executed; the
  rest were checked by file existence and `run_corners.py --list`.
- **Item 10 stays `unmet` (`no_evidence`) on purpose.** The item asks for a
  README that states the block, its spec table and how to reproduce every
  result. `README.md` has no reproduction instructions and no spec table (it
  links `spec/gate-driver.md`), and its status line ("schematic capture
  underway; full-schematic PVT corner simulation has not yet started") is
  stale against the post-layout records. Binding CI or a checklist would
  attest a hygiene item the audit does not support. The README fix is
  tracked as #289.

Why the other unmet rows say `no_evidence`:

- **5, 6, 7** — the block has real PVT-corner, Monte-Carlo, and post-layout
  evidence, but as `sim/` markdown records from this repo's own harness —
  not in `klt sim`/`klt yield`/`klt pex` envelope form. Item 7 additionally
  accepts **only** a `klt pex` report for an analog block; a clean DRC or a
  pre-layout sim renders `wrong_kind` by design. Converting a campaign to a
  `klt`-native envelope is a content decision each item's own issue tracks.

**Grading context.** `scope: "repo"` paths are resolved by the grader from the
git repository root, so grading a copy of the tree that has no `.git`
directory renders items 1, 2 and 9 `unmet`. CI's checkout has one.

## Claimant-enforced disclosures (read before quoting a `met`)

`klt signoff` grades, it does not adjudicate everything the checklist's prose
asks for. These are the disclosures the checklist texts make the claimant's
responsibility for the two layout legs:

- **Item 3 (DRC, `20260826-044706-fdf17d9.drc.json`, klt 0.3.0, released deck
  `79e71a1e…`)** — `status: clean`, 0 violations **within the deck's own
  scope**, quoted from the envelope's `coverage` block:
  - `deck_scope` (the DRM chapters the deck transcribes at all): 7.4 Nwell,
    7.5 Comp, 7.7 Poly2, 7.12 Contact, 7.13 Metaln, 7.14 Vian, 7.15
    MetalTop, 9.1 Bond Pad, 10.4.2 MIM Option B, 10.7 DRC_BJT Mark Layer.
  - `layers_in_stream_without_rules` (drawn here, no rule in the deck):
    `12/0`, `31/0`, `32/0`, `36/10`, `49/0`, `110/5`, `117/5`, `117/10`,
    `204/0`.
  - `rules_skipped` (carried by the deck, not evaluated this run):
    `bjt.separation.comp.1`, `metaltop.space.1`, `metaltop.width.1`,
    `pad.enclosing.metal5.1`.
- **Item 4 (LVS, `20260921-154640-86d17b3.lvs.json`, refreshed for this
  manifest under klt 0.5.0+g2b1e55e51bb8 with klayout 0.30.12 — the deck
  revision bundled there, `95c2eb91…`, is unreleased, and
  `provenance.klayout_version_mismatch: true` vs the expected 0.30.10; both
  are recorded in the envelope)** — `status: match`, 2044/2044 devices,
  295/295 nets, 25/25 pins, and:
  - one **warning-only** mismatch (topology: "device class has no counterpart
    on the other side, but no devices of this class were extracted either —
    not a real topology mismatch") — the known finding documented in
    `layout/README.md`;
  - `body_verification.status: "verified"` — body ties were part of the
    compare, not assumed;
  - `power_connectivity.status: "unchecked"`, reason: the reference is
    `plain-element`, whose netlist carries its own power/ground nets in the
    ordinary compare, so the per-standard-cell `power_connectivity` check
    does not apply — a supply-islands claim is item 11's subject (#238),
    not this verdict's.
- Both layout legs pin the same committed GDS:
  `sha256:54f02626…` = `layout/gate_driver_core.gds`.
- **Item 11 (power delivery, structural, `20261001-231815-1ac9445.erc.json`,
  klt 0.6.0+g21b0cc1d6883 at citation time)** — the one **compound** citation in the
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
report was graded with (klayout-tools merge `3a75c3ae…`, #2843); the PyPI
`0.5.0` wheel predates it (it bundles the 10-item tiers doc and lacks the
`source_doc_content_hash` report field, so its render can never match
`tier-report.json`). `jsonschema` is required
because `klt`'s CLI entry imports it eagerly:

```bash
pip install --no-deps "git+https://github.com/2AMLogic/klayout-tools@3a75c3ae705b7ad3803625255de93bcd982e70c6"
pip install 'jsonschema>=4.0'
```

## Grader pin move, 21b0cc1d to 3a75c3ae (issue #288)

Rendered first with the unchanged manifest and compared with the committed
report: no item's `status`, `reason` or `citation` changed. Only report
metadata (`source_doc_content_hash`, `tool.version`, `git_commit`,
`grading_ruleset_id`) and descriptive text (items 6 and 8 `text`, item 11
`notes`) differ. The four added citations were then rendered separately.
