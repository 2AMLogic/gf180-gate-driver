"""The scaffolding every `klt sim` request generator under `sim/*/klt/` shares.

A `klt sim` request is a JSON document; the generators in `sim/*/klt/` are the
deterministic scripts that write the committed `request-*.json` files cited as
sign-off evidence. Two parts of that document are *not* specific to any one
testbench:

* the **process axis** -- `corners.process`, the five MOS corner bundles, which
  is the same five-way `.lib`-section table `corners.CORNERS` already defines
  for the ngspice harness. It is derived here (``process_entries``) rather than
  re-typed, so the harness and the `klt sim` requests cannot disagree about what
  ``ss`` means.
* the **request envelope** -- `engine` / `models` / `batch` / `options`, the
  simulator, PDK model library, batch-submit policy and ngspice init every
  request in this repo carries identically (``envelope``).

Before issue #441 both lived as hand-typed copies in each generator: the
process table in three places (here, plus one dict per generator) and the
envelope in two. They agreed only because nobody had yet edited one of them.

Stdlib-only and import-cheap on purpose -- the generators run on the PDK-free
CI runner (`sim/test_gen_requests.py`), so this module must not pull in ngspice,
``klt``, or a located PDK. It deliberately imports only ``.corners``.

``envelope()`` returns freshly-built containers on every call: a generator may
mutate the request it is handed (``pex/gen_pex_requests.py`` re-points
``netlist`` and filters ``measurements``) without that leaking into the next one.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .corners import CORNERS, CORNER_SETS

#: Simulator the `klt sim` requests name. One engine in this repo.
ENGINE = "ngspice"

#: `models` -- the gf180mcu variant and the model library inside it, as
#: `klt sim` resolves them (the same pair `harness/pdk.py` locates on disk:
#: ``Pdk.model_lib`` is ``<variant>/libs.tech/ngspice/sm141064.ngspice``).
PDK_VARIANT = "gf180mcuD"
MODEL_LIB = "libs.tech/ngspice/sm141064.ngspice"

#: `batch` -- a runner-version mismatch warns rather than failing the submit,
#: and a submit that hits the vCPU-budgeted fleet with no capacity waits with
#: backoff instead of erroring out (`batch_no_capacity`).
RUNNER_VERSION_CHECK = "warn"
CAPACITY_WAIT_S = 1800

#: `options` -- per-unit wall-clock ceiling, no artefact retention (the report
#: is the evidence), and the two ngspice `set` lines that make `.meas` output
#: carry enough digits to be compared between runs.
TIMEOUT_S = 3000
KEEP_ARTIFACTS = False
NGSPICE_INIT: tuple[str, ...] = ("set measureprec=10", "set numdgt=10")

#: Which ``corners.CORNER_SETS`` entry the `klt sim` requests sweep by default:
#: the five classic MOS corners, the harness's own default corner set.
DEFAULT_PROCESS_SET = "mos"


def process_entries(names: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """The `corners.process` array: one ``{name, sections}`` entry per corner.

    ``names`` defaults to ``CORNER_SETS[DEFAULT_PROCESS_SET]`` (tt/ff/ss/fs/sf,
    in that order). ``sections`` is ``corners.CORNERS[name].sections`` converted
    to a list -- the harness holds it as a tuple for hashability, and the
    committed requests render it as a JSON array.
    """
    if names is None:
        names = CORNER_SETS[DEFAULT_PROCESS_SET]
    return [{"name": name, "sections": list(CORNERS[name].sections)} for name in names]


def envelope(
    netlist: str,
    corners: Mapping[str, Any],
    analysis: Mapping[str, Any],
    measurements: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """A complete `klt sim` request: the shared envelope around four fields.

    Key order is the order the committed `request-*.json` files carry, and both
    generators write ``json.dumps(..., indent=2)`` straight into the tree, so it
    is part of the committed bytes -- do not reorder.
    """
    return {
        "netlist": netlist,
        "engine": ENGINE,
        "models": {"pdk": PDK_VARIANT, "lib": MODEL_LIB},
        "corners": dict(corners),
        "batch": {
            "runner_version_check": RUNNER_VERSION_CHECK,
            "capacity_wait_s": CAPACITY_WAIT_S,
        },
        "analysis": dict(analysis),
        "measurements": list(measurements),
        "options": {
            "timeout_s": TIMEOUT_S,
            "keep_artifacts": KEEP_ARTIFACTS,
            "ngspice_init": list(NGSPICE_INIT),
        },
    }
