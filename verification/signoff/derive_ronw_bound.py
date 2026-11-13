#!/usr/bin/env python3
"""Derive the proposed Ron*W statistical bound from the committed MC samples.

Input is the `samples-*.csv` sidecars of sim record 20260821-134653-804155b;
nothing is re-simulated. For each PVT point the control is the baseline row
(plain deck, mismatch off), a draw is a mismatch row, and the proposed bound is
`control + 5 % of the ratified 3:1 window width`.

Which CSV rows are samples is **not** defined here. Draws and the control both
come from `sim/mc_to_yield.py` (`read_draws` / `read_control`), the converter
`sim/test_mc_to_yield.py` pins and CI runs, so this campaign and the three in
`mc_to_yield.CAMPAIGNS` share one definition. In particular a non-converged
draw is kept as a `null` sample -- counted `errored` by `klt yield` -- instead
of vanishing from the population and silently shrinking it.

Usage: derive_ronw_bound.py [--emit-samples OUT.json]

--emit-samples writes a `klt yield` sample-set document (one measurement per
PVT point, with the proposed `max` limit and `target_yield`) so the sample-size
verdict can be read with `klt yield OUT.json`.
"""
import argparse
import glob
import importlib.util
import json
import os
import statistics
import sys
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORNERS = os.path.join(
    REPO, "sim/low-side-power-switch-ronw-mismatch/corners/20260821-134653-804155b"
)
CAMPAIGN = "low-side-power-switch-ronw-mismatch"
COLUMN = "ronw_n06_3.6"  # worst design row: Vgs = 3.6 V (spec 2.1)
UNIT = "ohm*mm"
WINDOW_LO, WINDOW_HI = 1.8855, 4.5719  # ratified 2.1 window, ohm*mm
MATERIALITY = 0.05  # fraction of window width; the sim record's own threshold
TARGET_YIELD = 0.98  # N = 200 zero-failure gives a CP low end of 0.9817


def _load_mc_to_yield():
    """Import `sim/mc_to_yield.py` by explicit path.

    Decision record 0021 reproduces this script with `python3 -I`, which
    ignores PYTHONPATH and does not put the script's directory on `sys.path`,
    so the shared converter has to be located relative to this file.
    """
    if "mc_to_yield" in sys.modules:
        return sys.modules["mc_to_yield"]
    path = os.path.join(REPO, "sim", "mc_to_yield.py")
    spec = importlib.util.spec_from_file_location("mc_to_yield", path)
    if spec is None or spec.loader is None:  # pragma: no cover - layout error
        raise RuntimeError(f"cannot import the shared converter at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["mc_to_yield"] = module
    spec.loader.exec_module(module)
    return module


mc = _load_mc_to_yield()


def allowed_excursion() -> float:
    """The materiality allowance over a point's own control, in ohm*mm."""
    return MATERIALITY * (WINDOW_HI - WINDOW_LO)


def build_rows(corners_dir) -> list[dict]:
    """One record per PVT point: control, limit, samples, and the table stats.

    `samples` is the shared converter's population, so it may contain `None`
    for a non-converged draw. The statistics below are over the converged
    draws only (a `None` has no value to compare), but `n` stays the full
    population size and `n_converged` records the difference.
    """
    allowed = allowed_excursion()
    rows = []
    for path in sorted(glob.glob(os.path.join(corners_dir, "samples-*.csv"))):
        path = Path(path)
        samples, _seeds = mc.read_draws(path, [COLUMN])
        converged = [s for s in samples if s is not None]
        if len(converged) < 2:
            raise mc.ConversionError(
                f"{path}: fewer than two converged mismatch draws"
            )
        control = mc.read_control(path, [COLUMN])
        limit = control + allowed
        rows.append(
            {
                "pvt": mc.pvt_of(path),
                "control": control,
                "limit": limit,
                "samples": samples,
                "n": len(samples),
                "n_converged": len(converged),
                "sigma": statistics.stdev(converged),
                "excursion": max(converged) - control,
                "fails": sum(d > limit for d in converged),
            }
        )
    if not rows:
        raise mc.ConversionError(f"{corners_dir}: no samples-*.csv")
    return rows


def sample_set(rows: list[dict]) -> dict:
    """The `klt yield` sample-set document for the per-PVT bound."""
    return {
        "schema": mc.SCHEMA,
        "campaign": CAMPAIGN,
        "measurements": [
            {
                "name": f"{COLUMN}@{r['pvt']}",
                "unit": UNIT,
                "samples": r["samples"],
                "limits": {"max": r["limit"], "target_yield": TARGET_YIELD},
            }
            for r in rows
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit-samples")
    args = ap.parse_args(argv)

    allowed = allowed_excursion()
    rows = build_rows(CORNERS)
    print(f"allowed excursion over own control: {allowed * 1e3:.3f} mOhm*mm")
    print("pvt                  n   control   sigma_mOhm*mm  max_exc_mOhm*mm  fails")
    for r in rows:
        print(
            f"{r['pvt']:20s} {r['n']:3d} {r['control']:9.4f} "
            f"{r['sigma'] * 1e3:13.3f} {r['excursion'] * 1e3:16.3f} {r['fails']:6d}"
        )
    worst = max(r["excursion"] for r in rows)
    n_min = min(r["n_converged"] for r in rows)
    floor = 0.025 ** (1.0 / n_min)  # two-sided 95 % Clopper-Pearson low end, zero failures
    print(f"worst excursion {worst * 1e3:.3f} mOhm*mm = {worst / allowed:.1%} of allowed")
    print(f"zero-failure yield floor (two-sided 95 % CP) with n={n_min}: {floor:.4f}")
    errored = sum(r["n"] - r["n_converged"] for r in rows)
    if errored:
        print(
            f"note: {errored} non-converged draw(s) are kept as null samples; "
            "`klt yield` counts them errored, and the floor above uses the "
            "converged draws only"
        )
    if args.emit_samples:
        with open(args.emit_samples, "w") as f:
            json.dump(sample_set(rows), f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
