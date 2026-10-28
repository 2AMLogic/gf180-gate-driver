#!/usr/bin/env python3
"""Derive the proposed Ron*W statistical bound from the committed MC samples.

Input is the `samples-*.csv` sidecars of sim record 20260821-134653-804155b;
nothing is re-simulated. For each PVT point the control is the baseline row
(plain deck, mismatch off), a draw is a row with sw_stat_mismatch != 0, and
the proposed bound is `control + 5 % of the ratified 3:1 window width`.

Usage: derive_ronw_bound.py [--emit-samples OUT.json]

--emit-samples writes a `klt yield` sample-set document (one measurement per
PVT point, with the proposed `max` limit and `target_yield`) so the sample-size
verdict can be read with `klt yield OUT.json`.
"""
import argparse
import csv
import glob
import json
import math
import os
import statistics

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORNERS = os.path.join(
    REPO, "sim/low-side-power-switch-ronw-mismatch/corners/20260821-134653-804155b"
)
COLUMN = "ronw_n06_3.6"  # worst design row: Vgs = 3.6 V (spec 2.1)
WINDOW_LO, WINDOW_HI = 1.8855, 4.5719  # ratified 2.1 window, ohm*mm
MATERIALITY = 0.05  # fraction of window width; the sim record's own threshold
TARGET_YIELD = 0.98  # N = 200 zero-failure gives a CP low end of 0.9817


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit-samples")
    args = ap.parse_args()

    allowed = MATERIALITY * (WINDOW_HI - WINDOW_LO)
    measurements = []
    print(f"allowed excursion over own control: {allowed * 1e3:.3f} mOhm*mm")
    print("pvt                  n   control   sigma_mOhm*mm  max_exc_mOhm*mm  fails")
    worst = 0.0
    for path in sorted(glob.glob(os.path.join(CORNERS, "samples-*.csv"))):
        pvt = os.path.basename(path)[len("samples-"):-len(".csv")]
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        control = float(next(r for r in rows if r["sample"] == "baseline")[COLUMN])
        draws = [
            float(r[COLUMN])
            for r in rows
            if r["sample"] != "baseline"
            and r["status"] == "ok"
            and float(r["sw_stat_mismatch"]) != 0
        ]
        limit = control + allowed
        fails = sum(d > limit for d in draws)
        exc = max(draws) - control
        worst = max(worst, exc)
        print(
            f"{pvt:20s} {len(draws):3d} {control:9.4f} "
            f"{statistics.stdev(draws) * 1e3:13.3f} {exc * 1e3:16.3f} {fails:6d}"
        )
        measurements.append(
            {
                "name": f"{COLUMN}@{pvt}",
                "unit": "ohm*mm",
                "samples": draws,
                "limits": {"max": limit, "target_yield": TARGET_YIELD},
            }
        )
    n_min = min(len(m["samples"]) for m in measurements)
    floor = 0.025 ** (1.0 / n_min)  # two-sided 95 % Clopper-Pearson low end, zero failures
    print(f"worst excursion {worst * 1e3:.3f} mOhm*mm = {worst / allowed:.1%} of allowed")
    print(f"zero-failure yield floor (two-sided 95 % CP) with n={n_min}: {floor:.4f}")
    if args.emit_samples:
        doc = {
            "schema": "gf180-gate-driver/mc-sample-set/1",
            "campaign": "low-side-power-switch-ronw-mismatch",
            "measurements": measurements,
        }
        with open(args.emit_samples, "w") as f:
            json.dump(doc, f)


if __name__ == "__main__":
    main()
