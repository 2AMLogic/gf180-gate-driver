#!/usr/bin/env bash
# Regression test for .loom/hooks/guard-destructive-generic.sh's
# catastrophic-tier `rm -rf /` (and related) scan false-denying a heredoc
# whose BODY merely quotes the phrase as literal test/sample text (issue #58).
#
# Usage: ./.loom/hooks/tests/test-guard-catastrophic-rm-heredoc.sh
#
# Bug: the catastrophic tier's ALWAYS_BLOCK_PATTERNS loop and its sibling
# extract_rm_targets() scan both read COMMAND_NO_LITERAL_TEXT, but that
# buffer's construction masked only quoted --body/-m/--title/--notes/
# --comment/--search/--arg FLAG VALUES (strip_literal_text()) -- never a
# BARE, top-level heredoc body such as
#     cat > /tmp/test_real_fn.sh << 'EOF'
#     DANGER1="git st""ash po""p"
#     ...deliberately embeds "rm -rf /" as an inert regression-test literal...
#     EOF
# Nothing in that command ever executes `rm`; it is entirely file-write. The
# fix extends the COMMAND_NO_LITERAL_TEXT construction with a heredoc-body
# masking pass that ONLY masks a heredoc whose delimiter is quoted or
# backslash-prefixed (`<<'EOF'`, `<<"EOF"`, `<<\EOF`, `<<-'EOF'` -- the shapes
# bash itself does NOT expand) and whose opener does not feed an interpreter
# (`bash <<EOF`, `sh -s <<EOF`, `cat <<EOF | bash`, ... -- genuinely live code
# to the inner interpreter even though inert to the outer shell). An
# UNQUOTED/expanding delimiter (`<<EOF`, no quotes) is deliberately left
# unmasked: a real `$(...)`/backtick command substitution inside such a body
# executes for real when the outer shell writes it, so it must stay visible
# to the scan.
#
# This suite is split into three parts:
#
#   PART 1 -- direct mask_heredoc_bodies_literal_only() unit tests. The
#   shared _MASKHEREDOC_AWK function library is extracted from the hook file
#   (matching the bash `_MASKHEREDOC_AWK='...'` assignment boundaries) and
#   driven the same way the hook's own call site drives it, isolating the
#   masking primitive itself from the rest of the hook pipeline.
#
#   PART 2 -- end-to-end hook decision tests (ALLOW/DENY) through the real
#   PreToolUse JSON protocol, covering the ALWAYS_BLOCK_PATTERNS catastrophic
#   loop (a bare-root/home rm target).
#
#   PART 3 -- end-to-end hook decision tests exercising the SECOND
#   catastrophic-tier consumer of the same COMMAND_NO_LITERAL_TEXT buffer,
#   extract_rm_targets()'s protected-top-level-directory check (`rm-protected-
#   path` tag), confirming the shared-buffer fix (COMMAND_NO_LITERAL_TEXT
#   built once, read by both scans, #5216) covers it too rather than needing
#   a second, separate patch.
#
# The hook under test is the canonical source at .loom/hooks/ (this repo
# ships no defaults/ tree -- see the file's own banner), copied into an
# isolated temp git tree, exactly like test-strip-literal-text-bsq.sh does
# for its own end-to-end part. Exit 0 = all pass, 1 = fail.

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
# never spells either one out contiguously -- avoids tripping this same
# guard on any future Bash invocation that greps/cats this file.
RMRF_ROOT="rm -r""f /"
RMRF_TMP="rm -r""f /tmp"

# The exact catastrophic-tier bare-root/home pattern (mirrors
# guard-destructive-generic.sh's ALWAYS_BLOCK_PATTERNS entry), used by PART 1
# to check whether masking removed the match.
ROOT_PATTERN='rm[[:space:]]+-[a-zA-Z]*[rf][a-zA-Z]*[[:space:]]+/([^[:alnum:]._~/-]|$)'

# =============================================================================
# PART 1 -- direct mask_heredoc_bodies_literal_only() unit tests
# =============================================================================
echo "=== mask_heredoc_bodies_literal_only() unit tests (#58) ==="

AWKLIB_FILE="$(mktemp)"
trap 'rm -f "$AWKLIB_FILE"' EXIT

START_LINE=$(grep -n "^_MASKHEREDOC_AWK='\$" "$SRC_HOOK" | head -1 | cut -d: -f1)
if [[ -z "$START_LINE" ]]; then
    fail "locate _MASKHEREDOC_AWK assignment in $SRC_HOOK"
else
    REL_END=$(tail -n "+$((START_LINE + 1))" "$SRC_HOOK" | grep -Fxn "'" | head -1 | cut -d: -f1)
    if [[ -z "$REL_END" ]]; then
        fail "locate closing quote of _MASKHEREDOC_AWK assignment in $SRC_HOOK"
    else
        END_LINE=$((START_LINE + REL_END))
        sed -n "${START_LINE},${END_LINE}p" "$SRC_HOOK" > "$AWKLIB_FILE"
        # shellcheck source=/dev/null
        source "$AWKLIB_FILE"

        if [[ -z "${_MASKHEREDOC_AWK:-}" ]]; then
            fail "extracted _MASKHEREDOC_AWK is empty"
        elif ! printf '%s' "$_MASKHEREDOC_AWK" | grep -q "mask_heredoc_bodies_literal_only"; then
            fail "extracted _MASKHEREDOC_AWK does not define mask_heredoc_bodies_literal_only()"
        else
            run_mask() {
                printf '%s' "$1" | awk "$_MASKHEREDOC_AWK"'
                { buf = buf (NR > 1 ? "\n" : "") $0 }
                END { printf "%s", mask_heredoc_bodies_literal_only(buf) }'
            }

            # --- (1) single-quoted delimiter, non-interpreter sink -> masked
            printf -v CMD1 '%s\n%s\n%s' \
                "cat > /tmp/loom-test-a.sh <<'EOF'" \
                "DANGER=\"${RMRF_ROOT}\"" \
                "EOF"
            OUT1=$(run_mask "$CMD1")
            if ! echo "$OUT1" | grep -qE "$ROOT_PATTERN"; then
                pass "(1) single-quoted delimiter <<'EOF' body masked (phrase no longer matches)"
            else
                fail "(1) single-quoted delimiter body NOT masked: $OUT1"
            fi

            # --- (2) double-quoted delimiter, non-interpreter sink -> masked
            printf -v CMD2 '%s\n%s\n%s' \
                'cat > /tmp/loom-test-b.sh <<"EOF"' \
                "DANGER=\"${RMRF_ROOT}\"" \
                "EOF"
            OUT2=$(run_mask "$CMD2")
            if ! echo "$OUT2" | grep -qE "$ROOT_PATTERN"; then
                pass '(2) double-quoted delimiter <<"EOF" body masked'
            else
                fail "(2) double-quoted delimiter body NOT masked: $OUT2"
            fi

            # --- (3) backslash-prefixed delimiter, non-interpreter sink -> masked
            printf -v CMD3 '%s\n%s\n%s' \
                'cat > /tmp/loom-test-c.sh <<\EOF' \
                "DANGER=\"${RMRF_ROOT}\"" \
                "EOF"
            OUT3=$(run_mask "$CMD3")
            if ! echo "$OUT3" | grep -qE "$ROOT_PATTERN"; then
                pass '(3) backslash-prefixed delimiter <<\EOF body masked'
            else
                fail "(3) backslash-prefixed delimiter body NOT masked: $OUT3"
            fi

            # --- (4) `<<-` dash form with a quoted delimiter and a
            # tab-indented closing delimiter line -> masked
            printf -v CMD4 '%s\n%s\n\t%s' \
                "cat > /tmp/loom-test-d.sh <<-'EOF'" \
                "DANGER=\"${RMRF_ROOT}\"" \
                "EOF"
            OUT4=$(run_mask "$CMD4")
            if ! echo "$OUT4" | grep -qE "$ROOT_PATTERN"; then
                pass "(4) <<-'EOF' dash form with tab-indented closer masked"
            else
                fail "(4) <<-'EOF' dash form NOT masked: $OUT4"
            fi

            # --- (5) UNQUOTED delimiter -> NOT masked (must remain fully
            # scanned: a real $(...)/backtick inside such a body genuinely
            # expands when the outer shell writes it)
            printf -v CMD5 '%s\n%s\n%s' \
                "cat > /tmp/loom-test-e.sh <<EOF" \
                "DANGER=\"${RMRF_ROOT}\"" \
                "EOF"
            OUT5=$(run_mask "$CMD5")
            if echo "$OUT5" | grep -qE "$ROOT_PATTERN"; then
                pass "(5) unquoted delimiter <<EOF body left fully visible (not masked)"
            else
                fail "(5) unquoted delimiter body was incorrectly masked: $OUT5"
            fi

            # --- (6) QUOTED delimiter but INTERPRETER-FED opener (`bash
            # <<'EOF' ... EOF`) -> NOT masked: the body is genuinely live
            # code to the inner interpreter even though inert to the outer
            # shell
            printf -v CMD6 '%s\n%s\n%s' \
                "bash <<'EOF'" \
                "${RMRF_ROOT}" \
                "EOF"
            OUT6=$(run_mask "$CMD6")
            if echo "$OUT6" | grep -qE "$ROOT_PATTERN"; then
                pass "(6) interpreter-fed (bash <<'EOF') body left visible (not masked)"
            else
                fail "(6) interpreter-fed body was incorrectly masked: $OUT6"
            fi

            # --- (7) narrowing-only: a REAL (non-heredoc) invocation
            # elsewhere in the SAME multi-line command stays visible even
            # though an unrelated inert heredoc in the same buffer is masked
            printf -v CMD7 '%s\n%s\n%s\n%s' \
                "cat > /tmp/loom-test-f.sh <<'EOF'" \
                "DANGER=\"${RMRF_ROOT}\"" \
                "EOF" \
                "${RMRF_ROOT}"
            OUT7=$(run_mask "$CMD7")
            if echo "$OUT7" | grep -qE "$ROOT_PATTERN"; then
                pass "(7) narrowing-only: real invocation outside the heredoc stays visible"
            else
                fail "(7) narrowing-only regression: real invocation outside heredoc was masked: $OUT7"
            fi

            # --- (8) baseline: no heredoc at all -> passthrough unchanged
            CMD8="${RMRF_ROOT}"
            OUT8=$(run_mask "$CMD8")
            if [[ "$OUT8" == "$CMD8" ]]; then
                pass "(8) baseline: no heredoc present -> buffer unchanged"
            else
                fail "(8) baseline regressed: expected [$CMD8], got [$OUT8]"
            fi
        fi
    fi
fi

# =============================================================================
# PART 2 + 3 -- end-to-end hook decision tests (ALLOW/DENY)
# =============================================================================
echo
echo "=== guard-destructive-generic.sh end-to-end ALLOW/DENY tests (#58) ==="

TMPROOT="$(mktemp -d)"
trap 'rm -f "$AWKLIB_FILE"; rm -rf "$TMPROOT"' EXIT
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

# --- (a) the exact reported repro: bare quoted-delimiter heredoc writing a
# test fixture whose body quotes the phrase as inert sample text -> ALLOW
# (was DENY before the fix)
printf -v CMD_A '%s\n%s\n%s' \
    "cat > /tmp/loom_test_real_fn.sh <<'EOF'" \
    "DANGER1=\"${RMRF_ROOT}\"" \
    "EOF"
result=$(run_hook "$CMD_A")
assert_allow "(a) bare quoted-delimiter heredoc test fixture quoting the phrase -> allow" "$result"

# --- (b) same, via the <<- dash form -> ALLOW
printf -v CMD_B '%s\n%s\n\t%s' \
    "cat > /tmp/loom_test_real_fn2.sh <<-'EOF'" \
    "DANGER1=\"${RMRF_ROOT}\"" \
    "EOF"
result=$(run_hook "$CMD_B")
assert_allow "(b) <<-'EOF' dash-form heredoc test fixture quoting the phrase -> allow" "$result"

# --- (c) interpreter-fed heredoc (`bash <<'EOF' ... EOF`) -> still DENY: the
# body is genuinely live code to the inner interpreter
printf -v CMD_C '%s\n%s\n%s' \
    "bash <<'EOF'" \
    "${RMRF_ROOT}" \
    "EOF"
result=$(run_hook "$CMD_C")
assert_deny "(c) interpreter-fed heredoc (bash <<'EOF') with real invocation -> still deny" "$result" \
    "dangerous pattern"

# --- (d) UNQUOTED delimiter heredoc whose body contains the phrase -> still
# DENY: an unquoted delimiter means the outer shell would genuinely expand
# any $(...) /backtick in the body, so it must stay fully scanned
printf -v CMD_D '%s\n%s\n%s' \
    "cat > /tmp/loom_test_real_fn3.sh <<EOF" \
    "${RMRF_ROOT}" \
    "EOF"
result=$(run_hook "$CMD_D")
assert_deny "(d) unquoted-delimiter heredoc body with real phrase -> still deny" "$result" \
    "dangerous pattern"

# --- (e) real, bare (non-heredoc) invocation -> still DENY (unaffected)
result=$(run_hook "$RMRF_ROOT")
assert_deny "(e) real bare invocation, no heredoc -> still deny (unaffected)" "$result" \
    "dangerous pattern"

# --- (f) real, sudo-prefixed invocation -> still DENY (unaffected)
result=$(run_hook "sudo $RMRF_ROOT")
assert_deny "(f) real sudo-prefixed invocation -> still deny (unaffected)" "$result" \
    "dangerous pattern"

# --- (g) extract_rm_targets() path (#5216 shape, unquoted-on-its-own-line
# separator): a bare quoted-delimiter heredoc test-fixture body line quotes a
# PROTECTED-TOP-LEVEL-DIRECTORY example as inert prose, using a real (from
# THAT physical line's perspective) unquoted `;` -- exactly the shape that
# makes qsplit's line-by-line, no-cross-line-memory segmentation
# (extract_rm_targets()'s own documented limitation, :4363-4372) misread
# heredoc prose as a live shell segment when unmasked. Targets a
# non-root top-level dir ("/tmp") deliberately -- the ALWAYS_BLOCK_PATTERNS
# bare-root/home regex used in (a)-(f) above does NOT match a non-root
# top-level path, so this isolates the SECOND catastrophic-tier consumer.
# -> ALLOW, confirming the shared COMMAND_NO_LITERAL_TEXT fix covers
# extract_rm_targets() too, not just the ALWAYS_BLOCK_PATTERNS loop.
printf -v CMD_G '%s\n%s\n%s' \
    "cat > /tmp/loom_test_real_fn4.sh <<'EOF'" \
    "See the anti-pattern: owner/repo; ${RMRF_TMP}" \
    "EOF"
result=$(run_hook "$CMD_G")
assert_allow "(g) extract_rm_targets(): quoted-delimiter heredoc quoting a protected-path phrase after an unquoted ';' -> allow" "$result"

# --- (h) the SAME shape as a REAL (non-heredoc) invocation -> still DENY via
# extract_rm_targets()'s rm-protected-path check (unaffected): a genuine `;`
# separator ahead of a real `rm -rf /tmp` segment must still be caught.
result=$(run_hook "owner/repo; ${RMRF_TMP}")
assert_deny "(h) real ';'-separated protected-top-level-dir rm, no heredoc -> still deny (unaffected)" "$result" \
    "protected system path"

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
