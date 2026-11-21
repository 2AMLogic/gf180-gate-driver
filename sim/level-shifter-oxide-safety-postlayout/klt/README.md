# `klt sim` requests for level-shifter-oxide-safety-postlayout (issue #559)

The same oxide-safety bench as `../testbench/` (the level shifter's
thin-oxide gate-excursion, XCCOMP MiM stack, sampled output-ratio and
propagation-delay measurements, against the extracted netlist of
layout/gate_driver_core.gds), restated as `klt sim` requests so the 60-point
matrix can run on the Spot batch fleet instead of a dispatch worker — the
first deliverable of [#558](https://github.com/2AMLogic/gf180-gate-driver/issues/558),
qualifying the batch route on the pre-#510 DUTs before
[#510](https://github.com/2AMLogic/gf180-gate-driver/issues/510) repeats a
header-only extraction change through it. The harness records in `../records/`
are untouched; this route's own records cite the committed envelopes under
`envelopes/` (the #558 citation rule, `sim/README.md`).

| File | What |
|---|---|
| `gen_requests.py` | Emits the two requests (deterministic). Every bound is read from `../testbench/tb.json`'s `checks` at generate time (not re-typed), the nine column names are cross-checked against its `measure` map, and the process axis and `engine`/`models`/`batch`/`options` envelope come from [`sim/harness/klt_request.py`](../../harness/klt_request.py) (`steps_envelope`), shared with the other generators (issue #441). |
| `body.spice`, `body-rc.spice` | Circuit body per DUT: identical stimulus (the harness fragment's 0.5 ns-edge, 40 ns-high, 80 ns-period IN pulse, built from a unit pulse scaled by `v(VDD_LOGIC)` because `supply_v` alters DC sources only), 1 nF reference load and solver options (`gmin=1e-9`, `method=gear`, `reltol=1e-4` as body-level `.options` cards — the batch runner drops `options.ngspice_options`); they differ only in which extracted DUT they `.include` at deck level — `layout/lvs/gate_driver_core.extracted.spice` (no-RC) and `.extracted-rc.spice` (RC). Deck-level inclusion keeps the flat extracted probe names (`x1_inb`, `x1_na`, `x1_nb`, `x1_ncb`, `ANON293`..`ANON295`, `IN_DRV`) addressable, exactly as the harness deck `.include`s the DUT; each run's `environment.netlist_closure` pins the DUT sha256 it actually used. |
| `design.ngspice` | The PDK global-switch include the corner `.lib` sections need, copied so the batch worker can stage it (same copy as the #560 drive facets'). |
| `request-norcx.json` / `request-rc.json` | tt/ff/ss/fs/sf × {−40, 27, 125} °C × 4 tied rail points (2.97/4.5, 3.3/5.0, 3.63/5.5, 3.3/6.0 V) = 60 corners each — the harness grid exactly, no tier split: every `tb.json` check of this facet is tier-independent, so one request per DUT carries all 60 points at the manifest bounds. |

**Why `analysis_steps` and not a plain `analysis`:** the two output ratios
are one `.meas` result divided by another (`v(IN_DRV)` sampled at 59 ns or
19 ns over `v(VDD_DRV)` at 59 ns) — the shape that had no batch-portable
expression before `analysis_steps[]` derived measurements (the gap class
[2AMLogic/klayout-tools#4902](https://github.com/2AMLogic/klayout-tools/issues/4902)
tracks for the scalar-analysis form). Both requests use one `wave`
transient step (`tran 20p 200n`, the harness's own transient) carrying the
three `FIND ... AT=` samples, the two TRIG/TARG delay cards at the harness
fragment's literal 1.65 V / 2.5 V levels, and the waveform reductions
(`vecmax`/`abs` over the six `dq*` thin-oxide differences and four `dvc*`
MiM legs as `intermediate` lets); the nine top-level measurements are the
record columns as derived expressions over `wave.*` — aliases for the
reductions, ns conversions for the delays, and `wave.hi / wave.drv` /
`wave.lo / wave.drv` for the ratios, graded through `limits` exactly as the
harness grades them. No measurement of this facet had to stay on the
harness.

Method differences from the harness bench, all recorded in this facet's
batch-route records:

- the IN pulse is built from a unit pulse scaled by `v(VDD_LOGIC)`
  (`supply_v` alters DC sources only) — identical waveform at every corner;
- `reltol=1e-4`, `gmin=1e-9` and `method=gear` are body-level `.options`
  cards (the batch runner drops `options.ngspice_options`);
- `t_plh`/`t_phl` keep the harness fragment's literal 1.65 V / 2.5 V
  TRIG/TARG levels verbatim (the harness itself uses those fixed levels at
  every rail point), reported as `t_plh_ns`/`t_phl_ns` via a `* 1e9`
  derived expression.

Reproduce (both requests are 60-unit multi-corner runs — they go to the
batch fleet; `capacity_wait_s=1800` is in the shared envelope, and the
whole-job ceiling makes `--hosts 3` the comfortable shard size):

```bash
python3 sim/level-shifter-oxide-safety-postlayout/klt/gen_requests.py
cd sim/level-shifter-oxide-safety-postlayout/klt
mkdir -p envelopes
for r in norcx rc; do
  klt sim --backend batch --hosts 3 --wait-for-capacity 600 \
    --report-out envelopes/<date>-<sha>-klt-sim-oxide-$r.json --format json \
    request-$r.json
done
```

Envelopes are committed append-only under `envelopes/`; a record citing one
still states the GDS sha256 and the DUT sha256 it ran (the latter verified
against the envelope's `environment.netlist_closure`) — the #558 citation
rule.
