#!/usr/bin/env python3
"""Freshness gate for ``layout/gate_driver_core.provenance.json`` (issue #463).

The provenance file is the documented-provenance arm of the T1 item-2
attestation (``verification/signoff/layout.generic.json``): it pins the
sha256 of the committed GDS, its source netlist and its generator. Before
#463 nothing re-checked those hashes against the live tree, so the
attestation could go -- and with PR #466's generator edit briefly did go --
stale silently: CI's signoff job pins klt for *grading* only and the grader
hashes the GDS alone. This script anchors the chain to the live tree instead:

1. **Provenance freshness.** Recompute the sha256 of every pinned input
   (``layout``, ``source_netlist``, ``generator``) and compare it with the
   recorded value. Any mismatch fails, naming the artifact that moved and
   the direction to repair it: either the tree changed without a provenance
   refresh, or the tree is not the one attested. Since #528 a fourth arm
   pins the generator's ``layout/common/`` import closure
   (``generator_deps``): after PR #517 the generator's klt argv assembly
   (``common/klt_report.py``) and binary resolution (``common/klt_env.py``)
   live outside the pinned generator file, so those bytes co-determine the
   committed GDS. The closure is *derived* from the live generator's own
   imports rather than trusted from the record, so a generator that gains
   or loses a common import fails here until the provenance record says so.
2. **klt drift (advisory).** When a ``klt`` is on ``PATH``, compare the host
   ``klt --version`` with the recorded ``tools.klt_version``. Byte-equality
   against the committed GDS is *not* expected to hold under a different
   klt: 0.9.2 renames generated sub-cells, which rewrites most of the stream
   without touching geometry (#463). Per #470 the host tool moving ahead of
   committed evidence is the normal condition on a shared worker, not an
   error, so this arm prints the drift and its consequence and exits zero.
   It is skipped cleanly when no ``klt`` is available -- CI's signoff runner
   installs klt for grading only and cannot generate layout anyway.

Stdlib-only, like ``verification/signoff/check_tier_report.py``: no klt
generation install, no KLayout, no PDK, so it runs on the PDK-free signoff
runner. It never regenerates the GDS (that is a deliberate re-attestation
decision, out of #463's scope); it only re-hashes what is already committed.

Usage (repo root or anywhere beneath it)::

    python3 layout/check_layout_provenance.py
    python3 layout/check_layout_provenance.py --klt /path/to/klt
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = REPO_ROOT / "layout" / "gate_driver_core.provenance.json"

# Which provenance blocks pin a live-tree input, and the human label for
# each. Keys double as the failure prefix so a failing block names itself.
PINNED_INPUTS = (
    ("layout", "committed GDS"),
    ("source_netlist", "source netlist"),
    ("generator", "generator"),
)


class KltVersionError(RuntimeError):
    """``klt --version`` exists but does not run clean."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def klt_version(binary: str = "klt") -> str | None:
    """Host ``klt --version`` output, or ``None`` when unavailable.

    An absent binary and a failing ``--version`` are both "cannot ask the
    host tool" -- the advisory arm is skipped, never a hard failure.
    """
    resolved = shutil.which(binary)
    if resolved is None:
        return None
    try:
        proc = subprocess.run(
            [resolved, "--version"], capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise KltVersionError(f"cannot launch {resolved!r}: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip() or f"exit {proc.returncode}"
        raise KltVersionError(f"klt --version did not run clean: {detail}")
    version = proc.stdout.strip()
    return version or None


def check_pinned_inputs(provenance: dict, repo_root: Path = REPO_ROOT) -> list[str]:
    """Every pinned input hash matches the live tree.

    Returns human-readable failure messages (empty = pass). Paths are
    repo-relative, exactly as the generator records them; an absolute or
    escaping path is a failure, not something to resolve against the host.
    """
    failures: list[str] = []
    for block, label in PINNED_INPUTS:
        entry = provenance.get(block)
        if not isinstance(entry, dict):
            failures.append(
                f"{block}: provenance records no '{block}' object -- the {label} pin is missing"
            )
            continue
        rel, recorded = entry.get("path"), entry.get("sha256")
        if not isinstance(rel, str) or not rel:
            failures.append(f"{block}: provenance '{block}' block names no path")
            continue
        if not isinstance(recorded, str) or not recorded:
            failures.append(f"{block}: provenance '{block}' block records no sha256")
            continue
        if Path(rel).is_absolute():
            failures.append(
                f"{block}: pinned path {rel!r} is absolute -- provenance pins live-tree "
                f"inputs with repo-relative paths"
            )
            continue
        artifact = repo_root / rel
        try:
            artifact.resolve().relative_to(repo_root.resolve())
        except ValueError:
            failures.append(f"{block}: pinned path {rel!r} escapes the repository")
            continue
        if not artifact.is_file():
            failures.append(
                f"{block}: pinned {label} does not exist: {rel} -- the tree is not the "
                f"one the provenance describes"
            )
            continue
        actual = sha256_file(artifact)
        if actual != recorded.removeprefix("sha256:"):
            failures.append(
                f"{block}: stale pin -- provenance records sha256:{recorded.removeprefix('sha256:')} "
                f"for {rel} but the live file is sha256:{actual}; either the {label} changed "
                f"without a provenance refresh (re-derive it, #463) or restore the attested file"
            )
    return failures


def generator_common_imports(generator_path: Path) -> dict[str, Path]:
    """The ``layout/common/`` import closure of ``generator_path``.

    Absolute ``import X`` / ``from X import ...`` statements are kept when a
    ``common/X.py`` exists beside the generator, and those files' own imports
    are walked the same way (``klt_report`` imports ``klt_env``), so the
    result is the transitive closure of local modules the generator's
    execution reads: module name -> path, sorted by module name. A file that
    does not parse contributes no imports; that cannot hide a drift, because
    the generator's own bytes are pinned by the ``generator`` block and a
    dependency's by its ``generator_deps`` entry.
    """
    common = generator_path.parent / "common"
    closure: dict[str, Path] = {}
    pending = [generator_path]
    seen: set[Path] = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            tree = ast.parse(current.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            continue
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.append(node.module)
        for name in names:
            top = name.split(".")[0]
            candidate = common / f"{top}.py"
            if top not in closure and candidate.is_file():
                closure[top] = candidate
                pending.append(candidate)
    return dict(sorted(closure.items()))


def check_generator_deps(
    provenance: dict, repo_root: Path = REPO_ROOT
) -> tuple[list[str], list[str]]:
    """Every ``layout/common/`` module the live generator imports is pinned.

    #528: PR #517 moved the generator's klt invocation into
    ``common/klt_report.py`` (argv assembly, ``cwd``, ``ok_codes``) and its
    binary resolution into ``common/klt_env.py``, so an edit to either could
    change what the generator runs while every recorded hash still matched.
    The pinned set is derived from the live generator's imports and compared
    with the record in both directions, so the gap cannot reopen by a
    hand-listed record quietly going small.

    Returns ``(failures, closure_module_names)`` -- the second element feeds
    the anchor line so a pass names what was checked.
    """
    gen = provenance.get("generator")
    rel = gen.get("path") if isinstance(gen, dict) else None
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute():
        # Malformed/absolute/escaping generator path: the generator pin above
        # already named it; there is nothing to walk.
        return [], []
    generator = repo_root / rel
    try:
        generator.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return [], []
    if not generator.is_file():
        return [], []

    live = generator_common_imports(generator)
    failures: list[str] = []
    recorded = provenance.get("generator_deps")
    if recorded is None:
        if live:
            failures.append(
                "generator_deps: provenance records no generator_deps while the live "
                f"generator imports {', '.join(live)} from layout/common/ -- those "
                "bytes co-determine the GDS (issue #528); refresh the record (a "
                "GDS-neutral edit refreshes its pins with a same-klt comparison, "
                "the PR #478/#517 pattern)"
            )
        return failures, list(live)
    if not isinstance(recorded, list):
        return ["generator_deps: records a non-list generator_deps block"], list(live)

    pinned: dict[str, dict] = {}
    for i, entry in enumerate(recorded):
        if isinstance(entry, dict) and isinstance(entry.get("module"), str) and entry["module"]:
            pinned[entry["module"]] = entry
        else:
            failures.append(f"generator_deps[{i}]: entry names no module")
    for module, path in live.items():
        rel_live = path.relative_to(repo_root).as_posix()
        entry = pinned.get(module)
        if entry is None:
            failures.append(
                f"generator_deps: the live generator imports {module} ({rel_live}) but "
                "the record pins no hash for it -- an unpinned behavioural input, "
                "the #528 gap"
            )
            continue
        if entry.get("path") != rel_live:
            failures.append(
                f"generator_deps[{module}]: recorded path {entry.get('path')!r} is not "
                f"the live import target {rel_live!r}"
            )
            continue
        recorded_hash = entry.get("sha256")
        if not isinstance(recorded_hash, str) or not recorded_hash:
            failures.append(f"generator_deps[{module}]: records no sha256")
            continue
        actual = sha256_file(path)
        if actual != recorded_hash.removeprefix("sha256:"):
            failures.append(
                f"generator_deps[{module}]: stale pin -- provenance records "
                f"sha256:{recorded_hash.removeprefix('sha256:')} for {rel_live} but the "
                f"live file is sha256:{actual}; either the module changed without a "
                "provenance refresh (re-derive it, #463/#528) or restore the attested file"
            )
    for module in sorted(set(pinned) - set(live)):
        failures.append(
            f"generator_deps[{module}]: stale pin -- records "
            f"{pinned[module].get('path')!r} but the live generator's layout/common/ "
            "import closure does not include it (the import was removed, or the module "
            "file is gone); refresh the record"
        )
    return failures, list(live)


def klt_drift_advisory(provenance: dict, host_version: str | None) -> str | None:
    """The advisory sentence for a host klt differing from the recorded build."""
    recorded = (provenance.get("tools") or {}).get("klt_version")
    if host_version is None or not isinstance(recorded, str) or not recorded:
        return None
    if host_version == recorded:
        return None
    return (
        f"ADVISORY: klt drift -- provenance records '{recorded}' (the build that "
        f"generated the committed GDS) but the host runs '{host_version}'. "
        f"Byte-equality against the committed gate_driver_core.gds is NOT expected "
        f"to hold under a different klt build (0.9.2 renames generated sub-cells, "
        f"issue #463); the pinned-input hashes above are unaffected. This arm is "
        f"advisory by design (#470): the host tool moving ahead of committed "
        f"evidence is the normal condition, not an error."
    )


def run_check(
    provenance_path: Path = PROVENANCE,
    repo_root: Path = REPO_ROOT,
    klt: str = "klt",
    klt_runner=klt_version,
) -> tuple[int, str]:
    """Run both arms against ``provenance_path``; returns ``(exit_code, output)``.

    ``klt_runner`` is injectable so the tests can exercise absent, matching,
    drifted and failing klt binaries without one on ``PATH``.
    """
    lines: list[str] = []
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        if not isinstance(provenance, dict):
            raise ValueError("top-level JSON value is not an object")
    except (OSError, ValueError) as exc:
        return 1, f"FAIL: cannot read provenance {provenance_path}: {exc}\n"

    failures = check_pinned_inputs(provenance, repo_root=repo_root)
    dep_failures, dep_names = check_generator_deps(provenance, repo_root=repo_root)
    failures += dep_failures
    dep_note = (
        f" + {len(dep_names)} generator_deps module(s) ({', '.join(dep_names)})"
        if dep_names
        else " + 0 generator_deps module(s)"
    )
    lines.append(
        f"pin anchor     : {len(PINNED_INPUTS)} pinned input(s) checked "
        f"(layout, source_netlist, generator){dep_note}"
    )

    try:
        host_version = klt_runner(klt)
    except KltVersionError as exc:
        host_version = None
        lines.append(f"klt version    : skipped ({exc}) -- advisory arm only")
    if host_version is None:
        lines.append("klt version    : no klt on PATH -- version-drift advisory arm skipped (not a failure)")
    else:
        advisory = klt_drift_advisory(provenance, host_version)
        if advisory:
            lines.append(f"klt version    : {host_version}")
            lines.append(advisory)
        else:
            recorded = (provenance.get("tools") or {}).get("klt_version")
            lines.append(f"klt version    : {host_version} matches the recorded build" if host_version == recorded
                         else f"klt version    : {host_version} (no recorded klt_version to compare)")

    if failures:
        for failure in failures:
            lines.append(f"FAIL: {failure}")
        return 1, "\n".join(lines) + "\n"
    lines.append(f"PASS: {provenance_path.name} pins match the live tree")
    return 0, "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--klt", default="klt", help="klt binary for the advisory version arm (default: PATH)")
    args = parser.parse_args()
    code, output = run_check(klt=args.klt)
    print(output, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
