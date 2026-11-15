#!/usr/bin/env python3
"""Run every tracked test_*.py module.

    python3 scripts/run_tests.py

`npm test` calls this. The module set is discovered from `git ls-files`
(same pattern .github/scripts/lint.sh step 5/5 enforces on CI), so a newly
tracked test_*.py is picked up without a second list to maintain.
Stdlib only, no virtualenv required.
"""

import re
import subprocess
import sys

EXCLUDED_PREFIXES = (".loom/", ".claude/", ".agents/")
TEST_PATH_RE = re.compile(r"(^|/)test_[^/]*\.py$")


def tracked_test_modules():
    listing = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    )
    return [
        path
        for path in listing.stdout.splitlines()
        if TEST_PATH_RE.search(path) and not path.startswith(EXCLUDED_PREFIXES)
    ]


def main():
    modules = tracked_test_modules()
    if not modules:
        print("run_tests: no tracked test_*.py modules found", file=sys.stderr)
        return 1
    failures = []
    for module in modules:
        print(f"== {module}")
        if subprocess.run([sys.executable, module]).returncode != 0:
            failures.append(module)
    passed = len(modules) - len(failures)
    print(f"\n{passed}/{len(modules)} test module(s) passed")
    for module in failures:
        print(f"FAIL: {module}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
