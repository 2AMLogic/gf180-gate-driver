# spec

Ratified specs and decision records for this block.

- [`gate-driver.md`](gate-driver.md) — **facet (a)**, the high-voltage
  gate driver: target specification, ratified 2026-08-05: device flavors,
  low-side-only configuration, drive strength and reference load,
  level-shifter topology, and protection scope, each with a decision record
  and PDK-documentation citations.
- [`low-side-power-switch.md`](low-side-power-switch.md) — **facet (b)**,
  the low-side on-die power switch: target specification, ratified
  2026-08-18: cell-referenced `Ron·W` and switch sizing, the EM /
  current-density budget at 1 A per channel (`tm11k` vs. `tm30k`), the
  per-channel OCP and thermal-sense reference structures, and flyback
  handling. Does not amend `gate-driver.md` — the two are facets of one
  shared device base (decision record 0008), not two revisions of one spec.
- [`decision-records/`](decision-records/) — where post-ratification
  decisions land. `gate-driver.md` is the ratified baseline; any later
  decision that extends or fills a gap in it (rather than rewriting its
  text) is recorded here as a numbered, dated decision record instead of a
  silent edit, per `gate-driver.md`'s own amendment rule.
  - [`decision-records/TEMPLATE.md`](decision-records/TEMPLATE.md) — the
    template for a new decision record (ported from
    `2AMLogic/gf180-bandgap`).
  - [`decision-records/0001-block-interface-and-uvlo-parameters.md`](decision-records/0001-block-interface-and-uvlo-parameters.md)
    — ratified 2026-08-08: the block's port list, input electrical spec,
    polarity/enable, UVLO parameters, UVLO output behavior and reference,
    and operating temperature range. Extends `gate-driver.md` §3 and §5.
  - [`decision-records/0008-low-side-power-nmos-facet-scope-and-ronw-baseline.md`](decision-records/0008-low-side-power-nmos-facet-scope-and-ronw-baseline.md)
    — ratified 2026-08-17: scopes a second facet into this repo — direct
    low-side drive of a small load from a single Li-ion cell via an on-die
    `nfet_06v0`, no HV rail — and ratifies a `Ron·W` baseline derived from
    existing `sim/device-mv-fet` evidence. Does not amend `gate-driver.md`;
    the facet's own spec content is deferred to follow-on issues this
    record files.
  - [`decision-records/0009-multichannel-bond-ground-substrate-guidance.md`](decision-records/0009-multichannel-bond-ground-substrate-guidance.md)
    — ratified 2026-08-18: multi-channel guidance for the low-side
    on-die power-NMOS facet (decision record 0008) — bond wire count/sizing
    for N ∈ {1, 2, 4} channels at ~1 A/channel, per-channel dedicated
    `GND_DRV_n` ground return extending decision record 0001's
    `GND_LOGIC`/`GND_DRV` split, and a qualitative substrate-noise-coupling
    treatment for the co-integrated UVLO comparator, with the
    comparator-glitch magnitude question left as an explicit open item
    pending a transistor-level sim. Does not amend `gate-driver.md` or
    decision record 0001.
  - [`decision-records/0010-low-side-power-switch-spec-ronw-em-and-protection.md`](decision-records/0010-low-side-power-switch-spec-ronw-em-and-protection.md)
    — ratified 2026-08-18: creates `low-side-power-switch.md`; replaces
    decision record 0008's stopgap `Ron·W` baseline as facet (b)'s design
    baseline with a purpose-built measurement at the cell-referenced gate
    drive (`Vgs` = 3.6/4.2/5.0 V, full 15-point PVT grid,
    `sim/low-side-power-switch/records/20260818-011754-03afe04.md`);
    ratifies the DRM §14.2 EM/current-density budget at 1 A per channel and
    the per-channel OCP + thermal-sense reference structures. 0008's own
    numbers stay valid as evidence at the bias points they were measured at.
  - [`decision-records/0011-low-side-power-switch-flyback-handling.md`](decision-records/0011-low-side-power-switch-flyback-handling.md)
    — ratified 2026-08-18: facet (b)'s flyback path is a dedicated on-die
    `diode_pd2nw_06v0` clamp (≥ 10⁴ µm²/A), rejecting the implicit
    high-side-PMOS body diode and the synchronous PMOS. Extends
    `low-side-power-switch.md` §5.
