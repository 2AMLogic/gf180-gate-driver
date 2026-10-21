"""Helpers shared by the standalone ``sim/*/run_*.py`` experiment scripts.

These scripts drive ngspice directly rather than through ``runner``, and each
used to carry its own byte-identical copy of these functions. ``fmt`` keeps
4 digits (``campaign.fmt`` defaults to 6) so recorded evidence formatting does
not change.
"""

from __future__ import annotations

from . import campaign
from . import corners as harness_corners


def fmt(value, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def parse_dc_tables(log: str) -> list[tuple[list[str], list[list[float]]]]:
    """Every ``Index <cols...>`` table in a control-block's printed output,
    in the order the ``print`` commands that produced them were issued."""
    lines = log.splitlines()
    tables: list[tuple[list[str], list[list[float]]]] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("Index"):
            header = lines[i].split()[1:]
            rows: list[list[float]] = []
            j = i + 2  # skip the header and the '---' rule line
            while j < len(lines):
                parts = lines[j].split()
                if not parts or not parts[0].isdigit():
                    break
                try:
                    values = [float(p) for p in parts[1:]]
                except ValueError:
                    break
                if len(values) == len(header):
                    rows.append(values)
                j += 1
            tables.append((header, rows))
            i = j
        else:
            i += 1
    return tables


def column(header: list[str], rows: list[list[float]], name: str) -> list[float]:
    idx = header.index(name)
    return [row[idx] for row in rows]


def build_points(
    process_corners, temperatures_c, supplies: dict
) -> list[harness_corners.PvtPoint]:
    """A mismatch campaign's PVT points, in the order `sample_seed` indexes."""
    corner_list = [harness_corners.CORNERS[name] for name in process_corners]
    return harness_corners.build_grid(
        corner_list, list(temperatures_c), [dict(supplies)]
    )


def claim_sigma_summary(outcomes, measurement: str) -> str:
    """`campaign.point_sigma_summary` over one named claim measurement."""
    return campaign.point_sigma_summary(
        outcomes, lambda outcome: outcome.values(measurement)
    )
