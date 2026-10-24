"""Synthetic fixtures for pinning the three mismatch runners' record bodies.

Used by ``sim/test_harness_campaign.py`` (issue #344). PDK- and ngspice-free:
the runners' ``build_record_body`` only reads ``PointOutcome`` accessors and a
handful of ``Testbench`` attributes.
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
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
