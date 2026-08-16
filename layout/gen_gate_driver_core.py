#!/usr/bin/env python3
"""Generate the ``gate_driver_core`` physical layout from its committed netlist.

This is the *reproducible provenance* for ``layout/gate_driver_core.gds``: the
GDS in this directory is not hand-drawn, it is the output of running this
script against ``design/netlist/gate_driver_core.spice`` and the gf180mcu PDK.

    python3 layout/gen_gate_driver_core.py            # writes layout/gate_driver_core.gds
    python3 layout/gen_gate_driver_core.py --out-dir /tmp/x   # scratch run

Flow (all geometry is produced by `klt`, per the repo's stated tooling -- this
script never links klayout itself and needs nothing but the standard library):

1.  Parse ``design/netlist/gate_driver_core.spice`` and flatten the two
    sub-cells (``level_shifter`` x1, ``output_stage`` x2) into one device list
    with top-level net names.
2.  ``klt gen mos_array`` once per netlist device. A netlist device with
    ``m=M`` is drawn as a single ``1x1`` unit device folded into ``M`` parallel
    gate fingers (``finger_topology: "parallel"``), which is exactly ``M``
    parallel transistors of width ``W`` sharing one source/drain/gate strap --
    the same thing ``m=M`` means in SPICE, and what ``klt extract`` reads back.
3.  ``klt draw`` once for the interconnect/marker cell: the Metal2 net rails,
    the Metal1 device stubs and gate routes, the Via1 stack between them, the
    net-name labels, and the two voltage-domain marker regions
    (``DNWELL``/``LVPWELL`` over the 5V/6V group, ``Dualgate`` over the same).
4.  ``klt gen-compose`` (``placement.strategy: "explicit"``) merges every
    device cell plus the interconnect cell into one ``gate_driver_core`` top
    cell at the origins this script computed.

Floorplan
---------

Every device is a left-aligned horizontal strip; strips stack upward in
netlist order, thin-oxide (3.3V logic) group first, then a domain gap, then
the thick-oxide (5V/6V drive) group.  ``klt gen``'s ``mos_array`` reports the
source pad on a strip's left edge (facing 180), the drain pad on its right
edge (facing 0) and the gate pad on its top edge (facing 90), so:

* net rails run vertically on **Metal2**, in a channel to the left of the
  strips (sources + gates) and a channel to their right (drains);
* a **Metal1** stub runs horizontally out of each pad to its rail and drops a
  **Via1** there; a gate route goes up out of the strip, then horizontally
  through the empty channel above it to the left rail;
* each net's left and right rail are tied together by one horizontal Metal1
  jumper in a cross-over band above the whole stack.

Metal1 stubs therefore cross *under* unrelated Metal2 rails with no via, which
is what keeps a purely orthogonal, no-router wiring scheme short-free.

Known limitations of this first-cut layout (deliberately not fixed here -- see
``layout/README.md`` and issue #105, which owns DRC/LVS closure):

* No well/substrate taps, no guard ring around ``DNWELL_DRV``.  A closed tap
  ring around the drive domain has to be cut for every signal crossing the
  domain boundary, which is a routing plan, not a marker rectangle.
* Device aspect ratios are whatever ``m`` folds into a single row.
* Not DRC-clean and not LVS-clean; ``klt drc`` has never been run on it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

# --------------------------------------------------------------------------- #
# Repo layout
# --------------------------------------------------------------------------- #

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
NETLIST_PATH = os.path.join(REPO_ROOT, "design", "netlist", "gate_driver_core.spice")

TOP_CELL = "gate_driver_core"
DEFAULT_PDK = "gf180mcuD"

# --------------------------------------------------------------------------- #
# gf180mcu drawing layers used by the interconnect cell.
#
# Every number below is the gf180mcu PDK's own, cross-checked against
# $PDK_ROOT/$PDK/libs.tech/klayout/{drc,lvs}/rule_decks/layers_def*.
# The Metal1/Metal2/Via1 triple matches the roles `klt gen`'s own generators
# draw on (`metal`/`metal2`/`via1`), so a stub lands on the same layer as the
# device pad it starts from.
# --------------------------------------------------------------------------- #

L_DNWELL = (12, 0)
L_LVPWELL = (204, 0)
L_DUALGATE = (55, 0)
L_METAL1 = (34, 0)
L_METAL1_LABEL = (34, 10)
L_VIA1 = (35, 0)
L_METAL2 = (36, 0)
L_METAL2_LABEL = (36, 10)

# --------------------------------------------------------------------------- #
# Floorplan constants (um)
# --------------------------------------------------------------------------- #

CHANNEL_UM = 3.2  # vertical gap between stacked device strips
DOMAIN_GAP_UM = 20.0  # 3.3V group top -> 5V/6V group bottom
RAIL_WIDTH_UM = 0.8  # Metal2 net rail
RAIL_PITCH_UM = 1.6
RAIL_MARGIN_UM = 6.0  # first rail's offset from the device column
STUB_WIDTH_UM = 0.42  # Metal1 pad stub / gate route
VIA_SIZE_UM = 0.26  # Via1 square
LANDING_UM = 0.6  # Metal1 landing pad around a via
JUMPER_WIDTH_UM = 0.6  # Metal1 left-rail <-> right-rail jumper
JUMPER_PITCH_UM = 1.4
JUMPER_BAND_GAP_UM = 4.0  # stack top -> first jumper
DNWELL_MARGIN_UM = 4.0  # DNWELL_DRV enclosure of the 5V/6V group
LVPWELL_MARGIN_UM = 1.0  # LVPWELL enclosure of one 5V/6V nfet strip
DUALGATE_MARGIN_UM = 2.0  # Dualgate enclosure of the 5V/6V group

# Thick-oxide (medium-voltage) model names -- the ones that must sit inside
# DNWELL_DRV + Dualgate and must never share a DNWELL with the 3.3V devices
# (spec/gate-driver.md 2.4, DRM 7.2, design/level-shifter-partition.md).
MV_MODELS = {"nfet_06v0", "pfet_06v0"}
LV_MODELS = {"nfet_03v3", "pfet_03v3"}


class GenError(RuntimeError):
    """A layout-generation step could not be completed."""


# --------------------------------------------------------------------------- #
# SPICE netlist parsing
# --------------------------------------------------------------------------- #


def _logical_lines(text: str) -> list[str]:
    """Join SPICE ``+`` continuations and drop comment lines.

    ``*.ipin``/``**.subckt`` style comments are kept as raw text so the caller
    can read the commented-out top-cell header xschem emits for a netlist
    *fragment* (design/README.md): the top cell's ``.subckt``/``.ends`` pair is
    commented out on purpose, but its ``x`` instance lines are live.
    """
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("+"):
            if not lines:
                raise GenError("netlist starts with a '+' continuation line")
            lines[-1] = lines[-1] + " " + stripped[1:].strip()
            continue
        lines.append(stripped)
    return lines


_PARAM_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*('[^']*'|\"[^\"]*\"|\S+)")
_SI_SUFFIX = {
    "t": 1e12,
    "g": 1e9,
    "meg": 1e6,
    "k": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
}


def _spice_number(value: str) -> float:
    """Parse a SPICE scalar such as ``0.28u`` / ``4.4U`` / ``500`` into a float."""
    text = value.strip().strip("'\"").lower()
    match = re.fullmatch(r"([+-]?[0-9.]+(?:e[+-]?[0-9]+)?)\s*([a-z]*)", text)
    if not match:
        raise GenError(f"cannot parse SPICE number {value!r}")
    mantissa = float(match.group(1))
    suffix = match.group(2)
    if not suffix:
        return mantissa
    for name in ("meg", "t", "g", "k", "m", "u", "n", "p", "f"):
        if suffix.startswith(name):
            return mantissa * _SI_SUFFIX[name]
    raise GenError(f"unknown SPICE unit suffix in {value!r}")


class Device:
    """One flattened MOS device, with top-level net names."""

    def __init__(
        self,
        name: str,
        model: str,
        w_um: float,
        l_um: float,
        fingers: int,
        d: str,
        g: str,
        s: str,
        b: str,
    ) -> None:
        self.name = name
        self.model = model
        self.w_um = w_um
        self.l_um = l_um
        self.fingers = fingers
        self.d = d
        self.g = g
        self.s = s
        self.b = b

    @property
    def flavor(self) -> str:
        return "pfet" if self.model.startswith("pfet") else "nfet"

    @property
    def is_mv(self) -> bool:
        return self.model in MV_MODELS

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "model": self.model,
            "w_um": self.w_um,
            "l_um": self.l_um,
            "fingers": self.fingers,
            "nets": {"d": self.d, "g": self.g, "s": self.s, "b": self.b},
        }


def parse_netlist(path: str) -> tuple[list[str], list[Device]]:
    """Flatten ``gate_driver_core.spice`` into (top port list, device list).

    Returns the top cell's port names in ``.subckt`` order plus every MOS
    device in the design, with each device's terminals renamed to the
    *top-level* net they resolve to through the ``x1``/``x2`` instance lines.
    """
    with open(path, encoding="utf-8") as handle:
        lines = _logical_lines(handle.read())

    top_ports: list[str] = []
    top_instances: list[tuple[str, list[str], str]] = []
    subckts: dict[str, tuple[list[str], list[list[str]]]] = {}

    current: str | None = None
    for line in lines:
        low = line.lower()
        if low.startswith("**.subckt "):
            # '**.subckt <cell> <port> ...' -- drop the directive and cell name
            top_ports = line.split()[2:]
            continue
        if low.startswith(".subckt "):
            tokens = line.split()
            current = tokens[1]
            subckts[current] = (tokens[2:], [])
            continue
        if low.startswith(".ends") or low.startswith("**.ends"):
            current = None
            continue
        if line.startswith("*"):
            continue
        if not low.startswith("x"):
            continue
        tokens = line.split()
        if current is None:
            # Top-level subcircuit instance: X<name> <nets...> <subckt>
            top_instances.append((tokens[0], tokens[1:-1], tokens[-1]))
        else:
            subckts[current][1].append(tokens)

    if not top_ports:
        raise GenError(f"{path}: no top-level '**.subckt' header found")
    if not top_instances:
        raise GenError(f"{path}: no top-level subcircuit instances found")

    devices: list[Device] = []
    for inst_name, inst_nets, subckt_name in top_instances:
        if subckt_name not in subckts:
            raise GenError(f"{path}: instance {inst_name} names unknown cell {subckt_name}")
        formal, body = subckts[subckt_name]
        if len(formal) != len(inst_nets):
            raise GenError(
                f"{path}: instance {inst_name} has {len(inst_nets)} nets but "
                f"{subckt_name} declares {len(formal)} ports"
            )
        mapping = {f: a for f, a in zip(formal, inst_nets)}
        for tokens in body:
            devices.append(
                _device_from_tokens(tokens, mapping, prefix=f"{inst_name}_")
            )
    return top_ports, devices


def _device_from_tokens(
    tokens: list[str], mapping: dict[str, str], prefix: str
) -> Device:
    """Build a :class:`Device` from one ``X<name> d g s b model params...`` line."""
    name = tokens[0]
    terminals = tokens[1:5]
    model = tokens[5]
    params = dict(_PARAM_RE.findall(" ".join(tokens[6:])))

    def resolve(net: str) -> str:
        return mapping.get(net, f"{prefix}{net}")

    w_um = _spice_number(params["W"]) * 1e6
    l_um = _spice_number(params["L"]) * 1e6
    nf = int(round(_spice_number(params.get("nf", "1"))))
    m = int(round(_spice_number(params.get("m", "1"))))
    if nf < 1 or m < 1:
        raise GenError(f"{name}: nf/m must be >= 1 (got nf={nf}, m={m})")
    return Device(
        name=f"{prefix}{name}",
        model=model,
        w_um=w_um,
        l_um=l_um,
        fingers=nf * m,
        d=resolve(terminals[0]),
        g=resolve(terminals[1]),
        s=resolve(terminals[2]),
        b=resolve(terminals[3]),
    )


# --------------------------------------------------------------------------- #
# klt drivers
# --------------------------------------------------------------------------- #


def _klt(*args: str) -> dict:
    """Run one ``klt`` subcommand with ``--format json`` and return its response."""
    exe = shutil.which("klt")
    if exe is None:
        raise GenError(
            "klayout-tools ('klt') is not on PATH -- this repo's layout flow "
            "requires it (see CLAUDE.md)"
        )
    proc = subprocess.run(
        [exe, *args, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GenError(
            f"klt {' '.join(args[:2])} failed (exit {proc.returncode}):\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise GenError(f"klt {' '.join(args[:2])} produced non-JSON output: {exc}") from exc


def generate_device_cells(
    devices: list[Device], out_dir: str, pdk: str
) -> dict[str, dict]:
    """Run ``klt gen mos_array`` once per device; return name -> generator report."""
    reports: dict[str, dict] = {}
    for device in devices:
        params = {
            "w_um": round(device.w_um, 4),
            "l_um": round(device.l_um, 4),
            "fingers": device.fingers,
            "finger_topology": "parallel",
            "rows": 1,
            "cols": 1,
            "dummy": 0,
            "topology": "array",
            "flavor": device.flavor,
            "gate_contact": True,
        }
        gds_path = os.path.join(out_dir, f"{device.name}.gds")
        report = _klt(
            "gen",
            "mos_array",
            "--pdk",
            pdk,
            "--params",
            json.dumps(params),
            "--cell-name",
            device.name,
            "-o",
            gds_path,
        )
        reports[device.name] = report
    return reports


# --------------------------------------------------------------------------- #
# Floorplan
# --------------------------------------------------------------------------- #


def _ports_by_role(report: dict) -> dict[str, dict]:
    """Map a ``mos_array`` report's ``U0_S``/``U0_D``/``U0_G`` ports to s/d/g."""
    roles = {}
    for port in report.get("ports", []):
        suffix = port["name"].rsplit("_", 1)[-1].lower()
        if suffix in ("s", "d", "g"):
            roles[suffix] = port
    missing = {"s", "d", "g"} - set(roles)
    if missing:
        raise GenError(
            f"generator report for {report.get('cell_name')} is missing "
            f"port(s) {sorted(missing)}"
        )
    return roles


class Placement:
    """Absolute placement of one device strip."""

    def __init__(self, device: Device, report: dict, origin_x: float, origin_y: float):
        self.device = device
        self.report = report
        self.x = origin_x
        self.y = origin_y
        bbox = report["bbox_um"]
        self.x0 = bbox["x0"] + origin_x
        self.y0 = bbox["y0"] + origin_y
        self.x1 = bbox["x1"] + origin_x
        self.y1 = bbox["y1"] + origin_y
        roles = _ports_by_role(report)
        self.pad = {
            role: (port["x_um"] + origin_x, port["y_um"] + origin_y)
            for role, port in roles.items()
        }


def place_devices(devices: list[Device], reports: dict[str, dict]) -> list[Placement]:
    """Stack every device strip vertically: 3.3V group, domain gap, 5V/6V group."""
    ordered = [d for d in devices if not d.is_mv] + [d for d in devices if d.is_mv]
    placements: list[Placement] = []
    cursor = 0.0
    previous_mv: bool | None = None
    for device in ordered:
        report = reports[device.name]
        bbox = report["bbox_um"]
        if previous_mv is not None:
            cursor += DOMAIN_GAP_UM if device.is_mv != previous_mv else CHANNEL_UM
        origin_y = cursor - bbox["y0"]
        placements.append(Placement(device, report, 0.0, origin_y))
        cursor = origin_y + bbox["y1"]
        previous_mv = device.is_mv
    return placements


# --------------------------------------------------------------------------- #
# Interconnect / marker cell
# --------------------------------------------------------------------------- #


def _rect(layer: tuple[int, int], x0: float, y0: float, x1: float, y1: float, name=None):
    shape = {
        "layer": list(layer),
        "rect_um": [round(v, 4) for v in (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))],
    }
    if name:
        shape["name"] = name
    return shape


def _hbar(layer, x0: float, x1: float, y: float, width: float, name=None):
    return _rect(layer, x0, y - width / 2.0, x1, y + width / 2.0, name)


def _vbar(layer, y0: float, y1: float, x: float, width: float, name=None):
    return _rect(layer, x - width / 2.0, y0, x + width / 2.0, y1, name)


class Interconnect:
    """Builds the ``klt draw`` request for the wiring + marker cell."""

    def __init__(self, placements: list[Placement], nets: list[str]):
        self.placements = placements
        self.nets = nets
        self.shapes: list[dict] = []
        self.labels: list[dict] = []

        column_x1 = max(p.x1 for p in placements)
        self.left_rail_x = {
            net: -RAIL_MARGIN_UM - index * RAIL_PITCH_UM
            for index, net in enumerate(nets)
        }
        self.right_rail_x = {
            net: column_x1 + RAIL_MARGIN_UM + index * RAIL_PITCH_UM
            for index, net in enumerate(nets)
        }
        self.stack_bottom = min(p.y0 for p in placements)
        self.stack_top = max(p.y1 for p in placements)
        self.jumper_y = {
            net: self.stack_top + JUMPER_BAND_GAP_UM + index * JUMPER_PITCH_UM
            for index, net in enumerate(nets)
        }
        self.rail_y0 = self.stack_bottom - 2.0
        self.rail_y1 = max(self.jumper_y.values()) + 2.0

    # -- primitives -------------------------------------------------------- #

    def _via_stack(self, x: float, y: float) -> None:
        """Via1 plus its Metal1 landing pad (the Metal2 rail is the top plate)."""
        self.shapes.append(
            _rect(
                L_METAL1,
                x - LANDING_UM / 2,
                y - LANDING_UM / 2,
                x + LANDING_UM / 2,
                y + LANDING_UM / 2,
            )
        )
        self.shapes.append(
            _rect(
                L_VIA1,
                x - VIA_SIZE_UM / 2,
                y - VIA_SIZE_UM / 2,
                x + VIA_SIZE_UM / 2,
                y + VIA_SIZE_UM / 2,
            )
        )

    # -- build steps ------------------------------------------------------- #

    def rails(self) -> None:
        for net in self.nets:
            for x in (self.left_rail_x[net], self.right_rail_x[net]):
                self.shapes.append(
                    _vbar(L_METAL2, self.rail_y0, self.rail_y1, x, RAIL_WIDTH_UM, name=net)
                )
            self.labels.append(
                {
                    "layer": list(L_METAL2_LABEL),
                    "text": net,
                    "at_um": [round(self.left_rail_x[net], 4), round(self.rail_y0 + 1.0, 4)],
                }
            )
            self.labels.append(
                {
                    "layer": list(L_METAL2_LABEL),
                    "text": net,
                    "at_um": [round(self.right_rail_x[net], 4), round(self.rail_y0 + 1.0, 4)],
                }
            )

    def jumpers(self) -> None:
        """Tie each net's left rail to its right rail on Metal1, above the stack."""
        for net in self.nets:
            y = self.jumper_y[net]
            left = self.left_rail_x[net]
            right = self.right_rail_x[net]
            self.shapes.append(_hbar(L_METAL1, left, right, y, JUMPER_WIDTH_UM, name=net))
            self._via_stack(left, y)
            self._via_stack(right, y)

    def device_wiring(self) -> None:
        for index, placement in enumerate(self.placements):
            device = placement.device
            # Source -> left rail.
            sx, sy = placement.pad["s"]
            rail = self.left_rail_x[device.s]
            self.shapes.append(
                _hbar(L_METAL1, rail, sx + STUB_WIDTH_UM / 2, sy, STUB_WIDTH_UM, name=device.s)
            )
            self._via_stack(rail, sy)

            # Drain -> right rail.
            dx, dy = placement.pad["d"]
            rail = self.right_rail_x[device.d]
            self.shapes.append(
                _hbar(L_METAL1, dx - STUB_WIDTH_UM / 2, rail, dy, STUB_WIDTH_UM, name=device.d)
            )
            self._via_stack(rail, dy)

            # Gate -> up out of the strip, left through the channel above it.
            gx, gy = placement.pad["g"]
            channel_y = self._gate_channel_y(index)
            rail = self.left_rail_x[device.g]
            self.shapes.append(
                _vbar(
                    L_METAL1,
                    gy - STUB_WIDTH_UM / 2,
                    channel_y + STUB_WIDTH_UM / 2,
                    gx,
                    STUB_WIDTH_UM,
                    name=device.g,
                )
            )
            self.shapes.append(
                _hbar(
                    L_METAL1,
                    rail,
                    gx + STUB_WIDTH_UM / 2,
                    channel_y,
                    STUB_WIDTH_UM,
                    name=device.g,
                )
            )
            self._via_stack(rail, channel_y)

    def _gate_channel_y(self, index: int) -> float:
        """Centre of the empty horizontal channel above device strip ``index``."""
        this_top = self.placements[index].y1
        if index + 1 < len(self.placements):
            next_bottom = self.placements[index + 1].y0
        else:
            next_bottom = self.stack_top + JUMPER_BAND_GAP_UM
        return this_top + min(CHANNEL_UM / 2.0, (next_bottom - this_top) / 2.0)

    def voltage_domain_markers(self) -> None:
        """DNWELL_DRV + LVPWELL + Dualgate over the 5V/6V group only.

        The 3.3V group is left entirely outside every DNWELL, which is
        spec/gate-driver.md 2.4's second allowed option and the one
        design/level-shifter-partition.md's device table already commits to.
        """
        mv = [p for p in self.placements if p.device.is_mv]
        if not mv:
            return
        x0 = min(p.x0 for p in mv)
        x1 = max(p.x1 for p in mv)
        y0 = min(p.y0 for p in mv)
        y1 = max(p.y1 for p in mv)
        self.shapes.append(
            _rect(
                L_DNWELL,
                x0 - DNWELL_MARGIN_UM,
                y0 - DNWELL_MARGIN_UM,
                x1 + DNWELL_MARGIN_UM,
                y1 + DNWELL_MARGIN_UM,
                name="DNWELL_DRV",
            )
        )
        self.shapes.append(
            _rect(
                L_DUALGATE,
                x0 - DUALGATE_MARGIN_UM,
                y0 - DUALGATE_MARGIN_UM,
                x1 + DUALGATE_MARGIN_UM,
                y1 + DUALGATE_MARGIN_UM,
                name="DUALGATE_DRV",
            )
        )
        # Isolated p-well under each thick-oxide nfet inside DNWELL_DRV. The
        # pfets sit in their own Nwell (drawn by `klt gen mos_array`), so the
        # two never overlap: strips are stacked with a CHANNEL_UM gap and
        # LVPWELL_MARGIN_UM is well inside half of it.
        for placement in mv:
            if placement.device.flavor != "nfet":
                continue
            self.shapes.append(
                _rect(
                    L_LVPWELL,
                    placement.x0 - LVPWELL_MARGIN_UM,
                    placement.y0 - LVPWELL_MARGIN_UM,
                    placement.x1 + LVPWELL_MARGIN_UM,
                    placement.y1 + LVPWELL_MARGIN_UM,
                    name=f"LVPWELL_{placement.device.name}",
                )
            )

    def build(self) -> dict:
        self.rails()
        self.jumpers()
        self.device_wiring()
        self.voltage_domain_markers()
        # `klt draw --params` takes the *params* object itself (dbu_um /
        # shapes / labels); the CLI wraps it in the request envelope.
        return {"dbu_um": 0.001, "shapes": self.shapes, "labels": self.labels}


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #


def compose(
    placements: list[Placement],
    interconnect_report: dict,
    out_gds: str,
    out_dir: str,
    pdk: str,
) -> dict:
    blocks = [
        {"id": p.device.name, "generator_report": p.report} for p in placements
    ]
    origins = {p.device.name: {"x": p.x, "y": p.y} for p in placements}
    blocks.append({"id": "interconnect", "generator_report": interconnect_report})
    origins["interconnect"] = {"x": 0.0, "y": 0.0}
    order = [b["id"] for b in blocks]

    request = {
        "schema": "klt.gen_compose.request/1",
        "pdk": {"variant": pdk},
        "blocks": blocks,
        "placement": {"strategy": "explicit", "order": order, "origins_um": origins},
        "options": {"cell_name": TOP_CELL, "output": out_gds},
    }
    request_path = os.path.join(out_dir, "gen-compose-request.json")
    with open(request_path, "w", encoding="utf-8") as handle:
        json.dump(request, handle, indent=1)
    return _klt("gen-compose", request_path)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", REPO_ROOT, *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:  # pragma: no cover - git absent
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def build(out_dir: str, pdk: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    work_dir = os.path.join(out_dir, "build")
    os.makedirs(work_dir, exist_ok=True)

    top_ports, devices = parse_netlist(NETLIST_PATH)
    reports = generate_device_cells(devices, work_dir, pdk)
    placements = place_devices(devices, reports)

    nets = sorted({n for d in devices for n in (d.d, d.g, d.s)})
    interconnect_request = Interconnect(placements, nets).build()
    request_path = os.path.join(work_dir, "draw-request.json")
    with open(request_path, "w", encoding="utf-8") as handle:
        json.dump(interconnect_request, handle, indent=1)
    interconnect_gds = os.path.join(work_dir, "interconnect.gds")
    draw_report = _klt(
        "draw",
        "--params",
        request_path,
        "--cell-name",
        "gate_driver_core_interconnect",
        "-o",
        interconnect_gds,
    )
    # `klt draw` is not a `klt gen` generator, so it does not emit a
    # generator_report. `gen-compose` only needs generator/cell_name/gds_path/
    # bbox_um/ports (see docs/cli/gen-compose.md) -- synthesise exactly those
    # for the interconnect cell, which carries no routable ports of its own.
    interconnect_report = {
        "generator": "klt-draw:interconnect",
        "cell_name": draw_report["cell_name"],
        "gds_path": draw_report["gds_path"],
        "bbox_um": draw_report["bbox_um"],
        "ports": [],
    }

    out_gds = os.path.join(out_dir, f"{TOP_CELL}.gds")
    compose_report = compose(placements, interconnect_report, out_gds, work_dir, pdk)

    provenance = {
        "top_cell": TOP_CELL,
        "layout": {
            "path": os.path.relpath(out_gds, REPO_ROOT),
            "sha256": _sha256(out_gds),
            "bbox_um": compose_report.get("bbox_um"),
        },
        "source_netlist": {
            "path": os.path.relpath(NETLIST_PATH, REPO_ROOT),
            "sha256": _sha256(NETLIST_PATH),
            "top_ports": top_ports,
            "device_count": len(devices),
            "transistor_count": sum(d.fingers for d in devices),
        },
        "generator": {
            "path": os.path.relpath(os.path.abspath(__file__), REPO_ROOT),
            "sha256": _sha256(os.path.abspath(__file__)),
        },
        "tools": {
            "klt_version": _klt_version(),
            "pdk": compose_report.get("pdk"),
            "note": (
                "the klayout build and the extraction deck's content hash are "
                "recorded in gate_driver_core.checks.json (klt extract's own "
                "provenance block)"
            ),
        },
        "git": {
            "commit": _git("rev-parse", "HEAD"),
            "describe": _git("describe", "--always", "--dirty"),
        },
        "placement": [
            {
                "id": p.device.name,
                "origin_um": {"x": round(p.x, 4), "y": round(p.y, 4)},
                "bbox_um": {
                    "x0": round(p.x0, 4),
                    "y0": round(p.y0, 4),
                    "x1": round(p.x1, 4),
                    "y1": round(p.y1, 4),
                },
                "domain": "5V/6V" if p.device.is_mv else "3.3V",
            }
            for p in placements
        ],
        "compose_warnings": compose_report.get("warnings", []),
        "devices": [d.as_dict() for d in devices],
    }
    provenance_path = os.path.join(out_dir, f"{TOP_CELL}.provenance.json")
    with open(provenance_path, "w", encoding="utf-8") as handle:
        json.dump(provenance, handle, indent=2, sort_keys=False)
        handle.write("\n")
    return {
        "gds": out_gds,
        "provenance": provenance_path,
        "compose": compose_report,
        "devices": devices,
    }


def _klt_version() -> str:
    exe = shutil.which("klt")
    if exe is None:
        return "unknown"
    proc = subprocess.run([exe, "--version"], capture_output=True, text=True, check=False)
    return proc.stdout.strip() or proc.stderr.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out-dir",
        default=HERE,
        help="directory to write the layout + provenance into (default: layout/)",
    )
    parser.add_argument("--pdk", default=DEFAULT_PDK, help="PDK variant (default: %(default)s)")
    args = parser.parse_args(argv)

    try:
        result = build(os.path.abspath(args.out_dir), args.pdk)
    except GenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    compose_report = result["compose"]
    print(f"top cell     : {TOP_CELL}")
    print(f"layout       : {result['gds']}")
    print(f"provenance   : {result['provenance']}")
    print(f"blocks placed: {len(compose_report.get('blocks', []))}")
    bbox = compose_report.get("bbox_um") or {}
    if bbox:
        print(
            "bbox (um)    : "
            f"{bbox['x1'] - bbox['x0']:.2f} x {bbox['y1'] - bbox['y0']:.2f}"
        )
    print(f"netlist devs : {len(result['devices'])}")
    print(f"transistors  : {sum(d.fingers for d in result['devices'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
