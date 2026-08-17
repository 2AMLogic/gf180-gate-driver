# gf180-gate-driver

A high-voltage gate driver on the
[gf180mcu](https://github.com/google/gf180mcu-pdk) open PDK, designed by AI
agents driving [klayout-tools](https://github.com/2AMLogic/klayout-tools) and
the open-source xschem + ngspice analog flow.

**Status: spec ratified, schematic capture underway.** See [Target
specification](#target-specification) below.

**Built agent-native.** Every specification, decision record, testbench, and
line of documentation here is produced by AI agents working from a ratified
spec and an append-only evidence trail — not human-authored work that agents
merely assisted with. Verification is the product: every claim traces to a
recorded result under PVT corners. Where the agents hit friction with the
open-source tooling — most often
[klayout-tools](https://github.com/2AMLogic/klayout-tools) — that friction is
filed as a public issue against the tool itself, so the fix benefits everyone
using gf180mcu, not just this repo.

## Why this block

gf180mcu is a 3.3 V / 5 V / 6 V process, and every sibling canary uses only
the 3.3 V devices. This block is the first to work in the medium-voltage
flavors, which means the tools meet a set of device models, rules, and
extraction behavior they have not yet been exercised against.

A gate driver was chosen over a CAN transceiver for that job deliberately.
ISO 11898-2 demands roughly ±12 V bus common-mode range and fault tolerance
well beyond 6 V, so a CAN block risks dead-ending on device limits before it
produces much useful work. A gate driver exercises the same device flavors
without that risk, belongs to a real mature-node category (motor and power
control), and carries no standards-body entanglement.

## Target specification

See [`spec/gate-driver.md`](spec/gate-driver.md), ratified 2026-08-05 —
device flavors (with PDK electrical specs cited), low-side-only
configuration, drive strength and reference load, level-shifter topology,
and protection scope, each recorded as a decision with alternatives
considered.

Maturity ladder: spec ratified → schematic simulated across PVT → layout
DRC/LVS-clean → post-layout re-verification → shuttle seat → measured
silicon. **Current position: spec ratified, schematic capture underway**
(level shifter and low-side output stage captured and sized; full-schematic
PVT corner simulation has not yet started).

## Two facets, one shared device base

This repo scopes **two** distinct power-driver use cases on the same
gf180mcu medium-voltage devices, per
[decision record 0008](spec/decision-records/0008-low-side-power-nmos-facet-scope-and-ronw-baseline.md):

- **(a) High-voltage gate driver** (the block above) — an external-FET
  pattern: 3.3 V logic in, level-shifted to a 5–6 V drive rail that sources
  and sinks gate charge into an off-die power switch. This is the ratified
  spec (`spec/gate-driver.md`).
- **(b) Low-side on-die power-NMOS facet** (new) — direct low-side drive of
  a small load (motor/solenoid/LED) straight from a single Li-ion cell,
  where the switch is an **on-die** thick-oxide `nfet_06v0`, `Vgs` is the
  cell's own 3.6–5 V range, and there is no HV rail and no level shifter.
  This facet is **in scope in this repo, not a sibling one** — the device
  characterization it needs (`Ron`, `Vt`, `Ioff`, thermal behavior of the
  same `nfet_06v0`/`pfet_06v0` devices) is already being produced here for
  facet (a)'s output stage. Decision record 0008 records the scope decision
  and a `Ron·W` baseline derived from existing `sim/device-mv-fet` evidence;
  the rest of this facet's spec content (EM/current-density guidance,
  per-channel OCP/thermal-shutdown structures, flyback options, a
  shared-shuttle test-structure plan, multi-channel bond/ground guidance) is
  deferred to follow-on issues referenced from that record.

## Repo layout

```
spec/          ratified spec + decision records
design/        schematics / netlists (xschem)
sim/           testbenches + PVT corner results (ngspice)
layout/        GDS + DRC/LVS reports (klayout-tools driven)
measurements/  silicon characterization (empty until tape-out)
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
