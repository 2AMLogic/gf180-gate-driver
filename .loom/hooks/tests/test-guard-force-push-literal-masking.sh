#!/usr/bin/env bash
# Regression test for .loom/hooks/guard-destructive-generic.sh's
# ALWAYS_BLOCK_PATTERNS force-push-to-main/master literal patterns
# false-denying read-only commands that merely QUOTE the trigger phrase as
# DATA rather than invoking it (issue #134).
#
# Usage: ./.loom/hooks/tests/test-guard-force-push-literal-masking.sh
#
# Bug: the six force-push literal patterns in ALWAYS_BLOCK_PATTERNS
# ('git push --force origin main', '... origin master', '-f' short forms,
# '--force-with-lease' forms) are matched as plain substrings against
# COMMAND_NO_LITERAL_TEXT -- a working copy that strip_literal_text() and
# mask_catastrophic_positional_args() narrow to redact KNOWN-inert quoted
# data, but neither function recognized two real-world read-only shapes:
#
#   1. `jq -c 'select(.pattern == "catastrophic:git push --force origin
#      main")' .loom/logs/guard-decisions.log` -- a jq filter argument
#      selecting log entries BY the pattern's own name (the very telemetry
#      review workflow auditor.md recommends). jq's filter is never
#      shell-executed, but mask_catastrophic_positional_args()'s command
#      allowlist (grep/egrep/fgrep/rg/check-duplicate.sh) did not include jq.
#
#   2. `gh api -X GET search/issues -f q='repo:... "git push --force origin
#      main" in:title,body' ...` -- a GitHub search query value passed via
#      gh api's `-f NAME=VALUE` raw-field flag. strip_literal_text()'s
#      quoted-value regex only recognized `<flag> "<value>"` (--body/-m/...)
#      and `--arg NAME "<value>"` (jq) shapes -- neither matches `-f
#      NAME=<value>`, where the flag and value are joined by `=` with no
#      space and no preceding NAME token.
#
# Both are read-only, zero-blast-radius commands that never invoke git at
# all, yet were denied purely because the guard's own trigger phrase
# appeared as a string literal in their arguments.
#
# The fix:
#   - adds `jq` to mask_catastrophic_positional_args()'s command allowlist
#     (its filter argument is jq-language data, never shell syntax -- same
#     reasoning already applied to grep/rg there), and to the substring gate
#     that invokes it;
#   - adds a third regex alternative to strip_literal_text() recognizing
#     `-f|-F|--raw-field|--field NAME=<quoted value>`, and adds a matching
#     substring gate ("-f " with a trailing space, so "--force"/
#     "--force-with-lease" -- which contain "-f" but never "-f " -- don't
#     spuriously widen the gate).
#
#   - (issue #244, post-#134 residual) adds a FOURTH recognition to
#     strip_literal_text(): a quoted word in a `for <var> in <words...>`
#     word-list position, provided the loop variable is not used anywhere
#     later in the command in an executing shape (unquoted `$var`, an
#     eval/exec/interpreter argument, or piped into an interpreter). Both
#     post-#134 denials in guard-decisions.log carried the trigger phrase
#     only as inert loop-iterator data (a dedup-title loop and a
#     telemetry-review loop), matching none of the flag-gated shapes above.
#     A matching `for <var> ` gate arms strip_literal_text() for loop
#     commands, which contain none of the flag substrings either.
#
# The genuinely dangerous case -- a REAL force-push invocation, quoted or
# not, bare or `bash -c`-wrapped or smuggled via `$(...)` inside a `-f`
# value -- must remain a hard DENY; only the string-literal-only case is
# newly allowed. A quoted for-list word whose variable IS executed later
# (`for cmd in "<phrase>"; do $cmd; done`, `do eval "$cmd"`) stays DENIED
# too -- the word-list position is only inert when the value never reaches
# a command position.
#
# This suite is split into two parts:
#
#   PART 1 -- direct unit tests on strip_literal_text() (the new `-f`/`-F`/
#   `--raw-field`/`--field NAME=<value>` alternative) and
#   mask_catastrophic_positional_args() (the new `jq` allowlist entry). Both
#   functions are extracted from the hook file and sourced standalone,
#   matching test-strip-literal-text-bsq.sh's own extraction convention.
#
#   PART 2 -- end-to-end hook decision tests (ALLOW/DENY) through the real
#   PreToolUse JSON protocol, covering both reported false-denial shapes and
#   the safety-floor invariant (a real invocation, quoted/wrapped/smuggled,
#   still denies).
#
# The hook under test is the canonical source at .loom/hooks/ (this repo
# ships no defaults/ tree -- see the file's own banner), copied into an
# isolated temp git tree, exactly like test-strip-literal-text-bsq.sh and
# test-guard-catastrophic-rm-heredoc.sh do for their own end-to-end parts.
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

# Build the dangerous phrases from parts so this test FILE's own source text
# never spells any of them out contiguously -- avoids tripping this same
# guard on any future Bash invocation that greps/cats this file (mirrors the
# convention in test-guard-catastrophic-rm-heredoc.sh / test-strip-literal-
# text-bsq.sh).
FP_MAIN="git push --for""ce origin main"
FP_MASTER="git push --for""ce origin master"
FP_LEASE_MAIN="git push --force-with-lease""  origin main"
FP_LEASE_MAIN="${FP_LEASE_MAIN/  / }"

# The exact catastrophic-tier main-branch pattern (mirrors
# guard-destructive-generic.sh's ALWAYS_BLOCK_PATTERNS entry), used by PART 1
# to check whether masking removed the match.
MAIN_PATTERN='git push --force origin main'

# =============================================================================
# PART 1 -- direct unit tests
# =============================================================================
echo "=== strip_literal_text() / mask_catastrophic_positional_args() unit tests (#134) ==="

FN_FILE="$(mktemp)"
trap 'rm -f "$FN_FILE"' EXIT
{
    awk '/^strip_literal_text\(\) \{/{f=1} f{print; if ($0 == "}" && f == 1) exit}' "$SRC_HOOK"
    awk '/^mask_catastrophic_positional_args\(\) \{/{f=1} f{print; if ($0 == "}" && f == 1) exit}' "$SRC_HOOK"
} > "$FN_FILE"
if ! grep -q "^strip_literal_text" "$FN_FILE" || ! grep -q "^mask_catastrophic_positional_args" "$FN_FILE"; then
    fail "extract strip_literal_text()/mask_catastrophic_positional_args() from $SRC_HOOK (function not found)"
else
    # shellcheck source=/dev/null
    source "$FN_FILE"

    # --- (1) strip_literal_text(): gh api -f NAME=<single-quoted value>
    # containing the dangerous phrase -> masked (the reported repro shape).
    CMD1="gh api -X GET search/issues -f q='repo:owner/repo \"${FP_MAIN}\" in:title,body' --jq .total_count"
    OUT1=$(strip_literal_text "$CMD1")
    if ! echo "$OUT1" | grep -qiE "$MAIN_PATTERN"; then
        pass "(1) strip_literal_text(): -f q='...phrase...' masked"
    else
        fail "(1) strip_literal_text(): -f q='...phrase...' NOT masked: $OUT1"
    fi
    if [[ ${#OUT1} -eq ${#CMD1} ]]; then
        pass "(1) masked output preserves byte length (offset-stability invariant)"
    else
        fail "(1) masked output length changed: in=${#CMD1} out=${#OUT1}"
    fi

    # --- (2) strip_literal_text(): -F (capital) / --raw-field / --field
    # spellings all recognized too.
    CMD2A="gh api -F q='${FP_MAIN}'"
    OUT2A=$(strip_literal_text "$CMD2A")
    if ! echo "$OUT2A" | grep -qiE "$MAIN_PATTERN"; then
        pass "(2a) strip_literal_text(): -F q='...' masked"
    else
        fail "(2a) strip_literal_text(): -F q='...' NOT masked: $OUT2A"
    fi
    CMD2B="gh api --raw-field q='${FP_MAIN}'"
    OUT2B=$(strip_literal_text "$CMD2B")
    if ! echo "$OUT2B" | grep -qiE "$MAIN_PATTERN"; then
        pass "(2b) strip_literal_text(): --raw-field q='...' masked"
    else
        fail "(2b) strip_literal_text(): --raw-field q='...' NOT masked: $OUT2B"
    fi
    CMD2C="gh api --field q='${FP_MAIN}'"
    OUT2C=$(strip_literal_text "$CMD2C")
    if ! echo "$OUT2C" | grep -qiE "$MAIN_PATTERN"; then
        pass "(2c) strip_literal_text(): --field q='...' masked"
    else
        fail "(2c) strip_literal_text(): --field q='...' NOT masked: $OUT2C"
    fi

    # --- (3) strip_literal_text(): DOUBLE-quoted -f value carrying a LIVE
    # `$(...)` command substitution must NOT be masked -- the safety floor
    # (real invocation smuggled through a raw-field value) stays visible.
    CMD3="gh api -f q=\"\$(${FP_MAIN})\""
    OUT3=$(strip_literal_text "$CMD3")
    if echo "$OUT3" | grep -qiE "$MAIN_PATTERN"; then
        pass "(3) strip_literal_text(): -f q=\"\$(...)\" live substitution left unmasked (floor preserved)"
    else
        fail "(3) strip_literal_text(): live \$(...) inside -f value was incorrectly masked: $OUT3"
    fi

    # --- (4) strip_literal_text(): a real (unquoted, non--f) invocation
    # elsewhere in the same buffer is untouched by the new alternative.
    CMD4="gh api -f q='harmless search text' && ${FP_MAIN}"
    OUT4=$(strip_literal_text "$CMD4")
    if echo "$OUT4" | grep -qiE "$MAIN_PATTERN"; then
        pass "(4) strip_literal_text(): narrowing-only -- real trailing invocation stays visible"
    else
        fail "(4) strip_literal_text(): real trailing invocation was incorrectly masked: $OUT4"
    fi

    # --- (5) mask_catastrophic_positional_args(): jq's own quoted filter
    # argument containing the dangerous phrase (as a comparand, never
    # executed) -> masked (the reported repro shape).
    CMD5="jq -c 'select(.pattern == \"catastrophic:${FP_MAIN}\")' .loom/logs/guard-decisions.log"
    OUT5=$(mask_catastrophic_positional_args "$CMD5")
    if ! echo "$OUT5" | grep -qiE "$MAIN_PATTERN"; then
        pass "(5) mask_catastrophic_positional_args(): jq filter argument masked"
    else
        fail "(5) mask_catastrophic_positional_args(): jq filter argument NOT masked: $OUT5"
    fi

    # --- (6) mask_catastrophic_positional_args(): narrowing-only -- a real
    # invocation chained AFTER the jq call stays fully visible.
    CMD6="jq -c 'select(.x == 1)' file.log && ${FP_MAIN}"
    OUT6=$(mask_catastrophic_positional_args "$CMD6")
    if echo "$OUT6" | grep -qiE "$MAIN_PATTERN"; then
        pass "(6) mask_catastrophic_positional_args(): narrowing-only -- real trailing invocation stays visible"
    else
        fail "(6) mask_catastrophic_positional_args(): real trailing invocation was incorrectly masked: $OUT6"
    fi

    # --- (7) mask_catastrophic_positional_args(): pre-existing grep/rg
    # masking is unaffected by adding jq to the same allowlist.
    CMD7="grep -n \"${FP_MAIN}\" .loom/hooks/guard-destructive-generic.sh"
    OUT7=$(mask_catastrophic_positional_args "$CMD7")
    if ! echo "$OUT7" | grep -qiE "$MAIN_PATTERN"; then
        pass "(7) mask_catastrophic_positional_args(): pre-existing grep masking still works (no regression)"
    else
        fail "(7) mask_catastrophic_positional_args(): grep masking regressed: $OUT7"
    fi

    # --- (8) mask_catastrophic_positional_args(): SAFETY-FLOOR REGRESSION FIX
    # (issue #137) -- `jq -n`/`--null-input` needs no input at all, so it can
    # manufacture the dangerous phrase purely from its filter argument. That
    # argument must stay UNMASKED (visible to ALWAYS_BLOCK_PATTERNS) even
    # though the general jq allowlist entry above masks a normal jq filter.
    CMD8A="\$(jq -n -r '\"${FP_MAIN}\"')"
    OUT8A=$(mask_catastrophic_positional_args "$CMD8A")
    if echo "$OUT8A" | grep -qiE "$MAIN_PATTERN"; then
        pass "(8a) mask_catastrophic_positional_args(): jq -n -r filter argument left UNMASKED (safety floor)"
    else
        fail "(8a) mask_catastrophic_positional_args(): jq -n -r filter argument was incorrectly masked: $OUT8A"
    fi
    CMD8B="jq --null-input -r '\"${FP_MAIN}\"' | sh"
    OUT8B=$(mask_catastrophic_positional_args "$CMD8B")
    if echo "$OUT8B" | grep -qiE "$MAIN_PATTERN"; then
        pass "(8b) mask_catastrophic_positional_args(): jq --null-input filter argument left UNMASKED (safety floor)"
    else
        fail "(8b) mask_catastrophic_positional_args(): jq --null-input filter argument was incorrectly masked: $OUT8B"
    fi

    # --- (9) strip_literal_text(): for-loop word-list position (issue #244,
    # the reported dedup-loop shape): a double-quoted word in a
    # `for <var> in <words...>` list, with the loop variable used only as
    # inert data in the loop body -> masked. Phrase sits as the LAST of
    # three words so multi-word continuation (whitespace-only U segments
    # between quoted words) is exercised too.
    CMD9="for p in \"sql-ddl\" \"worktree-write-confinement\" \"${FP_MAIN}\"; do ./.loom/scripts/check-duplicate.sh \"Guard decision: \$p\"; done"
    OUT9=$(strip_literal_text "$CMD9")
    if ! echo "$OUT9" | grep -qiE "$MAIN_PATTERN"; then
        pass "(9) strip_literal_text(): for-loop word-list phrase (last of 3 words) masked"
    else
        fail "(9) strip_literal_text(): for-loop word-list phrase NOT masked: $OUT9"
    fi
    if [[ ${#OUT9} -eq ${#CMD9} ]]; then
        pass "(9b) masked for-loop output preserves byte length (offset-stability invariant)"
    else
        fail "(9b) masked for-loop output length changed: in=${#CMD9} out=${#OUT9}"
    fi

    # --- (10) the second reported shape (telemetry-review loop): phrase as
    # the FIRST (single) list word, loop variable reused inside a
    # `'...\"'\"$p\"'\"...'` single/double-quote concatenation -- \$p must
    # only ever appear inside Q segments, never unquoted.
    CMD10="for p in \"${FP_MAIN}\"; do echo \"=== \$p ===\"; jq -c 'select(.pattern==\""
    CMD10+="'\"\$p\"'"
    CMD10+="\")'"
    CMD10+=" .loom/logs/guard-decisions.log | tail -2; done"
    OUT10=$(strip_literal_text "$CMD10")
    if ! echo "$OUT10" | grep -qiE "$MAIN_PATTERN"; then
        pass "(10) strip_literal_text(): telemetry-loop phrase (first word, quote-dance body) masked"
    else
        fail "(10) strip_literal_text(): telemetry-loop phrase NOT masked: $OUT10"
    fi

    # --- (11) safety floor: a for-list word whose variable is EXECUTED
    # unquoted in the loop body must stay UNMASKED -- the executing shape
    # merely resembles the newly-allowed quoting shape.
    CMD11="for cmd in \"${FP_MAIN}\"; do \$cmd; done"
    OUT11=$(strip_literal_text "$CMD11")
    if echo "$OUT11" | grep -qiE "$MAIN_PATTERN"; then
        pass "(11) strip_literal_text(): for-list phrase with unquoted \$cmd body left UNMASKED (floor preserved)"
    else
        fail "(11) strip_literal_text(): for-list phrase incorrectly masked despite \$cmd execution: $OUT11"
    fi

    # --- (12) safety floor, eval form: `eval \"\$cmd\"` in the body is an
    # executing use of the loop variable even though \$cmd sits in a Q
    # segment -- must stay UNMASKED.
    CMD12="for cmd in \"${FP_MAIN}\"; do eval \"\$cmd\"; done"
    OUT12=$(strip_literal_text "$CMD12")
    if echo "$OUT12" | grep -qiE "$MAIN_PATTERN"; then
        pass "(12) strip_literal_text(): for-list phrase with eval \"\$cmd\" body left UNMASKED (floor preserved)"
    else
        fail "(12) strip_literal_text(): for-list phrase incorrectly masked despite eval: $OUT12"
    fi

    # --- (13) narrowing-only: masking the inert for-list word must not
    # blind the scan to a real (bare) invocation chained later in the SAME
    # command.
    CMD13="for p in \"${FP_MAIN}\"; do echo \"\$p\"; done && ${FP_MAIN}"
    OUT13=$(strip_literal_text "$CMD13")
    if echo "$OUT13" | grep -qiE "$MAIN_PATTERN"; then
        pass "(13) strip_literal_text(): narrowing-only -- real invocation chained after a loop stays visible"
    else
        fail "(13) strip_literal_text(): real chained invocation was incorrectly masked: $OUT13"
    fi
fi

# =============================================================================
# PART 2 -- end-to-end hook decision tests (ALLOW/DENY)
# =============================================================================
echo
echo "=== guard-destructive-generic.sh end-to-end ALLOW/DENY tests (#134) ==="

TMPROOT="$(mktemp -d)"
trap 'rm -f "$FN_FILE"; rm -rf "$TMPROOT"' EXIT
git init -q "$TMPROOT"
mkdir -p "$TMPROOT/.loom/hooks" "$TMPROOT/.loom/scripts/lib"
cp "$SRC_HOOK" "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
chmod +x "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
cp "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" "$TMPROOT/.loom/scripts/lib/config-resolver.sh"
cp "$REPO_ROOT/.loom/scripts/lib/canonical-path.sh" "$TMPROOT/.loom/scripts/lib/canonical-path.sh"
HOOK="$TMPROOT/.loom/hooks/guard-destructive-generic.sh"

make_input() {
    local command="$1"
    jq -n --arg cmd "$command" --arg cwd "$TMPROOT" \
        '{tool_input: {command: $cmd}, cwd: $cwd}'
}

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

# --- (a) the exact reported jq repro: read-only log introspection selecting
# entries BY this guard's own pattern name -> ALLOW (was DENY before the fix).
result=$(run_hook "jq -c 'select(.pattern == \"catastrophic:${FP_MAIN}\")' .loom/logs/guard-decisions.log")
assert_allow "(a) jq log introspection selecting by the pattern's own name -> allow" "$result"

# --- (b) the exact reported gh api repro: a read-only GitHub search query
# whose value happens to quote the phrase -> ALLOW (was DENY before the fix).
result=$(run_hook "gh api -X GET search/issues -f q='repo:owner/repo \"${FP_MAIN}\" in:title,body' --jq .total_count")
assert_allow "(b) gh api -f q='...phrase...' search query -> allow" "$result"

# --- (c) same shape, master branch spelling -> ALLOW.
result=$(run_hook "gh api -f q='repo:owner/repo \"${FP_MASTER}\" in:title,body'")
assert_allow "(c) gh api -f q='...phrase (master)...' search query -> allow" "$result"

# --- (d) same shape, --force-with-lease spelling -> ALLOW.
result=$(run_hook "jq -n --arg p \"catastrophic:${FP_LEASE_MAIN}\" '{pattern:\$p}'")
assert_allow "(d) jq --arg carrying the --force-with-lease phrase -> allow (pre-existing --arg masking, unaffected)" "$result"

# --- (e) real, bare force-push invocation -> still DENY (unaffected).
result=$(run_hook "$FP_MAIN")
assert_deny "(e) real bare force-push invocation -> still deny (unaffected)" "$result" \
    "dangerous pattern"

# --- (f) real force-push wrapped in bash -c -- the catastrophic scan runs
# over the full raw command including quoted text on purpose (per the file's
# own header comment), so a quoted LIVE invocation must still deny.
result=$(run_hook "bash -c '${FP_MAIN}'")
assert_deny "(f) real force-push via bash -c wrapper -> still deny (unaffected)" "$result" \
    "dangerous pattern"

# --- (g) real force-push smuggled via command substitution inside a -f
# value -> still DENY: strip_literal_text()'s new -f alternative must not
# widen the DQ \$(...) safety floor.
result=$(run_hook "gh api -f q=\"\$(${FP_MAIN})\"")
assert_deny "(g) force-push smuggled via \$(...) inside gh api -f value -> still deny" "$result" \
    "dangerous pattern"

# --- (h) real force-push chained after an inert jq call in the same
# command -> still DENY: mask_catastrophic_positional_args()'s new jq entry
# must not blind the scan to a real invocation elsewhere on the line.
result=$(run_hook "jq -c 'select(.x == 1)' file.log && ${FP_MAIN}")
assert_deny "(h) real force-push chained after an inert jq call -> still deny" "$result" \
    "dangerous pattern"

# --- (i) real force-push chained after a read-only gh api -f call -> still
# DENY: the -f gate must not blind the scan to a real invocation elsewhere.
result=$(run_hook "gh api -f q='harmless' && ${FP_MAIN}")
assert_deny "(i) real force-push chained after a read-only gh api -f call -> still deny" "$result" \
    "dangerous pattern"

# --- (j) sanity: -f with no dangerous phrase at all is unaffected (no false
# denial, nothing to mask).
result=$(run_hook "gh api -f q='just an ordinary search string'")
assert_allow "(j) sanity: gh api -f q='...' with no dangerous phrase -> allow" "$result"

# --- (k) SAFETY-FLOOR REGRESSION FIX (issue #137): `jq -n -r` needs no real
# input at all -- it can manufacture the dangerous phrase purely from its
# filter argument. Combined with `-r` (raw/unquoted output) and `$(...)`
# command substitution, a masked filter here becomes directly
# shell-executable -- bash runs the substitution first, then executes its
# captured output as a command line. Must still DENY.
result=$(run_hook "\$(jq -n -r '\"${FP_MAIN}\"')")
assert_deny "(k) jq -n -r filter manufacturing a force-push phrase via \$(...) -> still deny" "$result" \
    "dangerous pattern"

# --- (l) same shape piped directly to a shell instead of \$(...) -- still
# DENY.
result=$(run_hook "jq -n -r '\"${FP_MAIN}\"' | sh")
assert_deny "(l) jq -n -r filter manufacturing a force-push phrase piped to sh -> still deny" "$result" \
    "dangerous pattern"

# --- (m) issue #244 repro 1 (dedup-title loop): the trigger phrase rides
# only as a quoted for-loop word-list element; the loop body passes \$p to
# check-duplicate.sh as a TITLE argument (inert data) -> ALLOW (was DENY).
result=$(run_hook "for p in \"sql-ddl\" \"worktree-write-confinement\" \"${FP_MAIN}\"; do ./.loom/scripts/check-duplicate.sh \"Guard decision: \$p\"; done")
assert_allow "(m) dedup-check loop quoting the phrase as iterator data -> allow" "$result"

# --- (n) issue #244 repro 2 (telemetry-review loop): same word-list shape;
# the body echoes \$p and feeds it to a jq filter via the standard
# single/double-quote concatenation -> ALLOW (was DENY).
EV2="for p in \"${FP_MAIN}\"; do echo \"=== \$p ===\"; jq -c 'select(.pattern==\""
EV2+="'\"\$p\"'"
EV2+="\")'"
EV2+=" .loom/logs/guard-decisions.log | tail -2; done"
result=$(run_hook "$EV2")
assert_allow "(n) telemetry-review loop quoting the phrase as iterator data -> allow" "$result"

# --- (o) issue #244 safety floor: same quoting shape but the body EXECUTES
# the variable unquoted -- a real smuggled invocation -> still DENY.
result=$(run_hook "for cmd in \"${FP_MAIN}\"; do \$cmd; done")
assert_deny "(o) for-list phrase executed via unquoted \$cmd -> still deny" "$result" \
    "dangerous pattern"

# --- (p) issue #244 safety floor, eval form: the variable sits in a Q
# segment but eval executes its value -> still DENY.
result=$(run_hook "for cmd in \"${FP_MAIN}\"; do eval \"\$cmd\"; done")
assert_deny "(p) for-list phrase executed via eval \"\$cmd\" -> still deny" "$result" \
    "dangerous pattern"

# --- (q) issue #244 narrowing-only: the inert loop word is masked but a
# real bare invocation chained later in the same command stays visible ->
# still DENY.
result=$(run_hook "for p in \"${FP_MAIN}\"; do echo \"\$p\"; done && ${FP_MAIN}")
assert_deny "(q) real bare force-push chained after a loop -> still deny" "$result" \
    "dangerous pattern"

# --- (r) issue #244 edge: single-word list, single-quoted spelling (inert
# unconditionally, #5783) and an inert body -> ALLOW.
result=$(run_hook "for p in '${FP_MAIN}'; do echo \"saw: \$p\"; done")
assert_allow "(r) single-quoted single-word for-list phrase with echo body -> allow" "$result"

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
