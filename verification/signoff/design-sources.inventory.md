# Design-source inventory (T1 item 1)

Bound by `design-sources.generic.json` (T1 item 1). Audited 2026-10-08
(issue #288) against commit `f72b363`. `klt signoff` hashes **this file's
bytes**; it does not regenerate schematics and does not read the files
listed below. The per-file sha256 values are checked against the live tree by
`check_tier_report.py`, so editing a listed source without refreshing this
inventory fails CI.

## Sources and derived netlists

| role | file | sha256 (live bytes at audit) |
|---|---|---|
| schematic (top) | `design/gate_driver_core.sch` | `sha256:ff3f8603f6598d0e2f0d50fc6d2edf15a47abe11e6a766fde1decddc7c8cbb42` |
| schematic | `design/level_shifter.sch` | `sha256:cc8bf6356e89b897cc6dcbb016b6ce9876e793b4d0457cb05838b46e6d483ae8` |
| schematic | `design/output_stage.sch` | `sha256:2861f68b782239d9ea6fdc9c0ceb4360db8801ba4c99490c556c0cda0097d870` |
| schematic | `design/uvlo.sch` | `sha256:d5a017a4057b3670f8b0af4cb56c1b79dc008aff17e06fd1d9bfde055d691f2f` |
| symbol (top) | `design/gate_driver_core.sym` | `sha256:847d8c33f9f59cf9d5abaa07aeca7b5691567d86c02dc69c42c603014d0713ed` |
| symbol | `design/level_shifter.sym` | `sha256:1d5eb2d3b25e90cc11992cbc9131c2b76a07a86ebd6a3fe73ef8083fab421eb2` |
| symbol | `design/output_stage.sym` | `sha256:55b5631a2dfc576fccac0c62e55d8ed6f4ee2edb3a9e5899e1973aaa6f67a9f4` |
| symbol | `design/uvlo.sym` | `sha256:d451f495d2204db097e0fb0ed3cf32bb3fb55aa2a4464d8b013e44102ba7811d` |
| xschem config | `design/xschemrc` | `sha256:7721ee3139032583ba2ade5fb7f83341a64fb7b55664d5c45b58b7a51e7e22d8` |
| derived netlist (top, hierarchical) | `design/netlist/gate_driver_core.spice` | `sha256:1d44250367d95eaa935645036a80f682c2e31770f908b90b46b9cc7c26dcb83c` |
| derived netlist | `design/netlist/level_shifter.spice` | `sha256:bbb83347cd68bdfd05f8457a27b5ee9fb5dd23b498a907d042c2acdaf53917b4` |
| derived netlist | `design/netlist/output_stage.spice` | `sha256:0e4ca05ce6e241571965fb960d04ffe1b6096d2c806b2918eb994a09ef771c92` |
| derived netlist | `design/netlist/uvlo.spice` | `sha256:dcb299ea7da685ccc42c7fbb3ebbdcd3858626d676bf944ca815689fbb352d41` |

`design/README.md` mentions a `design/symbols/` directory for hand-authored
device symbols; there are none, and the directory does not exist in the tree.

## Regeneration command (from `design/README.md`)

```bash
source sim/env.sh
xschem --rcfile design/xschemrc -x -q -n -s -o design/netlist design/<cell>.sch
grep -v -e '^\*\* sch_path:' -e '^\*\* sym_path:' -e '^\.end$' \
  design/netlist/<cell>.spice > /tmp/nl && mv /tmp/nl design/netlist/<cell>.spice
# then re-add the hand-written header comment block
```

`<cell>` is each of `gate_driver_core`, `level_shifter`, `output_stage`,
`uvlo`.

## What was actually run in this audit

On a scratch export of the tree (not the working checkout), with xschem 3.4.4
and the gf180mcuD PDK (open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`),
all four cells were netlisted with the command above (written to a scratch
directory) and compared with the committed netlists after joining `+`
continuation lines and collapsing whitespace, ignoring the hand-written `*`
header blocks.

- **Device lines and real `.subckt`/`.ends` lines: identical** for all four
  cells (54, 18, 14 and 17 non-comment lines compared for
  `gate_driver_core`, `level_shifter`, `output_stage`, `uvlo`).
- **Not byte-identical.** Line wrapping of long device lines differs between
  the committed files and this xschem build, and the committed files carry
  the hand-written header block, so a byte diff is non-empty. The equivalence
  above is semantic, not textual.
- **Differences found, all outside device content:**
  - the commented `**.subckt` banner of `gate_driver_core`, `output_stage` and
    `uvlo` lists the ports in a different order than the committed file (a
    `**` comment line; the instantiated `.subckt` lines inside
    `gate_driver_core.spice` match exactly);
  - the committed `design/netlist/output_stage.spice` keeps a trailing
    `.end`, which `design/README.md` says to strip.
- **Not regenerated:** the `.sym` files (`make_sym.awk`, see
  `design/README.md`) and `design/xschemrc` are committed sources listed for
  completeness. They were not regenerated or re-derived here.
