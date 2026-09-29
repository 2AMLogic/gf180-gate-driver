#!/usr/bin/env bash
# Regression test for the decision-log test/repro suppression toggle
# LOOM_GUARD_LOG_SUPPRESS (issue #279).
#
# Usage: ./.loom/hooks/tests/test-guard-decision-log-suppress.sh
#
# Provenance: an Auditor review of `.loom/logs/guard-decisions.log` found that
# the two largest `pattern` counts in the live log were not real
# autonomous-work friction but FIXTURES — ad hoc guard-debug repro sessions run
# as real top-level Bash tool calls in the main checkout, whose command string
# happened to contain dangerous-looking fixture text (a `for p in "catastrophic
# rm -rf pattern" ...` enumeration loop, a `jq -n --arg cmd ...` harness, SQL
# DDL probes). The OUTER, live PreToolUse hook fires on that whole string and
# records it, so each telemetry review re-trips on the session that was
# investigating the guard.
#
# Note on what was NOT the source: the formal suites in this directory copy the
# hook into a fresh $TMPROOT, so their DECISION_LOG (derived from SCRIPT_DIR at
# runtime) already resolves inside that throwaway tree and never touches the
# repo's real log. The fix therefore targets the interactive/live surface, via
# an explicit opt-in env flag a repro session sets around itself.
#
# The contract under test, and the reason this file exists: suppression is
# TELEMETRY-ONLY. It must never become a way to quiet an enforcement decision.
# log_guard_decision() is called as the FIRST statement of deny()/ask(), always
# as `|| true`, and always AFTER the verdict is already fixed — so a suppressed
# run must produce a byte-for-byte identical permissionDecision JSON and exit
# code, differing only in that no line is appended to DECISION_LOG.
#
# Covers, end-to-end through the real PreToolUse JSON protocol:
#   (a) suppress SET + a would-deny command  -> still DENY, DECISION_LOG never
#       created
#   (b) suppress UNSET + the same command    -> still DENY, DECISION_LOG gains
#       exactly ONE line, with the documented 5-field schema intact (no new
#       `source`/provenance key leaked into the #3772 reader contract)
#   (c) the deny JSON is BYTE-IDENTICAL between the suppressed and unsuppressed
#       runs — the assertion that would fail if a future edit ever coupled
#       telemetry suppression to enforcement
#   (d) DANGEROUS-SET FLOOR: the whole catastrophic/ask set named in the issue's
#       "What does NOT change" section (force-push to main, `rm -rf /`, `git
#       clean -fd`, `git checkout .`) still resolves the SAME decision
#       (deny/ask) WITH the suppress var set as without it
#   (e) suppress is ORTHOGONAL to the existing on/off toggle: with
#       LOOM_GUARD_DECISION_LOG=0 (log off) and suppress unset, still no write —
#       suppression did not accidentally become an enabler
#   (f) only the documented truthy values suppress; a bogus/`0`/empty value
#       fails SAFE toward logging, not toward silence
#   (g) both writers agree: guard-loom-workflow.sh appends to the SAME log file
#       and must honour the SAME env var, else fixture rows still leak in
#
# The hooks under test are the canonical sources at .loom/hooks/ (this repo
# ships no defaults/ tree), copied into an isolated temp git tree alongside
# their config-resolver.sh/canonical-path.sh lib dependencies, exactly like
# test-guard-sql-ddl-jq-prose.sh does.
# Exit 0 = all pass, 1 = fail.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SRC_HOOK="$REPO_ROOT/.loom/hooks/guard-destructive-generic.sh"
SRC_WORKFLOW_HOOK="$REPO_ROOT/.loom/hooks/guard-loom-workflow.sh"

PASS=0
FAIL=0
TOTAL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); printf "${GREEN}PASS${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "${RED}FAIL${NC} %s\n" "$1"; }

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT
git init -q "$TMPROOT"
mkdir -p "$TMPROOT/.loom/hooks" "$TMPROOT/.loom/scripts/lib"
cp "$SRC_HOOK" "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
cp "$SRC_WORKFLOW_HOOK" "$TMPROOT/.loom/hooks/guard-loom-workflow.sh"
chmod +x "$TMPROOT/.loom/hooks/guard-destructive-generic.sh" \
         "$TMPROOT/.loom/hooks/guard-loom-workflow.sh"
cp "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" "$TMPROOT/.loom/scripts/lib/config-resolver.sh"
cp "$REPO_ROOT/.loom/scripts/lib/canonical-path.sh" "$TMPROOT/.loom/scripts/lib/canonical-path.sh"
HOOK="$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
WORKFLOW_HOOK="$TMPROOT/.loom/hooks/guard-loom-workflow.sh"

# The log path every case asserts against. Pinned explicitly via the
# LOOM_GUARD_DECISION_LOG_FILE test seam rather than relying on the
# SCRIPT_DIR-relative default, so a failure here is unambiguously "the hook did
# (not) write" and never "the hook wrote somewhere else".
DECISION_LOG="$TMPROOT/decisions.jsonl"

# Build stdin JSON for a Bash tool_input, with cwd fixed at TMPROOT (the
# synthetic main checkout).
make_input() {
    local command="$1"
    jq -n --arg cmd "$command" --arg cwd "$TMPROOT" \
        '{tool_input: {command: $cmd}, cwd: $cwd}'
}

# Run a hook from inside the temp tree so git-common-dir resolves to it.
#
# Every ambient LOOM_* override this host may already export is stripped with
# `env -u` and then set explicitly per-case, so the result never depends on the
# dispatching daemon's environment (#5388: a dispatched agent inherits
# LOOM_GUARD_DECISION_LOG=1 and LOOM_FORCE_SCOPE=protected, which silently
# changes exactly the behaviours this file asserts).
#
# Args: <hook-path> <suppress-value|-> <decision-log-value> <command>
# Prints "<exit_code>|<stdout>".
run_hook_env() {
    local hook="$1" suppress="$2" declog="$3" command="$4"
    local exit_code=0 output
    local -a env_args=(env -u LOOM_GUARD_LOG_SUPPRESS -u LOOM_GUARD_DECISION_LOG -u LOOM_FORCE_SCOPE)
    [[ "$suppress" != "-" ]] && env_args+=("LOOM_GUARD_LOG_SUPPRESS=$suppress")
    env_args+=("LOOM_GUARD_DECISION_LOG=$declog")
    env_args+=("LOOM_GUARD_DECISION_LOG_FILE=$DECISION_LOG")
    output=$(cd "$TMPROOT" && "${env_args[@]}" bash "$hook" < <(make_input "$command") 2>/dev/null) || exit_code=$?
    printf '%s|%s' "$exit_code" "$output"
}

# Convenience: the decision log is enabled (=1) for these, which is the only
# configuration in which suppression is observable at all.
run_suppressed()   { run_hook_env "$HOOK" "${2:-1}" 1 "$1"; }
run_unsuppressed() { run_hook_env "$HOOK" "-"       1 "$1"; }

reset_log() { rm -f "$DECISION_LOG"; }

log_lines() {
    [[ -f "$DECISION_LOG" ]] || { echo 0; return; }
    wc -l < "$DECISION_LOG" | tr -d ' '
}

decision_of() {
    local out="${1#*|}"
    echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // "allow"' 2>/dev/null || echo "?"
}

assert_decision() {
    local desc="$1" result="$2" want="$3"
    local code="${result%%|*}"
    local got
    got="$(decision_of "$result")"
    if [[ "$code" != "0" ]]; then
        fail "$desc (expected exit 0, got exit=$code)"
    elif [[ "$got" == "$want" ]]; then
        pass "$desc"
    else
        fail "$desc (expected permissionDecision=$want, got=$got)"
    fi
}

assert_log_lines() {
    local desc="$1" want="$2"
    local got
    got="$(log_lines)"
    if [[ "$got" == "$want" ]]; then
        pass "$desc"
    else
        fail "$desc (expected $want line(s) in DECISION_LOG, got $got)"
    fi
}

echo "=== guard decision-log LOOM_GUARD_LOG_SUPPRESS suppression tests (#279) ==="

# A command the catastrophic tier denies unconditionally. Assembled from parts
# so this test FILE's own text never contains the literal dangerous substring
# contiguously — the same convention every sibling suite in this directory uses
# to avoid tripping the guard on a future `cat`/`grep` of this file. (That this
# convention is necessary at all is precisely the friction #279 is about.)
FORCE_MAIN="git push --f""orce origin main"
RM_ROOT="rm -rf""  /"
GIT_CLEAN="git cl""ean -fd"
GIT_CHECKOUT_DOT="git chec""kout ."

# --- (a) suppress SET + would-deny command -> still DENY, nothing logged.
reset_log
result_suppressed=$(run_suppressed "$FORCE_MAIN")
assert_decision "(a) suppress=1: would-deny command still DENIES" "$result_suppressed" "deny"
assert_log_lines "(a) suppress=1: DECISION_LOG not created/appended" 0
if [[ -e "$DECISION_LOG" ]]; then
    fail "(a) suppress=1: DECISION_LOG file must not even be created"
else
    pass "(a) suppress=1: DECISION_LOG file not created at all"
fi

# --- (b) suppress UNSET + same command -> still DENY, exactly one line, and
# that line still carries the documented 5-field schema (no provenance key
# leaked into #3772's reader contract).
reset_log
result_plain=$(run_unsuppressed "$FORCE_MAIN")
assert_decision "(b) suppress unset: same command still DENIES" "$result_plain" "deny"
assert_log_lines "(b) suppress unset: DECISION_LOG gains exactly one line" 1

if [[ -f "$DECISION_LOG" ]]; then
    keys=$(jq -r 'keys_unsorted | join(",")' < "$DECISION_LOG" 2>/dev/null || echo "<unparseable>")
    if [[ "$keys" == "ts,decision,pattern,tier,command" ]]; then
        pass "(b) logged line keeps the documented 5-field STABLE SCHEMA ($keys)"
    else
        fail "(b) logged line schema drifted (expected ts,decision,pattern,tier,command; got $keys)"
    fi
else
    fail "(b) logged line keeps the documented 5-field STABLE SCHEMA (no log written)"
fi

# --- (c) the enforcement OUTPUT is byte-identical between the two runs. This
# is the assertion that fails if suppression is ever wired into the decision.
if [[ "$result_suppressed" == "$result_plain" ]]; then
    pass "(c) deny JSON + exit code byte-identical with and without suppression"
else
    fail "(c) suppression changed the enforcement output: suppressed=[$result_suppressed] plain=[$result_plain]"
fi

# --- (d) DANGEROUS-SET FLOOR. Everything the issue's "What does NOT change"
# section names must resolve the SAME decision under suppression as without it.
# Asserted as an equality between the two runs rather than against a hardcoded
# tier, so the case stays valid if a tier is legitimately retuned later — what
# it pins is that SUPPRESSION never moves it.
for dangerous in "$FORCE_MAIN" "$RM_ROOT" "$GIT_CLEAN" "$GIT_CHECKOUT_DOT"; do
    reset_log
    r_sup=$(run_suppressed "$dangerous")
    d_sup="$(decision_of "$r_sup")"
    reset_log
    r_plain=$(run_unsuppressed "$dangerous")
    d_plain="$(decision_of "$r_plain")"

    label="$(printf '%.40s' "$dangerous")"
    if [[ "$d_sup" != "deny" && "$d_sup" != "ask" ]]; then
        fail "(d) floor: '$label' must stay DENY or ASK, got '$d_sup' under suppression"
    elif [[ "$d_sup" == "$d_plain" ]]; then
        pass "(d) floor: '$label' -> $d_sup, identical with and without suppression"
    else
        fail "(d) floor: '$label' decision changed under suppression (suppressed=$d_sup plain=$d_plain)"
    fi
done

# --- (e) orthogonality: with the log toggle explicitly OFF and suppress unset,
# there is still no write. Suppression must not have become an enabler, and
# decision_log_enabled()'s own resolution must be untouched.
reset_log
result=$(run_hook_env "$HOOK" "-" 0 "$FORCE_MAIN")
assert_decision "(e) decisionLog=0, suppress unset: still DENIES" "$result" "deny"
assert_log_lines "(e) decisionLog=0, suppress unset: still no write (toggle untouched)" 0

# ...and suppress=1 on top of an already-off log is simply still off.
reset_log
result=$(run_hook_env "$HOOK" 1 0 "$FORCE_MAIN")
assert_decision "(e) decisionLog=0 + suppress=1: still DENIES" "$result" "deny"
assert_log_lines "(e) decisionLog=0 + suppress=1: still no write" 0

# --- (f) truthy-value parsing. The documented values suppress; everything else
# fails SAFE toward logging so a typo loses telemetry hygiene, never telemetry.
for truthy in 1 true yes on; do
    reset_log
    result=$(run_hook_env "$HOOK" "$truthy" 1 "$FORCE_MAIN")
    assert_decision "(f) suppress=$truthy: still DENIES" "$result" "deny"
    assert_log_lines "(f) suppress=$truthy suppresses the write" 0
done

for falsy in 0 false no off "" bogus; do
    reset_log
    result=$(run_hook_env "$HOOK" "$falsy" 1 "$FORCE_MAIN")
    assert_decision "(f) suppress='$falsy': still DENIES" "$result" "deny"
    assert_log_lines "(f) suppress='$falsy' does NOT suppress (fails safe toward logging)" 1
done

# --- (g) the sibling writer honours the same var. guard-loom-workflow.sh
# appends to the SAME guard-decisions.log, so a toggle respected by only one of
# the two writers would still let fixture rows into the file it is meant to keep
# clean. `gh pr merge` is that hook's canonical catastrophic redirect.
GH_PR_MERGE="gh pr me""rge 123 --squash"

reset_log
result=$(run_hook_env "$WORKFLOW_HOOK" "-" 1 "$GH_PR_MERGE")
assert_decision "(g) workflow guard, suppress unset: redirect still DENIES" "$result" "deny"
assert_log_lines "(g) workflow guard, suppress unset: logs exactly one line" 1

reset_log
result_wf_sup=$(run_hook_env "$WORKFLOW_HOOK" 1 1 "$GH_PR_MERGE")
assert_decision "(g) workflow guard, suppress=1: redirect still DENIES" "$result_wf_sup" "deny"
assert_log_lines "(g) workflow guard, suppress=1: write suppressed too" 0

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
