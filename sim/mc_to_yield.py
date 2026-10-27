#!/usr/bin/env python3
"""Convert a committed mismatch campaign's `samples-*.csv` into a `klt yield`
sample-set document (issue #368, T1 item 6).

The four `sim/*-mismatch` campaigns already commit every Monte Carlo draw as
one `samples-<pvt>.csv` per PVT point. This turns them into the sample-set
shape `klt yield` reads (docs/cli/yield.md, "Sample-set document") without
re-simulating anything and without touching the campaign scripts or records.

Conventions (each one is a claim about the evidence, so they are explicit):

* Each PVT point is its own population -> one measurement per point, named
  `<measurement>@<pvt>`. Nothing is pooled across points.
* Only mismatch draws are samples: rows with `sw_stat_mismatch == 1`. The
  `baseline` row (plain deck) and the `sw_stat_mismatch == 0` zero-sigma
  control rows are excluded; they are the harness's bit-for-bit
  reproducibility check, not draws from a distribution, and not a
  `klt yield` negative control (which must be a seeded-defect campaign).
* A draw whose `status` is not `ok` (non-converged) is kept as a `null`
  sample, so `klt yield` counts it as `errored` rather than it vanishing.
* Limits are the ratified bounds, never adjusted here (spec/gate-driver.md
  section 5 Exceptions 1-3).

Usage:
    sim/mc_to_yield.py CAMPAIGN CORNERS_DIR [-o OUT.json]
    sim/mc_to_yield.py --list
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCHEMA = "gf180-gate-driver/mc-sample-set/1"

#: campaign -> the claim it backs. `columns` is one CSV column or several
#: (the draw's value is the max of them: the worst of the node set the
#: exception bounds); `max` is the ratified upper bound in `unit`.
CAMPAIGNS: dict[str, dict] = {
    "gate-driver-indrv-mismatch": {
        "spec_row": "spec/gate-driver.md section 5, Exception 3 (IN_DRV <= 10 mV over the 6.0 V gate ceiling)",
        "measurement": "indrv_max_v",
        "columns": ["indrv_max_v"],
        "unit": "V",
        "max": 6.0 + 0.010,
    },
    "level-shifter-inb-mismatch": {
        "spec_row": "spec/gate-driver.md section 5, Exception 1 (inb <= 40 mV over VDD_LOGIC = 3.63 V)",
        "measurement": "vinb_max_v",
        "columns": ["vinb_max_v"],
        "unit": "V",
        "max": 3.63 + 0.040,
    },
    "output-stage-taper-mismatch": {
        "spec_row": "spec/gate-driver.md section 5, Exception 2 (taper nodes n1..n5 <= 175 mV over the 6.0 V gate ceiling)",
        "measurement": "taper_max_v",
        "columns": [f"n{i}_max_v" for i in range(1, 6)],
        "unit": "V",
        "max": 6.0 + 0.175,
    },
}


class ConversionError(Exception):
    pass


def read_draws(path: Path, columns: list[str]) -> tuple[list[float | None], list[int]]:
    """Return (samples, seeds) for the mismatch draws in one samples CSV.

    A non-`ok` draw becomes a `None` sample (counted as errored downstream).
    """
    samples: list[float | None] = []
    seeds: list[int] = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in ["sw_stat_mismatch", "status", "seed", *columns] if c not in (reader.fieldnames or [])]
        if missing:
            raise ConversionError(f"{path}: missing column(s) {missing}")
        for row in reader:
            if row["sw_stat_mismatch"].strip() != "1":
                continue  # baseline / zero-sigma control row
            seeds.append(int(row["seed"]))
            if row["status"].strip() != "ok":
                samples.append(None)
                continue
            try:
                samples.append(max(float(row[c]) for c in columns))
            except ValueError as exc:
                raise ConversionError(f"{path}: sample {row['sample']}: {exc}") from exc
    if not samples:
        raise ConversionError(f"{path}: no mismatch draws (sw_stat_mismatch == 1)")
    return samples, seeds


def pvt_of(path: Path) -> str:
    stem = path.stem
    if not stem.startswith("samples-"):
        raise ConversionError(f"{path}: not a samples-<pvt>.csv file")
    return stem[len("samples-"):]


def build_sample_set(campaign: str, corners_dir: Path) -> dict:
    if campaign not in CAMPAIGNS:
        raise ConversionError(f"no yield mapping for {campaign!r}; known: {sorted(CAMPAIGNS)}")
    spec = CAMPAIGNS[campaign]
    csvs = sorted(corners_dir.glob("samples-*.csv"))
    if not csvs:
        raise ConversionError(f"{corners_dir}: no samples-*.csv")
    measurements = []
    for path in csvs:
        pvt = pvt_of(path)
        samples, seeds = read_draws(path, spec["columns"])
        measurements.append({
            "name": f"{spec['measurement']}@{pvt}",
            "unit": spec["unit"],
            "samples": samples,
            "limits": {"max": spec["max"]},
            "source_corners": [pvt],
            "seeds": {"first": min(seeds), "last": max(seeds), "n": len(seeds)},
        })
    return {
        "schema": SCHEMA,
        "campaign": campaign,
        "spec_row": spec["spec_row"],
        "source": str(corners_dir),
        "measurements": measurements,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("campaign", nargs="?")
    ap.add_argument("corners_dir", nargs="?", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--list", action="store_true", help="list convertible campaigns")
    args = ap.parse_args(argv)
    if args.list:
        for name, spec in CAMPAIGNS.items():
            print(f"{name}\t{spec['measurement']}\tmax {spec['max']}")
        return 0
    if not args.campaign or not args.corners_dir:
        ap.error("CAMPAIGN and CORNERS_DIR are required")
    try:
        doc = build_sample_set(args.campaign, args.corners_dir)
    except ConversionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(doc, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
