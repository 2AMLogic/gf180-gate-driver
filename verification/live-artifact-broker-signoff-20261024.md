# Live artifact-broker verification of the signoff writers (#353)

Append-only evidence note. #352 verified the writers only against an emulated
`klt artifact put`; this records one run of each against the real broker and
PDK-backed `klt`. No writer code was changed.

## Environment

| | |
|---|---|
| Date / commit | 2026-10-24, `f4914d9` (main) |
| `klt --version` | `klt 0.7.1.dev2599+geaf26f00df36` (klayout 0.30.12) |
| PDK | `PDK=gf180mcuD` (`klt pdk find`: open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, root `~/.ciel`); corner N/A (DRC/LVS/ERC/PEX are not corner-dependent) |
| Broker | host `loom-fleet-captain:14351` (`$KLT_ARTIFACT_BROKER`) |
| Input | `layout/gate_driver_core.gds` |

## Results

| Writer | Exit | Verdict | Manifest |
|---|---|---|---|
| `layout/drc/run_drc.py` | 0 | **`violations`, 1513** (committed baseline: `clean`, klt 0.3.0) | `layout-drc-gate_driver_core-20261024-075045-f4914d9` |
| `layout/lvs/run_lvs.py` | 0 | `match`, 2044/2044 devices, 295/295 nets, mismatch_count 3 | `layout-lvs-gate_driver_core-20261024-075048-f4914d9` |
| `layout/erc/run_erc.py` | 0 | `clean`, 0 findings | `layout-erc-gate_driver_core-20261024-075053-f4914d9` |
| `layout/lvs/run_pex_extract.py` | 0 | extract stored | `layout-pex-gate_driver_core-20261024-075109-f4914d9` |
| `layout/lvs/lvs_negative_control.py` | **1** | control assertion failed (see below); manifest still written | `layout-lvs-negative-control-20261024-075111-f4914d9` |
| `layout/erc/erc_negative_control.py` | 0 | ok (3 manifests: `no-deck`, `deck-clean`, `phantom-supply`) | `layout-erc-negative-control-*-20261024-0751{15,17,19}-f4914d9` |
| `layout/drc/deck_negative_control.py` | 0 | ok, flags `metal1.space.1` x1; **it does store output**, so it is in scope | `layout-drc-deck-negative-control-20261024-075122-f4914d9` |

`klt artifact get <manifest>#<name>` was run for every entry of every manifest
above (21 entries): each returned bytes whose sha256 equals the manifest entry.
`python3 scripts/check_artifact_manifests.py check --tree HEAD` on the committed tree: OK (10 manifests, 25 entries, schema valid, no stored bytes committed).

## Findings (not fixed here)

1. **DRC no longer clean under the current klt/deck.** 1513 violations:
   `poly2.enclosing.sab.1` 542, `sab.separation.contact.1` 542, `sab.space.1`
   246, `pplus.enclosing.comp.1` 68, `nplus.enclosing.comp.1` 60,
   `comp.coverage.1` 35, `pplus.enclosing.comp.far.1` 20. The deck is
   unreleased (`released: false`, content hash `0eb6df1b...`) and covers 34
   layers vs 18 in the 2026-08-26 clean baseline (klt 0.3.0), so the newer deck
   adds SAB/COMP/implant rules the layout was never checked against. The
   committed `clean` claim in `layout/README.md` is therefore deck-scope
   dependent; it is not relaxed here.
2. **`lvs_negative_control.py` fails its own assertion** (`expected 1772
   reference devices after the drop, got 2043`). The comparator did notice the
   drop (`status: mismatch`, mismatch_count 5); the script's expected count
   (transistor cards only) disagrees with klt's total device count (2043 = 2044
   - 1, including the 4 MiM caps and 271 resistors).
3. `klt pdk find` warned that no PDK variant was selected and defaulted to
   `gf180mcuA`; the runs above set `PDK=gf180mcuD` explicitly.
