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
# This suite is split into three parts:
#
#   PART 1 -- direct unit tests of _fastpath_pipe_split() and
#   fastpath_grep_pipe_admits(). The two functions plus their sink allowlists
#   are extracted verbatim from the hook file and sourced in isolation, the
#   same extraction technique test-guard-catastrophic-rm-heredoc.sh uses for
#   the _MASKHEREDOC_AWK library. This pins the admission predicate itself,
#   including the shapes that must keep DECLINING.
#
#   PART 1b -- direct unit tests of fastpath_multistatement_admits() /
#   _fastpath_split_statements() (issue #198): the widened structural fastpath
#   that recognizes a `;`/newline/`&&`-joined SEQUENCE of statements as
#   fastpath-eligible when every statement independently matches one of the
#   two single-statement admitted shapes above. See that function's own header
#   comment in the hook source for why this direction does not reintroduce the
#   mask_ask_positional_args() regression documented at ~3295-3309 there.
#
#   PART 2 -- end-to-end hook decision tests (ALLOW/ASK/DENY) through the real
#   PreToolUse JSON protocol, including the issue's two literal repro commands
#   and (issue #198) the multi-statement repro/safety-floor cases.
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
# PART 1 -- fastpath_structural_ok() / _fastpath_pipe_split() /
#           fastpath_grep_pipe_admits() unit tests
# =============================================================================
echo "=== fastpath pipe-split unit tests (#109, #127) ==="

FASTPATH_LIB="$(mktemp)"
trap 'rm -f "$FASTPATH_LIB"' EXIT

# Extract from fastpath_structural_ok() (the #127 target) through the closing
# brace of fastpath_grep_pipe_admits() -- this range also picks up
# fastpath_builtin_admits() and the sink-allowlist assignments in between,
# which is harmless (unused by these tests, but self-contained).
awk '
    /^fastpath_structural_ok\(\) \{/ { emit = 1 }
    emit { print }
    /^fastpath_grep_pipe_admits\(\) \{/ { infunc = 1 }
    infunc && /^\}$/ { exit }
' "$SRC_HOOK" > "$FASTPATH_LIB"

if ! grep -q '^_fastpath_pipe_split() {' "$FASTPATH_LIB" || ! grep -q '^fastpath_structural_ok() {' "$FASTPATH_LIB"; then
    fail "could not extract fastpath_structural_ok()/_fastpath_pipe_split()/fastpath_grep_pipe_admits() from $SRC_HOOK"
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

    # --- _fastpath_has_unquoted_pipe(): quote-aware "is there a LIVE pipe on
    # this line" predicate (#127), factored out of the same quote-tracking scan
    # as _fastpath_pipe_split() above and used by fastpath_structural_ok() so a
    # `|` byte inside a quoted argument no longer disqualifies a BARE (unpiped)
    # command from the built-in fastpath allowlist.
    has_pipe() {
        local desc="$1" cmd="$2"
        if _fastpath_has_unquoted_pipe "$cmd"; then pass "$desc"
        else fail "$desc (expected TRUE/has-live-pipe, got FALSE)"; fi
    }
    no_pipe() {
        local desc="$1" cmd="$2"
        if _fastpath_has_unquoted_pipe "$cmd"; then fail "$desc (expected FALSE/no-live-pipe, got TRUE)"
        else pass "$desc"; fi
    }

    no_pipe "(29) bare double-quoted ERE alternation has no live pipe" \
        "grep -n \"${DDL}\\|foo\" f.sql"
    no_pipe "(30) bare single-quoted ERE alternation has no live pipe" \
        "grep -n '${DDL}\\|foo' f.sql"
    no_pipe "(31) no pipe byte anywhere has no live pipe" \
        "grep -n \"${DDL}\" f.sql"
    has_pipe "(32) a real unquoted pipe is detected" \
        'grep foo f.txt | head -3'
    has_pipe "(33) a quoted pipe PLUS a real pipe is still detected" \
        "grep -n \"${DDL}\\|foo\" f.sql | head -3"
    has_pipe "(34) FAIL-SAFE: an unterminated quote is treated as having a live pipe (decline)" \
        "grep -n \"${DDL}\\|foo f.sql"
    has_pipe "(35) FAIL-SAFE: an unterminated single quote is treated as having a live pipe (decline)" \
        "grep -n '${DDL}\\|foo f.sql"

    # --- fastpath_structural_ok(): the #127 target itself ---------------------
    # Direct unit tests of the shared structural pre-check, now that its `|`
    # test is quote-aware while every other metacharacter (`; & < > `` `` $(`)
    # stays a raw byte scan (explicitly out of scope per the issue).
    structural_ok() {
        local desc="$1" cmd="$2"
        if fastpath_structural_ok "$cmd"; then pass "$desc"
        else fail "$desc (expected structural_ok to ADMIT, got decline)"; fi
    }
    structural_declines() {
        local desc="$1" cmd="$2"
        if fastpath_structural_ok "$cmd"; then fail "$desc (expected structural_ok to DECLINE, got admit)"
        else pass "$desc"; fi
    }

    structural_ok "(36) #127 fix: bare double-quoted ERE alternation now admits" \
        "grep -n \"${DDL}\\|foo\" f.sql"
    structural_ok "(37) #127 fix: bare single-quoted ERE alternation now admits" \
        "grep -n '${DDL}\\|foo' f.sql"
    structural_ok "(38) single-term grep (no | at all) still admits (baseline, unchanged)" \
        "grep -n \"${DDL}\" f.sql"
    structural_declines "(39) x | y: a genuinely live pipe still declines" \
        'grep foo f.txt | head'
    structural_declines "(40) quoted | PLUS a live pipe still declines" \
        "grep -n \"${DDL}\\|foo\" f.sql | head"
    structural_declines "(41) FAIL-SAFE: unterminated quote still declines" \
        "grep -n \"${DDL}\\|foo f.sql"
    structural_declines "(42) a; b: chaining still declines (raw scan, unchanged)" \
        'echo hi; rm -rf /'
    structural_declines "(43) a && b: chaining still declines (raw scan, unchanged)" \
        'echo hi && rm -rf /'
    structural_declines "(44) a > b: redirection still declines (raw scan, unchanged)" \
        'echo hi > /etc/passwd'
    structural_declines "(45) a < b: redirection still declines (raw scan, unchanged)" \
        'echo hi < /etc/passwd'
    structural_declines "(46) backtick command substitution still declines (raw scan, unchanged)" \
        'echo `rm -rf /`'
    structural_declines "(47) \$(...) command substitution still declines (raw scan, unchanged)" \
        'echo "$(rm -rf /)"'
    structural_declines "(48) \$(...) substitution INSIDE an otherwise-quoted arg still declines" \
        'echo "prefix $(rm -rf /) suffix"'
    structural_declines "(49) newline still declines (unchanged)" \
        "$(printf 'echo hi\nrm -rf /')"
fi

# =============================================================================
# PART 1b -- fastpath_multistatement_admits() / _fastpath_split_statements()
# unit tests (#198)
# =============================================================================
echo
echo "=== fastpath multi-statement unit tests (#198) ==="

MULTI_LIB="$(mktemp)"
trap 'rm -f "$FASTPATH_LIB" "$MULTI_LIB"' EXIT

# Extract from fastpath_structural_ok() (the shared structural pre-check)
# through the closing brace of _fastpath_split_statements() -- covers
# fastpath_structural_ok(), fastpath_builtin_admits(), the pipe-sink
# allowlists, _fastpath_pipe_split(), fastpath_grep_pipe_admits(),
# fastpath_multistatement_admits(), and _fastpath_split_statements(), all of
# fastpath_multistatement_admits()'s own dependencies in one contiguous span.
awk '
    /^fastpath_structural_ok\(\) \{/ { emit = 1 }
    emit { print }
    /^_fastpath_split_statements\(\) \{/ { infunc = 1 }
    infunc && /^\}$/ { exit }
' "$SRC_HOOK" > "$MULTI_LIB"

if ! grep -q '^fastpath_multistatement_admits() {' "$MULTI_LIB"; then
    fail "could not extract fastpath_multistatement_admits()/_fastpath_split_statements() from $SRC_HOOK"
else
    # shellcheck disable=SC1090
    source "$MULTI_LIB"

    # --- _fastpath_split_statements(): quote-aware statement splitter -------
    split_stmts_ok() {   # split_stmts_ok <desc> <cmd> <expected-statement>...
        local desc="$1" cmd="$2"; shift 2
        local -a want=("$@")
        if _fastpath_split_statements "$cmd"; then
            if [[ "${#_FASTPATH_STATEMENTS[@]}" -eq "${#want[@]}" ]]; then
                local i ok=1
                for (( i = 0; i < ${#want[@]}; i++ )); do
                    [[ "${_FASTPATH_STATEMENTS[i]}" == "${want[i]}" ]] || ok=0
                done
                if [[ "$ok" -eq 1 ]]; then
                    pass "$desc"
                else
                    fail "$desc (statements=[${_FASTPATH_STATEMENTS[*]}], wanted=[${want[*]}])"
                fi
            else
                fail "$desc (got ${#_FASTPATH_STATEMENTS[@]} statements [${_FASTPATH_STATEMENTS[*]}], wanted ${#want[@]} [${want[*]}])"
            fi
        else
            fail "$desc (split declined, expected admission)"
        fi
    }
    split_stmts_declines() {
        local desc="$1" cmd="$2"
        if _fastpath_split_statements "$cmd"; then
            fail "$desc (split ACCEPTED, expected decline; statements=[${_FASTPATH_STATEMENTS[*]}])"
        else
            pass "$desc"
        fi
    }

    split_stmts_ok "(29) two ';'-separated statements split cleanly" \
        'echo "a"; echo "b"' 'echo "a"' ' echo "b"'
    split_stmts_ok "(30) newline-separated statements split cleanly" \
        $'echo "a"\necho "b"' 'echo "a"' 'echo "b"'
    split_stmts_ok "(31) '&&'-separated statements split cleanly" \
        'echo "a" && echo "b"' 'echo "a" ' ' echo "b"'
    split_stmts_ok "(32) three statements mixing ';' and newline, no doubled separator" \
        $'echo "a"\necho "b"; echo "c"' 'echo "a"' 'echo "b"' ' echo "c"'
    split_stmts_ok "(33) ';' inside a quoted argument is not a separator" \
        'echo "a; b"' 'echo "a; b"'
    split_stmts_ok "(34) '&&' would-be split with the DDL phrase safely inside quotes" \
        "echo \"${DDL}\" && echo done" "echo \"${DDL}\" " ' echo done'

    split_stmts_declines "(35) unterminated quote declines (fail-safe)" 'echo "a; echo "b"'
    split_stmts_declines "(36) a lone '&' (backgrounding) declines -- not a simple sequencer" \
        'echo "a" & echo "b"'
    split_stmts_declines "(37) trailing ';' yields an empty statement -- declines" 'echo "a";'
    split_stmts_declines "(38) leading ';' yields an empty statement -- declines" ';echo "a"'
    split_stmts_declines "(39) doubled ';;' yields an empty statement -- declines" 'echo "a";;echo "b"'
    split_stmts_declines "(39b) ';' immediately followed by newline yields an empty statement -- declines" \
        $'echo "a";\necho "b"'

    # --- fastpath_multistatement_admits(): full admission predicate ---------
    multi_admits() {
        local desc="$1" cmd="$2"
        if fastpath_multistatement_admits "$cmd"; then pass "$desc"
        else fail "$desc (expected ADMIT, got decline)"; fi
    }
    multi_declines() {
        local desc="$1" cmd="$2"
        if fastpath_multistatement_admits "$cmd"; then fail "$desc (expected DECLINE, got admit)"
        else pass "$desc"; fi
    }

    multi_admits "(40) #198 repro: echo + grep|head over the DDL phrase (newline-joined)" \
        "echo \"a\"
grep -n \"${DDL}\" f.sql | head -5"
    multi_admits "(41) ';'-joined echo + grep|head over the DDL phrase" \
        "echo \"a\"; grep -n \"${DDL}\" f.sql | head -5"
    multi_admits "(42) three admitted statements ('&&'-joined) all bare builtins" \
        'echo "a" && ls && echo "b"'
    multi_declines "(43) a single statement (no separator at all) declines -- not this fastpath's job" \
        "grep -n \"${DDL}\" f.sql"
    multi_declines "(44) SECURITY: one admitted statement + one live-DDL statement still declines" \
        "echo \"a\"; psql -c \"${DDL} users\""
    multi_declines "(45) SECURITY: an unadmitted statement anywhere in the sequence still declines" \
        'echo "a"; curl http://example.com; echo "b"'
    multi_declines "(46) unterminated quote anywhere in the block declines (fail-safe)" \
        "echo \"a\"; grep -n \"${DDL} f.sql | head"
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

assert_not_fastpath_allowed() {
    # Weaker than assert_decision: only pins "the fastpath declined" (not a
    # silent ALLOW), without coupling to which downstream deny/ask rule fires.
    # Used for #127 regression cases where the point is that
    # fastpath_structural_ok()'s non-`|` metacharacters still decline exactly
    # as before -- the specific full-path outcome for those shapes is a
    # different gate's concern, not this file's.
    local desc="$1" result="$2"
    local code="${result%%|*}" out="${result#*|}"
    if [[ "$code" == "0" && -z "$out" ]]; then
        fail "$desc (expected fastpath to DECLINE, got silent ALLOW)"
    else
        pass "$desc"
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

# --- (f) #127 fix: the BARE (unpiped) alternation search
# `grep -n "<ddl>\|foo" <file>` used to be denied by a DIFFERENT gate:
# fastpath_structural_ok()'s own raw `*'|'*` byte test, which disqualified the
# command from the built-in grep allowlist before fastpath_grep_pipe_admits()
# was ever consulted. #127 made ONLY that `|` check quote-aware (via
# _fastpath_has_unquoted_pipe(), factored out of _fastpath_pipe_split() above)
# -- the other metacharacters (`; & < > \` $(`) in that same gate stay raw byte
# scans on purpose (see fastpath_structural_ok()'s own comment). This is now a
# real ALLOW, pinning the #127 fix.
result=$(run_hook "grep -n \"${DDL}\\|foo\" ${TARGET}")
assert_allow "(f) #127 fix: BARE ERE-alternation grep (no pipe at all) -> allow" "$result"

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

# --- (l) issue #198: the same admitted grep|head statement, but preceded by
# an unrelated read-only echo statement on its own line -- was previously
# denied on the full path (fell out of both single-statement carve-outs);
# must now ALLOW via fastpath_multistatement_admits().
result=$(run_hook "echo \"checking hook source\"
grep -n \"${DDL}\" ${TARGET} | head -5")
assert_allow "(l) #198: echo statement + admitted grep|head statement (newline-joined) -> allow" "$result"

# --- (m) issue #198: same shape, ';'-joined with a trailing read-only
# statement too, confirming the fix generalizes beyond exactly two statements
result=$(run_hook "echo \"start\"; grep -n \"${DDL}\" ${TARGET} | head -5; echo \"done\"")
assert_allow "(m) #198: 3-statement ';'-joined block over the DDL phrase -> allow" "$result"

# --- (n) issue #198 safety floor: a multi-statement block where the DDL
# phrase appears in a live, non-grep/rg-executed statement must still deny --
# confirms the widened fastpath is scoped to already-admitted per-statement
# shapes, not a general loosening of multi-statement scanning.
result=$(run_hook "echo \"about to migrate\"; psql -c \"${DDL} users\"")
assert_decision "(n) #198 SECURITY: echo + live psql DDL statement -> still deny" "$result" deny "$DDL"

# --- (o) FAIL-SAFE (#127): a BARE (unpiped) grep with an unterminated quote
# is ambiguous pipe-count-wise -- _fastpath_has_unquoted_pipe() must treat that
# the same fail-safe way _fastpath_pipe_split() already does (decline), so this
# still falls through to the full path, which denies on the DDL phrase inside
# the still-open quote
result=$(run_hook "grep -n \"${DDL}\\|foo ${TARGET}")
assert_decision "(o) FAIL-SAFE: unterminated quote declines the fastpath -> deny" \
    "$result" deny "$DDL"

# --- (p)-(t) REGRESSION (#127): fastpath_structural_ok()'s OTHER
# metacharacters (`; & < > `` ` `` $(`) are explicitly OUT OF SCOPE for this
# issue and stay raw byte scans, unchanged -- only `|` became quote-aware.
# Exercised through the echo builtin allowlist entry, whose own documented
# invariant ("structural_ok already ruled out |/>/backtick/$( on this line")
# must still hold for anything that can actually execute.
result=$(run_hook "echo \"\$(${DDL} users)\"")
assert_not_fastpath_allowed "(p) REGRESSION: echo \"\$(...)\" command substitution still declines the fastpath" \
    "$result"

result=$(run_hook 'echo `'"${DDL} users"'`')
assert_not_fastpath_allowed "(q) REGRESSION: backtick command substitution still declines the fastpath" \
    "$result"

result=$(run_hook "echo hi; ${DDL} users")
assert_not_fastpath_allowed "(r) REGRESSION: a; b chaining still declines the fastpath" \
    "$result"

result=$(run_hook "echo hi && ${DDL} users")
assert_not_fastpath_allowed "(s) REGRESSION: a && b chaining still declines the fastpath" \
    "$result"

# NOTE: an end-to-end "(t) a > b redirection" case was deliberately dropped
# here. `echo hi > <repo file>` declines the fastpath exactly like every other
# `>` case (pinned directly at the fastpath_structural_ok() unit level as
# case (44) in PART 1 above), but the FULL path has no generic rule against
# redirecting into an arbitrary repo-relative file -- only specific sinks
# (.ssh/.aws credentials, etc.) are flagged -- so it is itself a silent ALLOW
# downstream of the (correct) fastpath decline. Asserting "not silently
# allowed" end-to-end on that shape would pin unrelated full-path behavior
# this issue does not touch, not the fastpath decline itself.

# --- (u) REGRESSION (#127): a genuinely live (unquoted) pipe on a BARE grep
# line must still decline fastpath_builtin_admits() outright (structural_ok
# still rejects it), even though it is the one case that then gets a SECOND
# chance via fastpath_grep_pipe_admits() -- already exercised end-to-end by
# cases (a)-(e) above (which all ALLOW) and (g) (which correctly DENIES a
# second real pipe). This case pins the single-live-pipe shape once more,
# directly, for the #127 diff.
result=$(run_hook "grep -n \"a\\|b\" ${TARGET} | head -3")
assert_allow "(u) REGRESSION: single real pipe (grep|head) still admits via fastpath_grep_pipe_admits()" \
    "$result"

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
