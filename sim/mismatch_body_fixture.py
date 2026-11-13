"""Synthetic fixtures for pinning the mismatch runners' record bodies.

Used by ``sim/test_harness_campaign.py`` (issue #344). PDK- and ngspice-free:
the runners' ``build_record_body`` only reads ``PointOutcome`` accessors and a
handful of ``Testbench`` attributes.

Four runners are covered. The three transient ones (``indrv``, ``inb``,
``taper``) share a node-voltage shape and a ``Testbench``; the device-level
``ronw`` runner has neither a testbench nor a supply rail and measures
``Ron.W`` / forward-drop families instead, so it gets its own outcome builder
and its own ``render_ronw`` (issue #442, which replaced that runner's private
copy of ``campaign.control_table_rows`` with the shared helper -- a change
whose whole point is that it must not move a single byte of generated
markdown).
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from harness import runner as harness_runner
from harness.montecarlo import CONTROL_SAMPLE, MismatchSample
from harness.runner import PointResult

SIM_DIR = Path(__file__).resolve().parent
STAMP = _dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=_dt.timezone.utc)

RUNNERS = {
    "indrv": ("gate-driver-indrv-mismatch", "run_indrv_mismatch.py"),
    "inb": ("level-shifter-inb-mismatch", "run_inb_mismatch.py"),
    "taper": ("output-stage-taper-mismatch", "run_output_stage_mismatch.py"),
}

RONW_RUNNER = ("low-side-power-switch-ronw-mismatch", "run_ronw_mismatch.py")

_MEASUREMENTS = ("indrv_max_v", "vinb_max_v", "n1_max_v", "n2_max_v", "n3_max_v", "n4_max_v", "n5_max_v")

TB = SimpleNamespace(
    dut_provenance_class="design",
    dut_path="design/fake.spice",
    dut_sha256="d" * 64,
    netlist=Path("/nonexistent/fake_tb.spice"),
    netlist_sha256="n" * 64,
)
PDK = SimpleNamespace(variant="gf180mcuD", path="/nonexistent/gf180mcuD")
NGSPICE = "ngspice-47 : fake"

SCENARIOS = ("mixed", "clean", "error")


def load_runner(key: str):
    directory, script = RUNNERS[key]
    path = SIM_DIR / directory / script
    spec = importlib.util.spec_from_file_location(f"_golden_{key}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _result(point, base, status="ok"):
    measurements = (
        {name: base + 0.001 * i for i, name in enumerate(_MEASUREMENTS)} if status == "ok" else {}
    )
    return PointResult(
        point=point,
        status=status,
        measurements=measurements,
        seconds=0.0,
        message="" if status == "ok" else "Timestep too small;\n  aborted",
        output="",
    )


def build_outcomes(module, scenario: str):
    """Deterministic outcomes over the first four of the runner's PVT points."""
    points = module.build_points()[:4]
    outcomes = []
    for index, point in enumerate(points):
        base = 3.0 + 0.5 * index
        ctrl = [
            (MismatchSample(sample=CONTROL_SAMPLE, seed=1), _result(point, base)),
            (MismatchSample(sample=CONTROL_SAMPLE, seed=2), _result(point, base)),
        ]
        baseline = _result(point, base if (index != 1 or scenario != "mixed") else base + 1e-6)
        samples = []
        for s in range(5):
            status = "ok"
            if scenario == "error" or (scenario == "mixed" and (index == 2 or (index == 0 and s == 3))):
                status = "failed"
            samples.append(
                (MismatchSample(sample=s + 1, seed=100 * index + s), _result(point, base + 0.01 * (s - 1) * (index + 1), status))
            )
        outcomes.append(module.PointOutcome(point, baseline, ctrl, samples))
    return outcomes


def render(key: str, scenario: str, smoke: bool) -> str:
    module = load_runner(key)
    original = harness_runner.effective_reltol
    harness_runner.effective_reltol = lambda tb: ("1e-4", "harness default")
    try:
        body, verdict = module.build_record_body(
            "20260102-030405-abcdef0", STAMP, PDK, NGSPICE, TB,
            build_outcomes(module, scenario), 5, 123.0, SimpleNamespace(smoke=smoke),
        )
    finally:
        harness_runner.effective_reltol = original
    return f"verdict={verdict}\n{body}"


# --------------------------------------------------------------------------
# The device-level `ronw` runner: no testbench, no supply rail, and a family
# of `Ron.W` / forward-drop measurements rather than one node voltage.
# --------------------------------------------------------------------------


def load_ronw():
    directory, script = RONW_RUNNER
    path = SIM_DIR / directory / script
    spec = importlib.util.spec_from_file_location("_golden_ronw", path)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: this runner defines a `@dataclass`, and
    # `dataclasses` resolves annotations through `sys.modules[cls.__module__]`.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _ronw_result(module, point, base, status="ok"):
    measurements = (
        {name: base + 0.01 * i for i, name in enumerate(module.FLATTEN_NAMES)}
        if status == "ok"
        else {}
    )
    return PointResult(
        point=point, status=status, measurements=measurements, seconds=0.0,
        message="" if status == "ok" else "aborted", output="raw\n",
    )


def build_ronw_outcomes(module, scenario: str):
    """Deterministic outcomes over the first four of the runner's grid points.

    Values sit inside `RATIFIED_WINDOW_OHMMM`'s `n06`/3.6 V window so the
    record exercises its normal (non-excursion) prose.
    """
    outcomes = []
    for index, (corner, temp) in enumerate(module.GRID[:4]):
        point = module.DevicePoint(corner=corner, temp_c=temp)
        base = 2.0 + 0.1 * index
        ctrl = [
            (MismatchSample(sample=CONTROL_SAMPLE, seed=1), _ronw_result(module, point, base)),
            (MismatchSample(sample=CONTROL_SAMPLE, seed=2), _ronw_result(module, point, base)),
        ]
        baseline = _ronw_result(
            module, point, base if (index != 1 or scenario != "mixed") else base + 1e-6
        )
        samples = []
        for s in range(5):
            status = "ok"
            if scenario == "error" or (
                scenario == "mixed" and (index == 2 or (index == 0 and s == 3))
            ):
                status = "failed"
            samples.append(
                (
                    MismatchSample(sample=s + 1, seed=100 * index + s),
                    _ronw_result(module, point, base + 0.001 * (s - 1) * (index + 1), status),
                )
            )
        outcomes.append(module.PointOutcome(point, baseline, ctrl, samples))
    return outcomes


def render_ronw(scenario: str, smoke: bool) -> str:
    module = load_ronw()
    body, verdict, anomalies = module.build_record_body(
        "20260102-030405-abcdef0", STAMP, PDK, NGSPICE,
        build_ronw_outcomes(module, scenario), 5, 123.0, SimpleNamespace(smoke=smoke),
    )
    return f"verdict={verdict}\nanomalies={anomalies}\n{body}"


# --------------------------------------------------------------------------
# The "no reference log anywhere" rendering (issue #442). Every runner's
# `PointOutcome.reference_delta` returns `None` when the committed reference
# record has no log for a point; this drives all four runners down that path
# without deleting committed evidence to do it.
# --------------------------------------------------------------------------


def _no_reference(module):
    """Patch `module.PointOutcome.reference_delta` to always return `None`."""
    original = module.PointOutcome.reference_delta
    module.PointOutcome.reference_delta = lambda self, *args, **kwargs: None
    return original


def render_without_reference(key: str, smoke: bool = False) -> str:
    """`render(key, "clean", smoke)` with no reference available at any point."""
    module = load_runner(key)
    original_reltol = harness_runner.effective_reltol
    harness_runner.effective_reltol = lambda tb: ("1e-4", "harness default")
    original_delta = _no_reference(module)
    try:
        body, verdict = module.build_record_body(
            "20260102-030405-abcdef0", STAMP, PDK, NGSPICE, TB,
            build_outcomes(module, "clean"), 5, 123.0, SimpleNamespace(smoke=smoke),
        )
    finally:
        module.PointOutcome.reference_delta = original_delta
        harness_runner.effective_reltol = original_reltol
    return f"verdict={verdict}\n{body}"


def render_ronw_without_reference(smoke: bool = False) -> str:
    """`render_ronw("clean", smoke)` with no reference available at any point."""
    module = load_ronw()
    original_delta = _no_reference(module)
    try:
        body, verdict, anomalies = module.build_record_body(
            "20260102-030405-abcdef0", STAMP, PDK, NGSPICE,
            build_ronw_outcomes(module, "clean"), 5, 123.0, SimpleNamespace(smoke=smoke),
        )
    finally:
        module.PointOutcome.reference_delta = original_delta
    return f"verdict={verdict}\nanomalies={anomalies}\n{body}"
