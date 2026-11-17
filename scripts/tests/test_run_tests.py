"""Regression tests for scripts/run_tests.py header ordering (issue #499).

``run_tests.py`` prints an ``== <module>`` header before spawning each module
on the inherited stdout. Python block-buffers stdout when it is not a TTY,
while each child writes the pipe directly, so an unflushed header stays in
the parent's buffer until exit and lands *after* every module's output --
labelling nothing in exactly the captured-output context (a pipe, never a
TTY) the header exists to serve.

Each test builds a scratch ``git init`` repo of trivial tracked modules and
runs the real ``run_tests.py`` against it with stdout captured. The scratch
cwd is load-bearing: module discovery is ``git ls-files`` relative to cwd, so
invoking ``run_tests.py`` from this repo's root would re-run the entire suite
-- including this file -- and recurse. Stdlib only.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_TESTS = ROOT / "scripts" / "run_tests.py"

PASS_MODULE = "test_aaa_pass.py"
FAIL_MODULE = "test_zzz_fail.py"
PASS_MARK = "AAA-PASS-MARK"
FAIL_MARK = "ZZZ-FAIL-MARK"

PASS_SOURCE = f"import sys\nprint({PASS_MARK!r})\n"
FAIL_SOURCE = f"import sys\nprint({FAIL_MARK!r})\nsys.exit(1)\n"
REPORT_SOURCE = (
    "import os, sys\n"
    "print('ENV-REPORT-MARK')\n"
    "print('PYTHONUNBUFFERED=' + os.environ.get('PYTHONUNBUFFERED', '<unset>'))\n"
)


def run_in_scratch_repo(sources):
    """git init + git add ``sources`` in a scratch dir (no commit needed --
    discovery reads the staged index), then run run_tests.py with that dir as
    cwd and stdout a pipe. Returns the CompletedProcess."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env.update(sources.get("__extra_env__", {}))
        # Measured against the unflushed script (issue #499): with
        # PYTHONUNBUFFERED inherited the headers order correctly anyway, so
        # without this scrub the ordering tests are a false green.
        env.pop("PYTHONUNBUFFERED", None)
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_SYSTEM"] = os.devnull
        for name, source in sources.items():
            if name.startswith("__"):
                continue
            (Path(tmpdir) / name).write_text(source)
        subprocess.run(["git", "init", "-q", "."], cwd=tmpdir, env=env, check=True)
        subprocess.run(["git", "add", "-A"], cwd=tmpdir, env=env, check=True)
        return subprocess.run(
            [sys.executable, str(RUN_TESTS)],
            cwd=tmpdir, capture_output=True, text=True, env=env,
        )


class HeaderOrderingTests(unittest.TestCase):

    def assert_header_precedes(self, proc, module, mark):
        lines = proc.stdout.splitlines()
        headers = [i for i, line in enumerate(lines) if line == f"== {module}"]
        marks = [i for i, line in enumerate(lines) if mark in line]
        self.assertEqual(len(headers), 1, f"one header for {module}: {lines!r}")
        self.assertEqual(len(marks), 1, f"one {mark!r} line: {lines!r}")
        self.assertLess(
            headers[0], marks[0],
            f"header for {module} must precede its module's output: {lines!r}")

    def test_header_precedes_module_output_when_stdout_captured(self):
        # capture_output gives run_tests.py a pipe -- the non-TTY
        # block-buffering case the defect lives in. One passing and one
        # failing module: ordering must hold for both, and the failing
        # module must still be reported.
        proc = run_in_scratch_repo(
            {PASS_MODULE: PASS_SOURCE, FAIL_MODULE: FAIL_SOURCE})
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assert_header_precedes(proc, PASS_MODULE, PASS_MARK)
        self.assert_header_precedes(proc, FAIL_MODULE, FAIL_MARK)

    def test_all_passing_scratch_repo_headers_still_ordered(self):
        proc = run_in_scratch_repo(
            {PASS_MODULE: PASS_SOURCE, "test_bbb_pass.py":
             PASS_SOURCE.replace(PASS_MARK, "BBB-PASS-MARK")})
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assert_header_precedes(proc, PASS_MODULE, PASS_MARK)
        self.assert_header_precedes(proc, "test_bbb_pass.py", "BBB-PASS-MARK")

    def test_child_env_scrubbed_of_pythonunbuffered(self):
        # With PYTHONUNBUFFERED=1 in the surrounding environment the buffered
        # path must still be exercised: the scrub drops it before the child
        # env, so the grandchild modules see it unset and the ordering
        # assertion below cannot be satisfied by the env var alone.
        proc = run_in_scratch_repo(
            {PASS_MODULE: PASS_SOURCE, "test_env_report.py": REPORT_SOURCE,
             "__extra_env__": {"PYTHONUNBUFFERED": "1"}})
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("PYTHONUNBUFFERED=<unset>", proc.stdout.splitlines())
        self.assert_header_precedes(proc, "test_env_report.py", "ENV-REPORT-MARK")


if __name__ == "__main__":
    unittest.main()
