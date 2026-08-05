# gf180-gate-driver

A high-voltage gate driver on the
[gf180mcu](https://github.com/google/gf180mcu-pdk) open PDK, designed by AI
agents driving [klayout-tools](https://github.com/2AMLogic/klayout-tools) and
the open-source xschem + ngspice analog flow.

**Status: just opened, specification phase.** Nothing is designed yet.

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

## Target specification (DRAFT — engineering to ratify, see issue #1)

| Parameter | Target | Stretch |
|---|---|---|
| Supply | 5 V drive rail, 3.3 V logic input | 6 V |
| Configuration | low-side driver | high-side / half-bridge |
| Peak drive current | ≥ 0.5 A source / sink | 1 A |
| Propagation delay | < 50 ns | < 25 ns |
| Rise / fall into 1 nF | < 50 ns | — |
| Shoot-through protection | dead-time control | adaptive |
| Signoff | DRC + LVS clean | — |

Every number above is provisional and exists to be argued with during
ratification. Cross-domain level shifting between the 3.3 V logic and the
5 V drive rail is the design's central problem — say so in the spec rather
than discovering it in layout.

Maturity ladder: spec ratified → schematic simulated across PVT → layout
DRC/LVS-clean → post-layout re-verification → shuttle seat → measured
silicon. **Current position: pre-spec.**

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
