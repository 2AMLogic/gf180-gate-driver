#!/usr/bin/env python3
"""Send storable ``layout/`` signoff outputs through the fleet artifact store (issue #348).

The ``layout/{drc,lvs,erc}`` runners and negative controls used to commit every
byte they wrote under ``layout/<tool>/reports/``. Most of those bytes are
write-only: nothing in the tree reads them back. They now go to the artifact
store through ``sim/harness/evidence_store.py`` (``klt artifact put``, the same
writer ``sim/`` uses since #333) and git keeps one manifest per run,
``manifests/artifacts/<bench>-<record-id>.manifest.json``.

Which kinds stay in git is a decision, not a default (``layout/README.md``,
"Stored vs committed signoff outputs"):

* **committed**: the ``drc.json`` / ``lvs.json`` / ``erc.json`` envelopes of a
  block's own run, which ``verification/signoff/check_tier_report.py`` opens by
  path from the tree. The runners write these exactly as before, but only
  *after* the store succeeded.
* **stored**: everything else a run writes (text twins, request records,
  per-run extracted netlists, extraction JSON, negative-control output).

A runner stages the stored kinds under ``layout/build/evidence/<bench>/<rid>/``
(git-ignored) laid out as they would sit under ``reports/``, calls
:func:`store_or_exit`, and only then writes the committed envelope.

**Fail closed**, as in ``evidence_store``: no broker, no ``klt artifact``, a
put that fails, a manifest that does not match the bytes -- all raise
``StoreError`` here, the runner exits ``EXIT_NOT_STORED`` and nothing is
committed. There is no fallback that commits the bytes instead. The staged
bytes stay in the scratch tree, which is also where a deliberate *promotion*
copies a file from when an extraction becomes an input (a DUT header or a CI
step names it): copy it to ``reports/`` under the same name and commit it.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "sim"))

from harness import evidence_store as es  # noqa: E402

import report_id  # noqa: E402

StoreError = es.StoreError
EXIT_NOT_STORED = es.EXIT_NOT_STORED
STAGE_ROOT = Path("layout") / "build" / "evidence"


def stage_dir(repo_root: Path, bench: str, rid: str) -> Path:
    """Fresh git-ignored scratch dir for one run (``layout/build/`` is ignored)."""
    return es.stage_dir(repo_root, bench, rid, root=STAGE_ROOT)


def new_record_id(repo_root: Path, bench: str, reports_dir: Path,
                  when: _dt.datetime | None = None, sha: str | None = None) -> str:
    """First record id that neither ``reports_dir`` nor the manifests claim.

    ``report_id.record_id`` only sees files in ``reports_dir``; a run whose
    outputs are all stored leaves nothing there, so a same-second rerun would
    collide on the manifest instead.
    """
    when = when or _dt.datetime.now(_dt.timezone.utc)
    sha = sha or report_id.short_sha(repo_root)
    while True:
        rid = report_id.record_id(reports_dir, when, sha)
        if not (es.manifest_path(repo_root, bench, rid).exists()
                or (repo_root / STAGE_ROOT / bench / rid).exists()):
            return rid
        when += _dt.timedelta(seconds=1)


def preflight_or_exit(repo_root: Path = REPO_ROOT) -> None:
    """Refuse to start a run whose outputs could not be stored.

    A pass-through to :func:`evidence_store.preflight_or_exit` that adds only
    the ``REPO_ROOT`` default, kept so a ``layout/`` runner reaches the whole
    store through one facade rather than importing ``evidence_store`` for this
    one call. The preflight itself is not signoff-specific -- it checks the
    broker and ``klt``, which both halves share.
    """
    es.preflight_or_exit(repo_root)


def store(stage: Path, *, repo_root: Path, bench: str, rid: str,
          name_prefix: str, put=None) -> Path:
    """Put every staged file and install the run's manifest; return its path.

    ``name_prefix`` is the logical directory the bytes would have had in git
    (``layout/lvs/reports/<block>``); each manifest ``name`` is that prefix plus
    the staged relative path. Raises :class:`StoreError` on any failure, with
    nothing installed.

    The refuse-if-exists / put / install-manifest core is
    :func:`evidence_store.store_manifest_only` -- the same code ``store_files``
    runs, so "fail closed, as in ``evidence_store``" is a call here and cannot
    drift from it. There is no ``also_refuse``: a signoff run commits only the
    manifest, so the manifest is the only path to guard.
    """
    files = es.stage_files(stage, name_prefix)
    mpath, _manifest, _empty = es.store_manifest_only(
        files, repo_root=repo_root, bench=bench, rid=rid, put=put)
    return mpath


def store_or_exit(stage: Path, *, repo_root: Path, bench: str, rid: str,
                  name_prefix: str, put=None) -> Path:
    """:func:`store`, but a failure reports and exits ``EXIT_NOT_STORED``."""
    try:
        return store(stage, repo_root=repo_root, bench=bench, rid=rid,
                     name_prefix=name_prefix, put=put)
    except StoreError as exc:
        print(es.not_stored_message(exc, stage, subject="SIGNOFF OUTPUT"), file=sys.stderr)
        raise SystemExit(EXIT_NOT_STORED) from None
