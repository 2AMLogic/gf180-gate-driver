# DRC triage: SAB / implant / COMP-coverage violations (issue #358)

`layout/gate_driver_core.gds` is unchanged since the committed `status: clean`
baseline (klt 0.3.0, 18-layer deck). Re-run with klt `0.7.1.dev2599+geaf26f00df36`,
`PDK=gf180mcuD`, deck `gf180mcu` content hash
`sha256:0eb6df1bafc5106ec50bd58479dbd7cda36bb685f1ef18cd3a2244a6e7e48666`
(34 layers), it reports **1513 violations** in 7 rules (report
`layout/drc/reports/gate_driver_core/20261024-075045-f4914d9.drc.json`, arrives
with PR #360). The old verdict never evaluated these rules: the old deck had
no SAB, implant-enclosure or COMP-coverage checks.

## Result: all 7 rules are real layout violations

Each deck threshold was read with `klt deck rules --deck gf180mcu --rule <id>`
and, for the SAB group, compared with the foundry's own KLayout deck
(`libs.tech/klayout/tech/drc/rule_decks/sab.rb` in the installed gf180mcuD PDK),
which implements the same checks. Geometry was measured by loading the
committed GDS with KLayout's `db` module. **No deck/tool defect was found, so no
`2AMLogic/klayout-tools` issue is filed from this triage and no deck
reproduction fixture is needed.**

| Rule (DRM) | Count | Threshold | Measured in the layout | Verdict |
|---|---|---|---|---|
| `poly2.enclosing.sab.1` (SB.10) | 542 | 0.22 um | `res_array` unit resistor: Poly2 `(0,0)-(80840,420)`, SAB `(420,0)-(80420,420)`; SAB is flush with the Poly2 long edges, so side extension is 0 | **real** (foundry `sab.rb` SB.10 is `sab.enclosed(poly_sab, 0.22)` on all edges) |
| `sab.separation.contact.1` (SB.4) | 542 | 0.15 um | Contact `(100,100)-(320,320)` to SAB left edge at x=420: gap 0.10 um | **real** |
| `sab.space.1` (SB.2) | 246 | 0.42 um | SAB rows `(420,0)-(80420,420)` and `(420,820)-(80420,1240)`: gap 0.40 um | **real** |
| `pplus.enclosing.comp.1` (PP.3) | 68 | 0.16 um | tap Pplus rectangle equals the tap COMP footprint (`gen_gate_driver_core.py` `_tap`): enclosure 0 | **real** |
| `nplus.enclosing.comp.1` (NP.3) | 60 | 0.16 um | same, Nplus tap | **real** |
| `pplus.enclosing.comp.far.1` | 20 | 0.02 um | same Pplus tap geometry (rule applies >= 0.429 um from any Nwell/Dnwell) | **real** |
| `comp.coverage.1` | 35 | any Nplus/Pplus | flat top cell: 19138 um^2 of 22186 um^2 COMP has no Nplus/Pplus. The generator draws implants only on body taps (`Nplus` 2.6 um^2 on COMP, `Pplus` 3044 um^2); no transistor source/drain has an implant. Each of the 35 violations is a whole `mos_array` COMP region (e.g. `x1_XMNINV`, `x1_XMPINV`) | **real** |

The 542 / 542 / 246 split for the SAB group is one systematic pattern, not 1513
independent defects: every `ppolyf_u` unit resistor (271 of them) comes from
`klt gen res_array` with the SAB sized to the resistor body, 0.10 um from the
contacts, and rows pitched 0.40 um apart.

## Hypothesis (b) (deck derives implants from markers) is not supported

The generator's `_tap` docstring says implants are drawn only on taps because
a Pplus over an nfet would be read by `klt extract` as a substrate tie. That
reasoning rules out the wrong-polarity implant, not a correct one: an nfet
source/drain takes Nplus (outside Nwell, so not `tap_nplus & active & nwell`)
and a pfet source/drain takes Pplus (inside Nwell, so not `tap_pplus & (active - nwell)`).
Whether adding both survives `klt extract` and LVS is **untested**, and so are
the fixes for the SAB and tap-implant geometry. They are layout work and out of
scope here (tracked in #362); the deck and `spec/` are
not changed.

## Not covered by this triage

The deck still lists the `_MV` rule columns (`DF.6_MV`, `DV.*`, `NW.*_MV`, ...)
as `unmodeled_rules`; the new violations were measured with 3.3 V thresholds
on part of the geometry. A clean re-run after a layout fix would still not be
a medium-voltage signoff.
