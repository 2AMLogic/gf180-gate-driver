#!/usr/bin/env python3
"""Freshness gate for the committed ``klt signoff`` block manifest.

``verification/signoff/manifest.json`` (issue #239) declares this block's
``kind`` and, per T1 item, the evidence envelope that backs it, each pinned to
the ``content_hash`` of the artifact the check actually ran against.
``klt signoff --manifest`` alone cannot catch a *file-backed* citation going
stale: it compares the manifest's pin against the envelope's own recorded
``provenance.input.content_hash`` -- two committed values that agree even
after the cited artifact has since changed. This script anchors the chain to
the live tree instead, in two passes:

1. **Pin anchor.** For every manifest citation, re-resolve which committed
   artifact the pin refers to (per envelope kind -- see ``INPUT_PATH_FIELDS``)
   and recompute its sha256. A manifest citing an artifact that has since
   changed fails here rather than rotting.
2. **Report reproducibility.** Re-run ``klt signoff --manifest ... --format
   json`` and compare the fresh grading against the committed
   ``tier-report.json``. Any drift -- an envelope edited, a pin changed, a
   klt release whose bundled tiers doc grades differently -- fails here.

Artifact-bound generic envelopes (T1 items 1, 2, 9, 10; klayout-tools#2843)
are anchored through their *declared* ``provenance.input.path`` -- a string
resolved beside the envelope, or a ``{"path", "scope": "repo"}`` object
resolved from the repo root -- never through ``source``. A malformed declared
path is a failure, not a fallback. Only an envelope that declares no
``provenance.input.path`` at all (item 8's legacy form) falls back to
``source``. Inventory artifacts (``*.inventory.md``) additionally have every
``path`` + ``sha256:`` pair they list re-hashed against the live tree.

Exit code ``3`` from the re-run is *success*: ``klt signoff`` renders
``tier: null`` whenever at least one T1 item is honestly ``unmet``, which is
this block's real state and the whole point of the manifest (#239: a
near-all-``unmet`` manifest is the honest machine-readable statement of the
gap, not a failure to grade). Exit ``0`` is the same success once the block
reaches T1. Only exit ``1``/``2`` (bad manifest, unreadable evidence) or a
compare mismatch fails CI.

Stdlib-only, like everything in this repo. CI installs klt from the pinned
source commit in `.github/workflows/ci.yml` (the PyPI 0.5.0 wheel predates
the eleventh tiers item and the report schema this record uses):
``klt signoff`` reads JSON envelopes and parses the bundled tiers doc, it
never touches the klayout module or a PDK.

Usage (repo root or anywhere beneath it)::

    python3 verification/signoff/check_tier_report.py
    python3 verification/signoff/check_tier_report.py --klt /path/to/klt
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIGNOFF_DIR = Path(__file__).resolve().parent
MANIFEST = SIGNOFF_DIR / "manifest.json"
TIER_REPORT = SIGNOFF_DIR / "tier-report.json"

# Which envelope field names the artifact a citation's ``content_hash`` pins,
# and how that field resolves. Keys are resolved by :func:`envelope_kind` from
# the envelope's own shape -- never trusted from the manifest -- so a manifest
# that swaps an envelope for another kind fails loudly below instead of being
# anchored against the wrong file. Extend this table before citing a new kind
# (``sim``/``yield``/``pex`` today) in the manifest; an unmapped kind is a
# check failure, not a skip.
INPUT_PATH_FIELDS = {
    "drc": ("file", "repo_root"),  # emitted with cwd = repo root (run_drc.py)
    "lvs": ("layout", "envelope_dir"),  # request-relative (run_lvs.py's request builder)
    "extract": ("file", "repo_root"),  # emitted with cwd = repo root (run_lvs.py step 2)
    "generic": ("source", "repo_root"),
    "erc": ("file", "repo_root"),  # emitted with cwd = repo root (run_erc.py)
}

RENDER_EXIT_CODES = (0, 3)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def envelope_kind(envelope: dict) -> str | None:
    """Kind of a ``klt`` JSON envelope from its own discriminating shape.

    The five shapes the manifest may cite today; mirrors
    ``docs/cli/signoff.md``'s "Envelope validation" table, restricted to what
    ``INPUT_PATH_FIELDS`` can anchor.
    """
    if envelope.get("kind") == "generic":
        return "generic"
    if "violations" in envelope:
        return "drc"
    if "mismatches" in envelope:
        return "lvs"
    if "device_count" in envelope:
        return "extract"
    if "erc_findings" in envelope:
        return "erc"
    return None


def _citation_entries(item_id: str, entry: object) -> list[tuple[str, object]]:
    """Normalize one ``evidence`` value to its per-citation entries.

    A value is either a single citation object, or -- for the one compound
    item no single artifact proves (T1 item 11, power delivery: an ``erc``
    report plus the item-4 ``lvs`` report) -- a JSON list of them, exactly
    as ``klt signoff``'s compound-evidence path resolves it. Each element
    is anchored independently, with its list index in the failure label so
    a multi-citation item names which half went stale.
    """
    if isinstance(entry, list):
        return [(f"{item_id}[{i}]", sub) for i, sub in enumerate(entry)]
    return [(item_id, entry)]


INVENTORY_SUFFIX = ".inventory.md"
# `path` followed (same table row, or the next few tokens) by `sha256:<hex>`.
_LISTED_HASH = re.compile(r"`([\w./-]+)`[\s(|]*(?:sha256\s+)?`(sha256:[0-9a-f]{64})`")


def resolve_declared_input(envelope: dict, envelope_path: Path, repo_root: Path) -> tuple[Path | None, str | None]:
    """Resolve an explicit ``provenance.input.path`` binding.

    Returns ``(artifact, None)`` on success, ``(None, error)`` when a path is
    declared but unusable, and ``(None, None)`` when no path is declared at
    all (the caller then applies the legacy ``source`` rule). Semantics follow
    klayout-tools docs/cli/signoff.md: a string resolves beside the envelope;
    an object must be ``{"path": <str>, "scope": "repo"}`` and resolves from
    the repo root.
    """
    provenance = envelope.get("provenance")
    input_block = provenance.get("input") if isinstance(provenance, dict) else None
    if not isinstance(input_block, dict) or "path" not in input_block:
        return None, None
    declared = input_block["path"]
    if isinstance(declared, str):
        name, base = declared, envelope_path.parent
    elif isinstance(declared, dict):
        name = declared.get("path")
        if declared.get("scope") != "repo":
            return None, f"provenance.input.path object must carry scope 'repo', got {declared.get('scope')!r}"
        base = repo_root
    else:
        return None, f"provenance.input.path must be a string or a {{path, scope}} object, got {type(declared).__name__}"
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        return None, f"provenance.input.path names no usable relative path: {name!r}"
    artifact = (base / name).resolve()
    try:
        artifact.relative_to(repo_root.resolve())
    except ValueError:
        return None, f"provenance.input.path resolves outside the repository: {artifact}"
    return artifact, None


def check_inventory_hashes(artifact: Path, repo_root: Path) -> list[str]:
    """Every ``path`` + ``sha256:`` pair an inventory lists matches the live file."""
    failures: list[str] = []
    text = artifact.read_text(encoding="utf-8")
    pairs = _LISTED_HASH.findall(text)
    if not pairs:
        return [f"inventory {artifact.name} lists no `path` + `sha256:` pairs to anchor"]
    for rel, listed in pairs:
        target = repo_root / rel
        if not target.is_file():
            failures.append(f"inventory {artifact.name}: listed file does not exist: {rel}")
            continue
        actual = sha256_file(target)
        if actual != listed:
            failures.append(
                f"inventory {artifact.name}: stale listing for {rel} -- inventory says {listed} "
                f"but the live file is {actual}; re-audit and refresh the inventory"
            )
    return failures


def anchor_citations(manifest: dict, repo_root: Path = REPO_ROOT) -> list[str]:
    """Pass 1: every pinned citation names the live artifact it pins.

    Returns a list of human-readable failure messages (empty = pass).
    """
    failures: list[str] = []
    evidence = manifest.get("evidence")
    if not isinstance(evidence, dict):
        return [f"manifest has no evidence object: {MANIFEST}"]
    for item_id, raw_entry in sorted(evidence.items()):
        for label, entry in _citation_entries(item_id, raw_entry):
            if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
                failures.append(f"item {label}: entry is not file-backed (object with 'file')")
                continue
            pin = entry.get("content_hash")
            if not isinstance(pin, str):
                failures.append(f"item {label}: citation pins no content_hash -- unpinned citations cannot be freshness-verified at all (#239)")
                continue
            envelope_path = repo_root / entry["file"]
            try:
                envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                failures.append(f"item {label}: cannot read evidence envelope {entry['file']}: {exc}")
                continue
            kind = envelope_kind(envelope)
            if kind not in INPUT_PATH_FIELDS:
                failures.append(
                    f"item {label}: evidence {entry['file']} has no anchorable input path "
                    f"(kind={kind!r}) -- extend INPUT_PATH_FIELDS before citing it"
                )
                continue
            artifact = None
            declared = None
            if kind == "generic":
                artifact, error = resolve_declared_input(envelope, envelope_path, repo_root)
                if error:
                    failures.append(f"item {label}: generic envelope {entry['file']}: {error}")
                    continue
                declared = artifact is not None
            if declared:
                if envelope.get("t1_item") != int(item_id) or isinstance(envelope.get("t1_item"), bool):
                    failures.append(
                        f"item {label}: envelope {entry['file']} declares t1_item "
                        f"{envelope.get('t1_item')!r}, cited for item {item_id}"
                    )
                    continue
            else:
                field, base = INPUT_PATH_FIELDS[kind]
                input_name = envelope.get(field)
                if not isinstance(input_name, str) or not input_name:
                    failures.append(f"item {label}: {kind} envelope {entry['file']} names no input path in '{field}'")
                    continue
                anchor_root = envelope_path.parent if base == "envelope_dir" else repo_root
                artifact = (anchor_root / input_name).resolve()
            if not artifact.is_file():
                failures.append(f"item {label}: cited artifact does not exist: {artifact}")
                continue
            actual = sha256_file(artifact)
            if actual != pin:
                failures.append(
                    f"item {label}: stale citation -- manifest pins {pin} "
                    f"but the live artifact {artifact} is now {actual}; "
                    f"re-run the evidence and refresh the manifest + tier-report"
                )
                continue
            if declared and artifact.name.endswith(INVENTORY_SUFFIX):
                failures += [f"item {label}: {m}" for m in check_inventory_hashes(artifact, repo_root)]
    return failures


def render_fresh_report(klt: str) -> tuple[int, dict | None, str]:
    """Pass 2: re-run the grader and return (exit, report, stderr)."""
    try:
        proc = subprocess.run(
            [klt, "signoff", "--manifest", str(MANIFEST), "--format", "json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError) as exc:
        return 127, None, f"cannot launch klt {klt!r}: {exc}"
    if proc.returncode not in RENDER_EXIT_CODES:
        detail = (proc.stderr or proc.stdout).strip() or f"exit {proc.returncode}"
        return proc.returncode, None, detail
    try:
        return proc.returncode, json.loads(proc.stdout), ""
    except ValueError as exc:
        return proc.returncode, None, f"klt signoff stdout was not valid JSON: {exc}"


def first_difference(fresh: dict, committed: dict) -> str | None:
    if fresh == committed:
        return None
    for key in ("block", "kind", "tier", "t1_item_count", "t1_met_count", "source_doc", "source_doc_content_hash"):
        if fresh.get(key) != committed.get(key):
            return f"{key}: committed {committed.get(key)!r} vs fresh {fresh.get(key)!r}"
    for item in fresh.get("items", []):
        if item.get("tier") != "T1":
            continue
        matching = [
            committed_item
            for committed_item in committed.get("items", [])
            if committed_item.get("id") == item.get("id")
        ]
        if not matching:
            return f"item {item.get('id')} is missing from the committed report"
        committed_item = matching[0]
        if committed_item == item:
            continue
        for field in ("status", "reason", "citation"):
            if committed_item.get(field) != item.get(field):
                return (
                    f"item {item.get('id')} ({item.get('title')}) {field}: "
                    f"committed {committed_item.get(field)!r} vs fresh {item.get(field)!r}"
                )
    return "reports differ in a way not covered field-by-field -- re-inspect them"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--klt", default="klt", help="klt binary to re-run the grading with (default: PATH)")
    args = parser.parse_args()

    failures: list[str] = []
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"FAIL: cannot read block manifest {MANIFEST}: {exc}")
        return 1
    try:
        committed = json.loads(TIER_REPORT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"FAIL: cannot read committed tier report {TIER_REPORT}: {exc}")
        return 1

    failures += anchor_citations(manifest)
    citation_count = sum(
        len(_citation_entries(item_id, entry))
        for item_id, entry in manifest.get("evidence", {}).items()
    )
    print(f"pin anchor     : {citation_count} pinned citation(s) checked")

    exit_code, fresh, detail = render_fresh_report(args.klt)
    if fresh is None:
        print(f"FAIL: fresh klt signoff render did not run clean: {detail}")
        return 1
    print(f"fresh render   : klt signoff exit {exit_code} (0 = tier T1, 3 = rendered with honest unmet items)")
    diverged = first_difference(fresh, committed)
    if diverged:
        failures.append(f"committed tier-report.json is stale: {diverged}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: manifest citations anchored to the live tree; committed tier report reproduced exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
