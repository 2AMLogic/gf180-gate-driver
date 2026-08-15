#!/usr/bin/env bash
# Regression test for .loom/hooks/guard-destructive-generic.sh's
# strip_literal_text() single-quoted-span masking (issue #56).
#
# Usage: ./.loom/hooks/tests/test-strip-literal-text-bsq.sh
#
# Bug: strip_literal_text()'s single-quoted-span regex was
# `SQ "[^" SQ "]*" SQ` -- open quote, a run of non-quote bytes, close quote --
# which ends the masked span at the FIRST raw single-quote byte it meets. A
# `--body`/-m/--title/--notes/--comment VALUE built with bash's standard
# apostrophe-escaping idiom (close-quote, backslash, quote, reopen-quote --
# the bytes a real shell parses as "insert one literal apostrophe and keep
# concatenating onto the same word") puts a raw quote byte partway through
# the otherwise-single logical value at every embedded apostrophe. The old
# regex treated that byte as a real close-quote, truncating the masked span
# there -- so everything after the FIRST embedded apostrophe (an ordinary
# English possessive/contraction: "it's", "#50's", "Champion's", ...) stayed
# fully unmasked and visible to the ASK_PATTERNS / stash-scope:*
# COMMAND_ASK_SCAN checks, and to the catastrophic-tier
# COMMAND_NO_LITERAL_TEXT scan.
#
# Observed live in .loom/logs/guard-decisions.log: a `gh issue comment`
# posting Champion's prose verdict on issue #50 tripped a false
# `stash-scope:main-checkout` ASK because its --body value (after "...#50's
# own verdict is...") quoted, as documentation, "raw `git stash`/`git stash
# pop`" -- never invoking either. That stalls headless/autonomous dispatch,
# since nothing answers an ASK in that mode.
#
# The fix makes the single-quoted branch of strip_literal_text()'s span
# regex aware of the escape idiom: a `'\''`-shaped byte sequence now
# continues the same logical masked span instead of ending it.
#
# This suite is split into two parts:
#
#   PART 1 -- direct strip_literal_text() unit tests. The function is
#   extracted from the hook file (via awk, isolating just the function body)
#   and sourced standalone, exactly as issue #56's own reproduction did.
#   This deliberately bypasses the rest of the hook pipeline -- in
#   particular COMMAND_NO_COMMENT's separate, NOT-quote-aware `#`-comment
#   stripper (`sed -E 's/(^|[[:space:]])#.*$//'`, out of scope for this
#   issue) -- so these cases isolate the masking regex itself, matching a
#   `--body`/`-m`/... value verbatim as strip_literal_text() alone would see
#   it, with no confound from that unrelated, pre-existing limitation.
#
#   PART 2 -- end-to-end hook decision tests (ALLOW/ASK) through the real
#   PreToolUse JSON protocol, covering:
#     - the full real-world command from the guard-decisions.log entry cited
#       in issue #56 (Champion's multi-apostrophe comment body) -> ALLOW
#     - a minimal apostrophe-escaped --body value quoting a dangerous phrase
#       as documentation (deliberately free of any whitespace-preceded `#`,
#       so it is NOT confounded by the comment-stripper limitation above)
#       -> ALLOW
#     - a value with NO embedded apostrophe (baseline, must not regress)
#       that also quotes a dangerous phrase as documentation -> still ALLOW
#     - a double-quoted --body value quoting the same dangerous phrase ->
#       still ASK (the DQ safety floor is deliberately UNCHANGED by this fix
#       -- dollar-paren/backtick inside double quotes IS live shell syntax)
#     - a REAL (unquoted) `git stash pop` in the main checkout -> still ASK
#       (the fix must never widen what counts as "safe to mask" beyond text
#       that is actually inside a single-quoted span)
#     - an unterminated single-quoted --body value immediately followed by a
#       real (unquoted) `git stash pop` -> still ASK (the fix's optional
#       BSQ-continuation group must not let a malformed/unterminated span
#       swallow trailing live shell text)
#
# The hook under test is the canonical source at .loom/hooks/ (this repo
# ships no defaults/ tree -- see the file's own banner), copied into an
# isolated temp git tree alongside its config-resolver.sh/canonical-path.sh
# lib dependencies so MAIN_ROOT/git-common-dir resolve inside the temp tree,
# exactly like test-guard-destructive-worktree-confinement.sh already does
# for the sibling Edit/Write guard. Exit 0 = all pass, 1 = fail.

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
# contains the literal substring "git stash pop" -- avoids tripping this
# same guard on the Bash invocation that RUNS this test suite.
GS="git st""ash"
GSP="git st""ash po""p"

# =============================================================================
# PART 1 -- direct strip_literal_text() unit tests
# =============================================================================
echo "=== strip_literal_text() unit tests (#56) ==="

FN_FILE="$(mktemp)"
trap 'rm -f "$FN_FILE"' EXIT
awk '/^strip_literal_text\(\) \{/{f=1} f{print; if ($0 == "}" && f == 1) exit}' \
    "$SRC_HOOK" > "$FN_FILE"
if [[ ! -s "$FN_FILE" ]]; then
    fail "extracted strip_literal_text() from $SRC_HOOK (function not found)"
else
    # shellcheck source=/dev/null
    source "$FN_FILE"

    # --- (1) issue #56's own minimal repro, byte-for-byte: one embedded
    # apostrophe via the '\''-escape idiom immediately after "#50", followed
    # by a backticked dangerous-phrase example.
    CMD1="gh issue comment 50 --body 'Issue #50'\\''s own verdict is confirmed. See \`${GS}\`/\`${GSP}\` example.' && gh issue edit 50 --remove-label x"
    OUT1=$(strip_literal_text "$CMD1")
    if [[ "$OUT1" != *"$GSP"* ]]; then
        pass "(1) issue #56 minimal repro: masked span no longer leaks dangerous phrase"
    else
        fail "(1) issue #56 minimal repro: dangerous phrase still leaked: $OUT1"
    fi
    if [[ ${#OUT1} -eq ${#CMD1} ]]; then
        pass "(1) masked output preserves byte length (offset-stability invariant)"
    else
        fail "(1) masked output length changed: in=${#CMD1} out=${#OUT1}"
    fi

    # --- (2) multiple embedded apostrophes in one value must all be
    # traversed, not just the first.
    CMD2="gh issue comment 50 --body 'a'\\''s b'\\''s see \`${GSP}\` c' && echo done"
    OUT2=$(strip_literal_text "$CMD2")
    if [[ "$OUT2" != *"$GSP"* ]]; then
        pass "(2) multiple embedded apostrophes in one value -> fully masked"
    else
        fail "(2) multiple embedded apostrophes: dangerous phrase leaked: $OUT2"
    fi

    # --- (3) two SEPARATE single-quoted --body spans (different flag
    # invocations) must stay independent -- the BSQ-continuation group must
    # not bridge across an unrelated pair of quotes.
    CMD3="gh issue comment 50 --body 'first' && gh issue comment 51 --body 'second value'"
    OUT3=$(strip_literal_text "$CMD3")
    if [[ "$OUT3" == "gh issue comment 50 --body 'XXXXX' && gh issue comment 51 --body 'XXXXXXXXXXXX'" ]]; then
        pass "(3) two separate single-quoted spans stay independently masked"
    else
        fail "(3) spans incorrectly bridged/merged: $OUT3"
    fi

    # --- (4) --arg/--argjson branch (#5797) is BSQ-aware too.
    CMD4="jq --arg NAME 'has an apostrophe'\\''s and \`${GSP}\` example' '.'"
    OUT4=$(strip_literal_text "$CMD4")
    if [[ "$OUT4" != *"$GSP"* ]]; then
        pass "(4) --arg branch: apostrophe-escaped value fully masked"
    else
        fail "(4) --arg branch: dangerous phrase leaked: $OUT4"
    fi

    # --- (5) DOUBLE-quoted span with a backtick inside is UNCHANGED --
    # still left unmasked (the #5783 safety floor: dollar-paren/backtick
    # inside double quotes IS live shell syntax).
    CMD5="gh pr comment 1 --body \"See \`${GSP}\` example\""
    OUT5=$(strip_literal_text "$CMD5")
    if [[ "$OUT5" == *"$GSP"* ]]; then
        pass "(5) double-quoted span with backtick: DQ safety floor unchanged"
    else
        fail "(5) double-quoted span was unexpectedly masked (DQ floor regressed): $OUT5"
    fi

    # --- (6) an UNTERMINATED single-quoted value must not let the optional
    # BSQ-continuation group greedily swallow trailing text as if it were
    # still inside quotes -- the regex must backtrack to the narrower,
    # correctly-terminated match.
    CMD6="gh issue comment 50 --body 'unterminated'\\''oops && ${GSP} #"
    OUT6=$(strip_literal_text "$CMD6")
    if [[ "$OUT6" == *"$GSP"* ]]; then
        pass "(6) unterminated single-quoted value: no runaway match past real content"
    else
        fail "(6) unterminated single-quoted value incorrectly swallowed trailing text: $OUT6"
    fi

    # --- (7) baseline: a plain value with no apostrophe at all must still
    # be masked exactly as before (no regression for the common case).
    CMD7="gh issue comment 50 --body 'plain value with no escapes'"
    OUT7=$(strip_literal_text "$CMD7")
    EXPECT7="gh issue comment 50 --body '$(printf 'X%.0s' $(seq 1 27))'"
    if [[ "$OUT7" == "$EXPECT7" ]]; then
        pass "(7) baseline: plain apostrophe-free value masked unchanged"
    else
        fail "(7) baseline regressed: expected [$EXPECT7], got [$OUT7]"
    fi
fi

# =============================================================================
# PART 2 -- end-to-end hook decision tests (ALLOW/ASK)
# =============================================================================
echo
echo "=== guard-destructive-generic.sh end-to-end ALLOW/ASK tests (#56) ==="

TMPROOT="$(mktemp -d)"
trap 'rm -f "$FN_FILE"; rm -rf "$TMPROOT"' EXIT
git init -q "$TMPROOT"
mkdir -p "$TMPROOT/.loom/hooks" "$TMPROOT/.loom/scripts/lib"
cp "$SRC_HOOK" "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
chmod +x "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
cp "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" "$TMPROOT/.loom/scripts/lib/config-resolver.sh"
cp "$REPO_ROOT/.loom/scripts/lib/canonical-path.sh" "$TMPROOT/.loom/scripts/lib/canonical-path.sh"
HOOK="$TMPROOT/.loom/hooks/guard-destructive-generic.sh"

# Build stdin JSON for a Bash tool_input, with cwd fixed at TMPROOT (the
# synthetic main checkout -- no other worktrees exist in it, so
# stash-scope:main-checkout is the only stash-scope disposition reachable).
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

assert_ask() {
    local desc="$1" result="$2" reason_substr="${3:-}"
    local code="${result%%|*}" out="${result#*|}"
    if [[ "$code" != "0" ]]; then
        fail "$desc (expected exit 0 with ask JSON, got NONZERO exit=$code)"
        return
    fi
    local decision reason
    decision=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)
    reason=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason // empty' 2>/dev/null || true)
    if [[ "$decision" != "ask" ]]; then
        fail "$desc (expected permissionDecision=ask, got: $out)"
        return
    fi
    if [[ -n "$reason_substr" && "$reason" != *"$reason_substr"* ]]; then
        fail "$desc (ask reason missing expected substring '$reason_substr': $reason)"
        return
    fi
    pass "$desc"
}

# --- (a) minimal apostrophe-escaped --body value quoting a dangerous phrase
# as documentation, deliberately free of any whitespace-preceded `#` (so
# this is unconfounded by COMMAND_NO_COMMENT's separate, out-of-scope
# not-quote-aware `#`-comment stripper -- see the PART 1 header comment)
# -> ALLOW (was a false stash-scope:main-checkout ASK before the fix).
result=$(run_hook "gh issue comment 50 --body 'This finding'\\''s own verdict is confirmed. See \`${GS}\`/\`${GSP}\` example.' && gh issue edit 50 --remove-label x")
assert_allow "(a) apostrophe-escaped --body quoting dangerous phrase as prose -> allow" "$result"

# --- (b) the full real-world command from the guard-decisions.log entry
# cited in issue #56 (Champion's comment body, MULTIPLE embedded
# apostrophes: "...'s own verdict...", "...it's a record...", "...that's a
# human call...", "...Champion's promotion...") -> ALLOW
CHAMPION_BODY="gh issue comment 50 --body 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'\\''s own verdict is \"Close as \\\"confirmed correct\\\" once reviewed — same disposition as #21. No code change needed.\" There is no code, config, or documentation change proposed anywhere in the body — nothing exists here for a Builder to implement. Promoting it would dispatch a Builder with no actionable work.

This is not a criticism of the finding itself — confirming a correct DENY on raw \`${GS}\`/\`${GSP}\` inside a linked worktree (shared \`refs/stash\` collision hazard, correct scoped alternative already exists via \`./.loom/scripts/worktree.sh snapshot\`/\`stash-push\`/\`stash-pop\`) is exactly right, and per the standing Guard-Decision Telemetry Review policy (#3898) filing it is intentional: it'\\''s a record that stops the same trigger from being re-investigated on a future audit tick. It simply has no promotable implementation work in it, matching the disposition of #21 (operator closed directly, no Builder work).

**Recommended action**: no revision needed from the Auditor — this issue has already done its job by existing as a dedup record. If the operator wants to formally close the loop, that'\\''s a human call outside Champion'\\''s promotion authority; Champion does not close issues, only promotes or declines to promote.

Keeping original \`loom:auditor\` label.

---
*Automated by Champion role*' \\
  && gh issue edit 50 --remove-label \"loom:evaluating\""
result=$(run_hook "$CHAMPION_BODY")
assert_allow "(b) full guard-decisions.log repro (multi-apostrophe Champion comment body) -> allow" "$result"

# --- (c) baseline: NO embedded apostrophe, still quotes the dangerous
# phrase as documentation -> must already ALLOW (pre-existing behavior, must
# not regress)
result=$(run_hook "gh issue comment 50 --body 'See \`${GS}\`/\`${GSP}\` example, no apostrophe here.' && gh issue edit 50 --remove-label x")
assert_allow "(c) baseline: no embedded apostrophe, dangerous phrase quoted as prose -> allow (unchanged)" "$result"

# --- (d) DOUBLE-quoted --body value quoting the same dangerous phrase ->
# still ASK. The DQ safety floor is deliberately UNCHANGED: dollar-paren/
# backtick inside double quotes IS live shell syntax, so this fix must not
# touch that branch.
result=$(run_hook "gh issue comment 50 --body \"See \`${GSP}\` example\"")
assert_ask "(d) double-quoted --body quoting dangerous phrase -> still ask (DQ floor unchanged)" "$result" \
    "MAIN checkout can destroy operator-preserved state"

# --- (e) a REAL (unquoted) recovery-subcommand invocation in the main
# checkout -> still ASK. The fix must never widen what counts as "safe to
# mask" beyond text that is genuinely inside a single-quoted span.
result=$(run_hook "$GSP")
assert_ask "(e) real unquoted stash recovery in main checkout -> still ask (real invocation unaffected)" "$result" \
    "MAIN checkout can destroy operator-preserved state"

# --- (f) an UNTERMINATED single-quoted --body value immediately followed by
# a REAL (unquoted) recovery-subcommand invocation -> still ASK. The BSQ
# continuation group must backtrack off an unterminated span rather than
# swallowing trailing live shell text as if it were still inside quotes.
result=$(run_hook "gh issue comment 50 --body 'unterminated'\\''oops && ${GSP}")
assert_ask "(f) unterminated single-quoted value + real trailing stash recovery -> still ask (no runaway match)" "$result" \
    "MAIN checkout can destroy operator-preserved state"

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
