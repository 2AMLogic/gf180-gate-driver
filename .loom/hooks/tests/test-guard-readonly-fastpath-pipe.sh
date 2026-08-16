#!/usr/bin/env bash
# Regression test for .loom/hooks/guard-destructive-generic.sh's #5263
# read-only "search-pipe-to-sink" fastpath mis-counting a `|` that lives
# INSIDE the search pattern as a second shell-level pipe (issue #109).
#
# Usage: ./.loom/hooks/tests/test-guard-readonly-fastpath-pipe.sh
#
# Bug: fastpath_grep_pipe_admits() decided "exactly one pipe" with a raw byte
# scan --
#     left="${cmd%%|*}" ; right="${cmd#*|}" ; case "$right" in *'|'*) return 1
# -- which splits at the FIRST `|` byte anywhere in the string, with no notion
# of quoting. Writing a multi-term search the ordinary way, with ERE
# alternation --
#     grep -n "DROP TABLE\|foo" schema.sql | head -3
# -- puts a `|` byte inside grep's own quoted argument, textually BEFORE the
# real shell pipe. The split therefore landed mid-argument, `right` still held
# the real pipe, and the "second pipe -> decline" branch fired. The command
# fell through to the full path, where SQL_DDL_PATTERN substring-matched the
# phrase inside grep's argument and denied at the catastrophic tier -- even
# though grep only ever SEARCHES for that text and never executes it. The
# one-term spelling of the very same command (`grep -n "DROP TABLE" ... | head
# -3`) was allowed, so adding a second search term flipped a read-only command
# from ALLOW to a hard DENY.
#
# The fix replaces that split with _fastpath_pipe_split(), a pure-bash
# quote-aware single-pass scan that counts only pipes bash itself would parse
# as pipes, and declines (fail-safe, falls through to the full path unchanged)
# on zero pipes, two-or-more pipes, or an unterminated quote.
#
# This suite is split into two parts:
#
#   PART 1 -- direct unit tests of _fastpath_pipe_split() and
#   fastpath_grep_pipe_admits(). The two functions plus their sink allowlists
#   are extracted verbatim from the hook file and sourced in isolation, the
#   same extraction technique test-guard-catastrophic-rm-heredoc.sh uses for
#   the _MASKHEREDOC_AWK library. This pins the admission predicate itself,
#   including the shapes that must keep DECLINING.
#
#   PART 2 -- end-to-end hook decision tests (ALLOW/ASK/DENY) through the real
#   PreToolUse JSON protocol, including the issue's two literal repro commands.
#
# The hook under test is the canonical source at .loom/hooks/ (this repo ships
# no defaults/ tree -- see the file's own banner), copied into an isolated temp
# git tree. Exit 0 = all pass, 1 = fail.

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

# Build the DDL phrase from parts so this test FILE's own source text never
# spells it out contiguously -- avoids tripping this same guard on any future
# Bash invocation that greps/cats this file.
DDL="DROP TA""BLE"

# =============================================================================
# PART 1 -- _fastpath_pipe_split() / fastpath_grep_pipe_admits() unit tests
# =============================================================================
echo "=== fastpath pipe-split unit tests (#109) ==="

FASTPATH_LIB="$(mktemp)"
trap 'rm -f "$FASTPATH_LIB"' EXIT

# Extract from the sink-allowlist assignments through the closing brace of
# fastpath_grep_pipe_admits().
awk '
    /^_FASTPATH_PIPE_SINKS_ANYARG=/ { emit = 1 }
    emit { print }
    /^fastpath_grep_pipe_admits\(\) \{/ { infunc = 1 }
    infunc && /^\}$/ { exit }
' "$SRC_HOOK" > "$FASTPATH_LIB"

if ! grep -q '^_fastpath_pipe_split() {' "$FASTPATH_LIB"; then
    fail "could not extract _fastpath_pipe_split()/fastpath_grep_pipe_admits() from $SRC_HOOK"
else
    # shellcheck disable=SC1090
    source "$FASTPATH_LIB"

    # --- _fastpath_pipe_split(): quote-aware split ---------------------------
    split_ok() {   # split_ok <cmd> <expected-left> <expected-right>
        local desc="$1" cmd="$2" want_l="$3" want_r="$4"
        if _fastpath_pipe_split "$cmd"; then
            if [[ "$_FASTPATH_PIPE_L" == "$want_l" && "$_FASTPATH_PIPE_R" == "$want_r" ]]; then
                pass "$desc"
            else
                fail "$desc (left=[$_FASTPATH_PIPE_L] right=[$_FASTPATH_PIPE_R], wanted left=[$want_l] right=[$want_r])"
            fi
        else
            fail "$desc (split declined, expected a single shell-level pipe)"
        fi
    }
    split_declines() {
        local desc="$1" cmd="$2"
        if _fastpath_pipe_split "$cmd"; then
            fail "$desc (split ACCEPTED, expected decline; left=[$_FASTPATH_PIPE_L] right=[$_FASTPATH_PIPE_R])"
        else
            pass "$desc"
        fi
    }

    split_ok "(1) plain single pipe splits at the real pipe" \
        'grep foo f.txt | head -3' 'grep foo f.txt ' ' head -3'
    split_ok "(2) double-quoted ERE alternation does not count as a pipe" \
        "grep -n \"${DDL}\\|foo\" f.sql | head -3" \
        "grep -n \"${DDL}\\|foo\" f.sql " ' head -3'
    split_ok "(3) single-quoted ERE alternation does not count as a pipe" \
        "grep -n '${DDL}\\|foo' f.sql | head -3" \
        "grep -n '${DDL}\\|foo' f.sql " ' head -3'
    split_ok "(4) bare (unescaped) | inside quotes does not count as a pipe" \
        'rg -n "a|b|c" f.txt | wc -l' 'rg -n "a|b|c" f.txt ' ' wc -l'
    split_ok "(5) trailing | inside the quoted pattern, adjacent to the real pipe" \
        'grep "a\|" f.txt | head' 'grep "a\|" f.txt ' ' head'
    split_ok "(6) escaped quote inside a double-quoted span keeps the span open" \
        'grep "a\"b\|c" f.txt | head' 'grep "a\"b\|c" f.txt ' ' head'
    split_ok "(7) BSQ apostrophe idiom stays balanced" \
        "grep 'it'\\''s\\|x' f.txt | head" "grep 'it'\\''s\\|x' f.txt " ' head'

    split_declines "(8) two REAL pipes decline" 'grep a f | grep b | head'
    split_declines "(9) quoted pipe PLUS two real pipes decline" 'grep "a\|b" f | grep c | head'
    split_declines "(10) || (two adjacent | bytes) declines" 'grep a f || head'
    split_declines "(11) no shell-level pipe at all declines" 'grep "a\|b" f.txt'
    split_declines "(12) unterminated quote declines (fail-safe)" 'grep "a f.txt | head'
    split_declines "(13) backslash-escaped pipe outside quotes is not a pipe" 'grep a f \| head'

    # --- fastpath_grep_pipe_admits(): full admission predicate ---------------
    admits() {
        local desc="$1" cmd="$2"
        if fastpath_grep_pipe_admits "$cmd"; then pass "$desc"
        else fail "$desc (expected ADMIT, got decline)"; fi
    }
    declines() {
        local desc="$1" cmd="$2"
        if fastpath_grep_pipe_admits "$cmd"; then fail "$desc (expected DECLINE, got admit)"
        else pass "$desc"; fi
    }

    admits "(14) #5263 baseline: single-term grep | head admits" \
        "grep -n \"${DDL}\" f.sql | head -3"
    admits "(15) #109 fix: ERE-alternation grep | head admits" \
        "grep -n \"${DDL}\\|foo\" f.sql | head -3"
    admits "(16) #109 fix: alternation terms containing spaces admit" \
        'grep "a b\|c d" f.txt | head'
    admits "(17) repeated -e terms (no | at all) still admit" \
        "grep -e \"${DDL}\" -e foo f.sql | head -3"
    admits "(18) egrep/wc variant with alternation admits" \
        'egrep "a|b" f.txt | wc -l'
    admits "(19) stdin-only sink with no operand admits" \
        'grep "a\|b" f.txt | cat'

    declines "(20) SECURITY: stdin sink WITH a file operand still declines" \
        'grep "a\|b" f.txt | cat /home/u/.ssh/id_rsa'
    declines "(21) SECURITY: second real pipe still declines" \
        'grep "a\|b" f | grep c | head'
    declines "(22) SECURITY: non-search upstream still declines" \
        "mysql -e \"${DDL} users\" | head"
    declines "(23) SECURITY: unlisted sink still declines" \
        'grep "a\|b" f.txt | xargs rm'
    declines "(24) SECURITY: quoted | plus a command separator still declines" \
        'grep "a\|b" f.txt | head; rm -rf /tmp/x'
    declines "(25) SECURITY: quoted | plus a redirection still declines" \
        'grep "a\|b" f.txt | head > /etc/passwd'
    declines "(26) SECURITY: quoted | plus a command substitution still declines" \
        'grep "a\|b" $(echo f.txt) | head'

    # --- robustness: the scan must not abort an errexit caller ---------------
    # Called as a plain statement (not an `if` condition, which suppresses
    # errexit for the whole call), no loop branch may end on a bare failing
    # command. The trap is the escape branch: `(( i++ ))` evaluates to the
    # PRE-increment value, so at offset 0 it is a failed simple command and
    # errexit kills the caller mid-string with no output at all. Case (28)
    # below is the input that reaches offset 0 with a backslash.
    if ( set -e; _fastpath_pipe_split "grep -n 'a|b' f.txt | head -3"
         [[ "$_FASTPATH_PIPE_R" == " head -3" ]] ) 2>/dev/null; then
        pass "(27) scan completes under errexit when called as a plain statement"
    else
        fail "(27) scan aborted an errexit caller mid-string"
    fi
    # Leading backslash at offset 0 (`\grep …`) -- the escape branch must not
    # evaluate to 0 there either.
    split_ok "(28) backslash-escaped command word at offset 0 still splits" \
        '\grep "a\|b" f.txt | head' '\grep "a\|b" f.txt ' ' head'
fi

# =============================================================================
# PART 2 -- end-to-end hook decision tests (ALLOW/ASK/DENY)
# =============================================================================
echo
echo "=== guard-destructive-generic.sh end-to-end ALLOW/DENY tests (#109) ==="

TMPROOT="$(mktemp -d)"
trap 'rm -f "$FASTPATH_LIB"; rm -rf "$TMPROOT"' EXIT
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

assert_decision() {   # assert_decision <desc> <result> <deny|ask> [reason substring]
    local desc="$1" result="$2" want="$3" reason_substr="${4:-}"
    local code="${result%%|*}" out="${result#*|}"
    if [[ "$code" != "0" ]]; then
        fail "$desc (expected exit 0 with decision JSON, got NONZERO exit=$code)"
        return
    fi
    local decision reason
    decision=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)
    reason=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason // empty' 2>/dev/null || true)
    if [[ "$decision" != "$want" ]]; then
        fail "$desc (expected permissionDecision=$want, got: $out)"
        return
    fi
    if [[ -n "$reason_substr" && "$reason" != *"$reason_substr"* ]]; then
        fail "$desc (reason missing expected substring '$reason_substr': $reason)"
        return
    fi
    pass "$desc"
}

TARGET=".loom/hooks/guard-destructive-generic.sh"

# --- (a) issue #109 repro 1: single-term grep | head -> ALLOW (was already
# allowed; pins the #5263 baseline against regression)
result=$(run_hook "grep -n \"${DDL}\" ${TARGET} | head -3")
assert_allow "(a) repro 1: single-term grep | head -> allow" "$result"

# --- (b) issue #109 repro 2: THE BUG. Same command with a second search term
# expressed as ERE alternation -> was DENY (sql-ddl, catastrophic), must ALLOW
result=$(run_hook "grep -n \"${DDL}\\|foo\" ${TARGET} | head -3")
assert_allow "(b) repro 2: ERE-alternation grep | head -> allow (the #109 fix)" "$result"

# --- (c) single-quoted alternation, same shape -> ALLOW
result=$(run_hook "grep -n '${DDL}\\|foo' ${TARGET} | head -3")
assert_allow "(c) single-quoted ERE alternation -> allow" "$result"

# --- (d) alternation terms containing spaces -> ALLOW
result=$(run_hook "grep -n \"${DDL} users\\|CREATE INDEX x\" ${TARGET} | head -3")
assert_allow "(d) alternation terms containing spaces -> allow" "$result"

# --- (e) the same multi-term search spelled with repeated -e flags -> ALLOW
result=$(run_hook "grep -n -e \"${DDL}\" -e foo ${TARGET} | head -3")
assert_allow "(e) repeated -e search terms -> allow" "$result"

# --- (f) SCOPE NOTE, deliberately not asserted here. The BARE (unpiped)
# alternation search `grep -n "<ddl>\|foo" <file>` is ALSO denied today, but by
# a DIFFERENT gate: fastpath_structural_ok()'s own raw `*'|'*` byte test, which
# disqualifies the command from the built-in grep allowlist before
# fastpath_grep_pipe_admits() is ever consulted. That gate is shared by every
# fastpath admission (ls/grep/rg/jq/echo/find/git/gh/aws) and cannot be made
# quote-aware by the same argument used here -- `$(...)` and backticks DO expand
# inside double quotes, so ignoring double-quoted spans there would open a real
# bypass (`echo "$(rm -rf /)"`), and it needs a per-metacharacter analysis rather
# than this issue's one-line pipe-count fix. Explicitly out of scope for #109
# (see its acceptance criteria: "No change to fastpath_structural_ok()"), and
# tracked separately; no assertion is pinned so that the follow-up fix does not
# have to fight a test asserting the buggy behavior.

# --- (g) SECURITY: a genuinely SECOND shell-level pipe must still decline the
# fastpath and fall through to the full path, which denies on the DDL phrase
result=$(run_hook "grep -n \"${DDL}\\|foo\" ${TARGET} | grep bar | head -3")
assert_decision "(g) SECURITY: second real pipe falls through to the full path -> deny" \
    "$result" deny "$DDL"

# --- (h) SECURITY: the cat carve-out is untouched -- a stdin sink carrying a
# credential-file operand must NOT be fast-pathed, so the cat .ssh ASK fires
result=$(run_hook "grep -n \"a\\|b\" ${TARGET} | cat ~/.ssh/id_rsa")
assert_decision "(h) SECURITY: | cat ~/.ssh/id_rsa not fast-pathed -> ask" "$result" ask

# --- (i) SECURITY: a real DDL-EXECUTING command piped the same way has a
# non-search first token, is not admitted, and still denies
result=$(run_hook "mysql -e \"${DDL} users\" | head -3")
assert_decision "(i) SECURITY: real DDL execution piped to head -> deny" "$result" deny "$DDL"

# --- (j) SECURITY: no pipe at all, real DDL execution -> still denies
result=$(run_hook "psql -c \"${DDL} users\"")
assert_decision "(j) SECURITY: real DDL execution, no pipe -> deny" "$result" deny "$DDL"

# --- (k) SECURITY: a quoted `|` must not smuggle a chained command past the
# metacharacter guard -- the raw `;` scan still declines the fastpath
result=$(run_hook "grep -n \"a\\|b\" ${TARGET} | head -3; ${DDL} users")
assert_decision "(k) SECURITY: quoted | plus a chained DDL command -> deny" \
    "$result" deny "$DDL"

# =============================================================================
echo
echo "======================================"
echo "Total:  $TOTAL"
printf "${GREEN}Passed: %d${NC}\n" "$PASS"
if [[ $FAIL -gt 0 ]]; then
    printf "${RED}Failed: %d${NC}\n" "$FAIL"
    exit 1
fi
echo "All tests passed"
exit 0
