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
| `check_tier_report.py` | The freshness gate run by the `signoff` CI job (and `npm run signoff:check`): anchors every manifest pin to the live tree's sha256, re-runs the grading, and diffs the fresh render against the committed report. |

## Current graded state: 3/11 met, tier `null` — the honest state

Items **3 (DRC clean)**, **4 (LVS clean)** and **8 (characterization report)**
grade `met`; everything else renders `unmet` with a per-item `reason` in
`tier-report.json`. Near-all-`unmet` is a correct result, not a failure to
grade (#239): an `unmet` row with a `reason` is exactly the machine-readable
statement of the gap.

Why the unmet rows say `no_evidence`:

- **1, 2, 9, 10** — no `klt` verb backs them (`klt signoff`'s own guidance is
  to leave such items uncited rather than borrow an unrelated passing
  envelope's `met`). The artifacts themselves exist (committed sources and
  netlists, generated GDS with `gate_driver_core.provenance.json`, testbenches
  under `sim/`, README + license + this CI); what does not exist is a
  *grading* verb for them.
- **5, 6, 7** — the block has real PVT-corner, Monte-Carlo, and post-layout
  evidence, but as `sim/` markdown records from this repo's own harness —
  not in `klt sim`/`klt yield`/`klt pex` envelope form. Item 7 additionally
  accepts **only** a `klt pex` report for an analog block; a clean DRC or a
  pre-layout sim renders `wrong_kind` by design. Converting a campaign to a
  `klt`-native envelope is a content decision each item's own issue tracks.
- **11 (power delivery, structural)** — no `klt erc` supply spec or report
  exists yet; tracked in **#238** (the row must exist even while `unmet`).

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

## Refresh procedure

When evidence moves (design, layout, characterization report), the manifest
must move with it, and CI enforces that:

1. Refresh the evidence itself with this repo's own flows —
   `python3 layout/drc/run_drc.py layout/gate_driver_core.gds`,
   `python3 layout/lvs/run_lvs.py layout/gate_driver_core.gds` (append-only
   report records), etc.
2. Update the cited file paths and pinned `content_hash` in `manifest.json`
   (and item 8's envelope + pin if the characterization report changed).
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
report was graded with; the PyPI `0.5.0` wheel predates it (it bundles the
10-item tiers doc and lacks the `source_doc_content_hash` report field, so
its render can never match `tier-report.json`). `jsonschema` is required
because `klt`'s CLI entry imports it eagerly:

```bash
pip install --no-deps "git+https://github.com/2AMLogic/klayout-tools@2b1e55e51bb803c082e8857da44687f3e37ebfc0"
pip install 'jsonschema>=4.0'
```
