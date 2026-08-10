# gf180-gate-driver — agent instructions

Open-source canary block: a high-voltage gate driver on the gf180mcu PDK,
designed and verified by AI agents.

- **PDK**: gf180mcu (open PDK). Open-source flow: xschem + ngspice for
  design/sim, klayout-tools (`klt`) for layout work.
- **The medium-voltage devices are the point.** This is the first block in the
  program to use the 5 V / 6 V flavors rather than the 3.3 V ones. Device
  models, rules, and extraction behavior in that regime are untested by these
  tools. When something behaves oddly, suspect the tool or the deck before
  the circuit, and file it.
- **Cross-domain level shifting is the central design problem** — 3.3 V logic
  in, 5 V drive rail out. Treat it as a first-class part of the spec, not an
  implementation detail discovered during layout.
- **Friction protocol (the canary's job)**: every time klayout-tools is
  awkward, missing a capability, or wrong for what you need, file an issue at
  `2AMLogic/klayout-tools` describing the tool gap generically — that tracker
  is scoped to the tool, so keep design-specific detail out of it and describe
  the gap, not the design.
- **Verification is the product**: no claim without a testbench. PVT corners
  on every recorded result; `sim/` results are append-only evidence.
- Spec changes go through `spec/` with a decision record; agents do not relax
  the ratified spec to make results pass.
- Harness bootstrap: copy the sim-harness pattern from
  `2AMLogic/gf180-bandgap` rather than reinventing it.

## Not a CAN transceiver

A CAN transceiver was considered for this slot and rejected: ISO 11898-2
requires roughly ±12 V bus common-mode range and fault tolerance beyond what
6 V devices provide. If work here establishes what the gf180mcu HV devices
can actually withstand, record it in `spec/` — that answer is what a future
CAN or LIN block would be built on.

<!-- BEGIN LOOM ORCHESTRATION -->
This repository uses [Loom](https://github.com/rjwalters/loom) for AI-powered development orchestration — see the Loom repository for the full guide (roles, labels, worktrees, configuration). When installed, Loom also writes a locally-substituted copy of that guide to `.loom/CLAUDE.md`.
<!-- END LOOM ORCHESTRATION -->

<!-- BEGIN REPO-SKILLS -->
This repository has [Repo Skills](https://github.com/rjwalters/repo) v0.10.0 installed —
general repository hygiene and environment commands invoked as `/repo:<command>`. Run
`/repo:help` for the command list, or see `.claude/skills/repo/SKILL.md` for the full
guide. Hygiene commands apply safe, reversible fixes by default and report each
change; run with `--ask` to review first, and `--prune` to allow irreversible
removals. Managed by `install.sh` — edit outside the markers only.
<!-- END REPO-SKILLS -->
