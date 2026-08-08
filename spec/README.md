# spec

Ratified specs and decision records for this block.

- [`gate-driver.md`](gate-driver.md) — target specification, ratified
  2026-08-05: device flavors, low-side-only configuration, drive strength
  and reference load, level-shifter topology, and protection scope, each
  with a decision record and PDK-documentation citations.
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
