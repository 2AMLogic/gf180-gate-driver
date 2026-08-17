#!/usr/bin/env bash
# Regression test for .loom/hooks/guard-destructive-generic.sh's
# catastrophic-tier SQL_DDL_PATTERN check false-denying a `gh api ... --jq
# '<filter>'` read-only jq filter string that merely quotes/tests-for a SQL
# DDL phrase (e.g. "DROP TABLE"), rather than the phrase ever being live SQL
# executed against a real database (issue #170).
#
# Usage: ./.loom/hooks/tests/test-guard-sql-ddl-jq-prose.sh
#
# Provenance: `.loom/logs/guard-decisions.log` recorded 13 `catastrophic`-tier
# `deny` events under the `sql-ddl` pattern over 2026-08-16/17, none of which
# were real SQL DDL execution. The freshest repro (2026-08-17T15:11:18Z-ish,
# from an Auditor pass) was a **read-only** issue-title search:
#   gh api repos/OWNER/REPO/issues --jq 'select(.title | test("(?i)sql-ddl|DROP TABLE"))'
# -- no SQL, no execution, just a substring/regex test inside a jq filter --
# yet it was denied: "BLOCKED: Command matches dangerous pattern: DROP TABLE".
#
# Root cause: SQL_DDL_PATTERN (~line 4142) scans COMMAND_ASK_SCAN, which is
# built by strip_literal_text() redacting the quoted VALUE following a set of
# known text-carrying flags (--body/-m/--message/--title/--notes/--comment/
# --search/--arg/--argjson). `--jq` was missing from that flag list (both
# strip_literal_text()'s own FLAG_RE_BOL/FLAG_RE_MID regexes AND the three
# substring pre-check gates that decide whether to invoke it at all), even
# though a `--jq` filter string is exactly as read-only/non-executing as the
# `--search` value already handled by #5797 -- gh's `--jq` never runs its
# argument as a shell command, only as a jq filter program.
#
# This is the same false-positive CLASS already fixed for the sibling
# catastrophic-rm/heredoc-prose guard (#149/#154,
# test-guard-catastrophic-body-prose.sh) and the ask-tier `git clean -fd`
# substring guard (#90/#112/#122, test-guard-git-clean-scope.sh): a raw
# substring/regex match over command TEXT fires on the phrase appearing in
# prose/a search filter, not just on the phrase being executed as a real
# command.
#
# Covers, end-to-end through the real PreToolUse JSON protocol:
#   (a) the issue's exact repro shape: `gh api ... --jq 'select(.title |
#       test("(?i)sql-ddl|DROP TABLE"))'` -> ALLOW
#   (b) a `gh issue list --jq` variant with a plain grep-style DDL phrase
#       filter, confirming the fix isn't `gh api`-subcommand-specific ->
#       ALLOW
#   (c) safety floor: a REAL, live, unquoted SQL DDL invocation (`psql -c
#       "DROP TABLE users"`) must still resolve DENY, so (a)-(b) can't be
#       satisfied by an over-broad mask
#   (d) safety floor: the dangerous phrase smuggled via a LIVE `$(...)`
#       command substitution nested inside ANOTHER flag's (`--body`) quoted
#       value, with an unrelated `--jq` flag present elsewhere in the same
#       command (exercises the substring pre-check gates, not just the
#       regex) -> still DENY (the `$(`-floor strip_literal_text() already
#       has for every other text-carrying flag)
#   (e) safety floor: the dangerous phrase smuggled via a LIVE `$(...)`
#       command substitution nested directly INSIDE the `--jq` value itself
#       -> still DENY (the `$(`-floor applies to `--jq`'s own quoted span,
#       not just other flags')
#
# The hook under test is the canonical source at .loom/hooks/ (this repo
# ships no defaults/ tree -- see the file's own banner), copied into an
# isolated temp git tree alongside its config-resolver.sh/canonical-path.sh
# lib dependencies so MAIN_ROOT/git-common-dir resolve inside the temp tree,
# exactly like test-guard-catastrophic-body-prose.sh does for the same hook.
# Exit 0 = all pass, 1 = fail.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SRC_HOOK="$REPO_ROOT/.loom/hooks/guard-destructive-generic.sh"

PASS=0
FAIL=0
TOTAL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); printf "${GREEN}PASS${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "${RED}FAIL${NC} %s\n" "$1"; }

# Build the dangerous phrase from parts so this test FILE's own text never
# contains the literal substring "DROP TABLE" contiguously -- avoids tripping
# this same guard on any future Bash invocation that greps/cats this file
# (matching the convention already used by every sibling suite in this
# directory).
DROPTBL="DROP TAB""LE"

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT
git init -q "$TMPROOT"
mkdir -p "$TMPROOT/.loom/hooks" "$TMPROOT/.loom/scripts/lib"
cp "$SRC_HOOK" "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
chmod +x "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
cp "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" "$TMPROOT/.loom/scripts/lib/config-resolver.sh"
cp "$REPO_ROOT/.loom/scripts/lib/canonical-path.sh" "$TMPROOT/.loom/scripts/lib/canonical-path.sh"
HOOK="$TMPROOT/.loom/hooks/guard-destructive-generic.sh"

# Build stdin JSON for a Bash tool_input, with cwd fixed at TMPROOT (the
# synthetic main checkout).
make_input() {
    local command="$1"
    jq -n --arg cmd "$command" --arg cwd "$TMPROOT" \
        '{tool_input: {command: $cmd}, cwd: $cwd}'
}

# Run the hook from inside the temp tree so git-common-dir resolves to it.
# Prints "<exit_code>|<stdout>".
run_hook() {
    local command="$1"
    local exit_code=0 output
    output=$(cd "$TMPROOT" && bash "$HOOK" < <(make_input "$command") 2>/dev/null) || exit_code=$?
    printf '%s|%s' "$exit_code" "$output"
}

assert_allow() {
    local desc="$1" result="$2"
    local code="${result%%|*}" out="${result#*|}"
    if [[ "$code" == "0" && -z "$out" ]]; then
        pass "$desc"
    else
        fail "$desc (expected exit 0 + empty output/ALLOW, got exit=$code output=$out)"
    fi
}

assert_deny() {
    local desc="$1" result="$2" reason_substr="${3:-}"
    local code="${result%%|*}" out="${result#*|}"
    if [[ "$code" != "0" ]]; then
        fail "$desc (expected exit 0 with deny JSON, got NONZERO exit=$code)"
        return
    fi
    local decision reason
    decision=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)
    reason=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason // empty' 2>/dev/null || true)
    if [[ "$decision" != "deny" ]]; then
        fail "$desc (expected permissionDecision=deny, got: $out)"
        return
    fi
    if [[ -n "$reason_substr" && "$reason" != *"$reason_substr"* ]]; then
        fail "$desc (deny reason missing expected substring '$reason_substr': $reason)"
        return
    fi
    pass "$desc"
}

echo "=== guard-destructive-generic.sh sql-ddl / --jq end-to-end ALLOW/DENY tests (#170) ==="

# --- (a) the issue's exact repro shape: a read-only gh api call whose --jq
# filter merely TESTS a title string for the DDL phrase -- no SQL, no
# execution.
result=$(run_hook "gh api repos/2AMLogic/gf180-gate-driver/issues --jq 'select(.title | test(\"(?i)sql-ddl|${DROPTBL}\"))'")
assert_allow "(a) gh api --jq filter merely testing for the DDL phrase in a title -> allow" "$result"

# --- (b) gh issue list --jq variant, confirming the fix isn't
# `gh api`-subcommand-specific.
result=$(run_hook "gh issue list --json title --jq '.[] | select(.title | contains(\"${DROPTBL}\"))'")
assert_allow "(b) gh issue list --jq filter mentioning the DDL phrase -> allow" "$result"

# --- (c) safety floor: a REAL, live, unquoted SQL DDL invocation (no --jq
# flag involved at all) must still resolve DENY, so (a)-(b) can't be
# satisfied by an over-broad mask.
result=$(run_hook "psql -c \"${DROPTBL} users\"")
assert_deny "(c) safety floor: real live psql DDL invocation, no --jq -> still deny" "$result" \
    "dangerous pattern"

# --- (d) safety floor: the dangerous phrase smuggled via a LIVE $(...)
# command substitution nested inside a DIFFERENT flag's (--body) quoted
# value, with an unrelated --jq flag present elsewhere in the same command
# (exercises the substring pre-check gates picking up "--jq" and routing
# into strip_literal_text(), which must still leave a live $(...) span
# un-redacted).
result=$(run_hook "gh issue comment 1 --body \"\$(psql -c '${DROPTBL} users')\" --jq '.'")
assert_deny "(d) safety floor: DDL smuggled via \$(...) inside --body, --jq present elsewhere -> still deny" "$result" \
    "dangerous pattern"

# --- (e) safety floor: the dangerous phrase smuggled via a LIVE $(...)
# command substitution nested DIRECTLY inside the --jq value itself -- the
# $(-floor must apply to --jq's own quoted span, not just other flags'.
result=$(run_hook "gh api foo --jq \"\$(psql -c '${DROPTBL} users')\"")
assert_deny "(e) safety floor: DDL smuggled via \$(...) directly inside --jq's own value -> still deny" "$result" \
    "dangerous pattern"

# --- defaults/ vs .loom/ sync: this repo ships no defaults/ tree (installed
# consumer repo, not the Loom source repo), so there is nothing to diff
# against -- confirm that expectation instead of silently skipping it.
if [[ ! -d "$REPO_ROOT/defaults" ]]; then
    pass "no defaults/ tree in this repo -- .loom/hooks/ vendored copy is the sole guard (as expected)"
else
    fail "unexpected defaults/ tree found -- re-check whether this suite should diff against it"
fi

echo "=== $PASS/$TOTAL passed ==="
[[ "$FAIL" -eq 0 ]]
