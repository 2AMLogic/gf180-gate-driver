#!/usr/bin/env bash
# Regression test for .loom/hooks/guard-destructive-generic.sh's
# extract_write_targets() sed branch mis-parsing BSD/macOS `sed -i ''`
# (issue #106).
#
# Bug: BSD/macOS sed requires a SEPARATE, possibly-empty backup-extension
# argument immediately after a bare `-i` token -- `sed -i '' <script>
# <file>` -- unlike GNU sed, where `-i` either has no separate argument at
# all or the extension is ATTACHED (`-i.bak`). extract_write_targets()'s sed
# branch tried to recognize that separate empty-string argument with
# `toks[j] == ""`, but qsplit()/mask_ws() preserve quote characters
# VERBATIM in every token (#3755/#4934) -- so the BSD form's `''` argument
# never arrives as awk's true empty string, it arrives as the literal
# TWO-CHARACTER token `''` (or `""`). The `toks[j] == ""` check could never
# match it, so that token fell through into nfargs[] as if it were a real
# file operand, shifting every later index by one. The result: the SED
# SCRIPT text (e.g. `s/foo/bar/`) printed as the write "target" instead of
# the real file argument -- producing a fabricated confinement-check target
# built from `<cwd><sed-script-text>` rather than the actual file. That
# fabricated target denied every BSD `sed -i ''` invocation unconditionally,
# regardless of the real target's location (main checkout OR a legitimate
# worktree/tmp write) -- the only correct in-place-edit spelling on macOS.
#
# This suite covers:
#   - a genuine main-checkout `sed -i ''` write -> still DENY, but for the
#     RIGHT reason: the reported target must be the real file argument
#     (README.md), never the sed script text (`s/foo/bar` or similar)
#   - a `/tmp`-confined `sed -i ''` write -> ALLOW (was unconditionally
#     denied before the fix)
#   - the double-quote spelling of the same BSD idiom, `sed -i "" ...`,
#     confined to /tmp -> ALLOW
#   - the GNU attached form `sed -i.bak ...` (baseline -- must not regress):
#     /tmp -> ALLOW, main checkout -> DENY
#   - the GNU bare form `sed -i ...` with NO separate argument (baseline --
#     must not regress): main checkout -> DENY with the real file as target
#   - MULTIPLE trailing file operands after the BSD empty-extension argument:
#     every one of them must still be scanned (all-/tmp -> ALLOW; a
#     main-checkout file in the LAST position -> DENY naming that file)
#   - `sed -i '' -e <script> <file>`: an intervening `-e` flag must not
#     disturb the operand indexing
#   - the AMBIGUOUS two-operand shape `sed -i '' <file>`, which reads as an
#     empty SCRIPT + a real in-place FILE write under GNU sed and as a
#     backup extension + a script with no file under BSD sed. The fix must
#     NOT drop the empty-quote token here: doing so would turn a genuine
#     main-checkout write into an ALLOW, relaxing the #4178 confinement
#     floor rather than just correcting the parse. It must stay DENY, with
#     the real file as the reported target (its pre-#106 behavior).
#
# The hook under test is the canonical source at .loom/hooks/ (this repo
# ships no defaults/ tree and no .claude/skills/repo/hooks/ canonical Repo
# Skills guard -- see the file's own banner -- so this vendored copy is the
# only thing enforcing worktree-write-confinement here), copied into an
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

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT
git init -q "$TMPROOT"
mkdir -p "$TMPROOT/.loom/hooks" "$TMPROOT/.loom/scripts/lib"
cp "$SRC_HOOK" "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
chmod +x "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
cp "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" "$TMPROOT/.loom/scripts/lib/config-resolver.sh"
cp "$REPO_ROOT/.loom/scripts/lib/canonical-path.sh" "$TMPROOT/.loom/scripts/lib/canonical-path.sh"
HOOK="$TMPROOT/.loom/hooks/guard-destructive-generic.sh"

# A real file in the synthetic main checkout, so a "denied for the real
# reason" assertion has something concrete to point at.
echo "hello" >"$TMPROOT/README.md"

# A fixture Loom-managed worktree elsewhere in the repo -- the
# worktree-write-confinement check only flags a main-checkout write when a
# managed worktree exists elsewhere to redirect to (mirrors the fixture in
# test-guard-destructive-worktree-confinement.sh).
mkdir -p "$TMPROOT/.loom/worktrees/issue-6"
cat >"$TMPROOT/.loom/worktrees/issue-6/.loom-managed" <<'EOF'
# Loom-managed worktree marker
EOF

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); printf "${GREEN}PASS${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "${RED}FAIL${NC} %s\n" "$1"; }

# Build stdin JSON for a Bash tool_input, with cwd fixed at TMPROOT (the
# synthetic main checkout).
make_input() {
    local command="$1"
    jq -n --arg cmd "$command" --arg cwd "$TMPROOT" \
        '{tool_input: {command: $cmd}, cwd: $cwd}'
}

# Run the hook from inside the temp tree so git-common-dir resolves
# _WT_MAIN_ROOT to it. Prints "<exit_code>|<stdout>".
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

# assert_deny additionally checks the reason text carries the given
# substring(s), so an ALLOW-vs-DENY flip, OR a deny for the WRONG (fabricated)
# target, still fails loudly.
assert_deny() {
    local desc="$1" result="$2" reason_substr="${3:-}" forbidden_substr="${4:-}"
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
    if [[ -n "$forbidden_substr" && "$reason" == *"$forbidden_substr"* ]]; then
        fail "$desc (deny reason contains the FABRICATED target '$forbidden_substr': $reason)"
        return
    fi
    pass "$desc"
}

echo "=== guard-destructive-generic.sh BSD sed -i '' target-parsing tests (#106) ==="

# --- (a) genuine main-checkout BSD `sed -i ''` write -> still DENY, but the
# reported target must be the REAL file (README.md), never the sed script
# text (the pre-fix fabricated target).
result=$(run_hook "sed -i '' 's/foo/bar/' README.md")
assert_deny "(a) main-checkout sed -i '' README.md -> deny, real target reported" "$result" \
    "$TMPROOT/README.md" "$TMPROOT/s/foo/bar"

# --- (b) /tmp-confined BSD `sed -i ''` write -> ALLOW (was unconditionally
# denied before the fix, regardless of the real target's location).
result=$(run_hook "sed -i '' 's/foo/bar/' /tmp/loom-issue106-test.md")
assert_allow "(b) /tmp-confined sed -i '' write -> allow" "$result"

# --- (c) double-quote spelling of the same BSD idiom, confined to /tmp ->
# ALLOW.
result=$(run_hook 'sed -i "" '"'"'s/foo/bar/'"'"' /tmp/loom-issue106-test.md')
assert_allow "(c) /tmp-confined sed -i \"\" write (double-quote empty arg) -> allow" "$result"

# --- (d) GNU attached form `sed -i.bak ...` -- baseline, must not regress.
result=$(run_hook "sed -i.bak 's/foo/bar/' /tmp/loom-issue106-test.md")
assert_allow "(d1) /tmp-confined GNU sed -i.bak write -> allow (baseline)" "$result"

result=$(run_hook "sed -i.bak 's/foo/bar/' README.md")
assert_deny "(d2) main-checkout GNU sed -i.bak README.md -> deny, real target reported (baseline)" "$result" \
    "$TMPROOT/README.md"

# --- (e) GNU bare form `sed -i ...` with NO separate argument -- baseline,
# must not regress: the very next token IS the real file, not a BSD
# backup-extension argument, so it must still be read as the write target.
result=$(run_hook "sed -i 's/foo/bar/' README.md")
assert_deny "(e) main-checkout bare GNU sed -i README.md -> deny, real target reported (baseline)" "$result" \
    "$TMPROOT/README.md" "$TMPROOT/s/foo/bar"

# --- (f) MULTIPLE trailing file operands after the BSD empty-extension
# argument. sed accepts any number of files; every one must still be scanned
# after the extension token is dropped, so the index correction must not stop
# at the first file.
result=$(run_hook "sed -i '' 's/foo/bar/' /tmp/loom-issue106-a.md /tmp/loom-issue106-b.md")
assert_allow "(f1) two /tmp file operands after sed -i '' -> allow" "$result"

# The main-checkout file sits LAST here, so this only denies if operands
# beyond the first are scanned too.
result=$(run_hook "sed -i '' 's/foo/bar/' /tmp/loom-issue106-a.md README.md")
assert_deny "(f2) sed -i '' with main-checkout file in the LAST operand -> deny, that file reported" "$result" \
    "$TMPROOT/README.md" "$TMPROOT/s/foo/bar"

# --- (g) an intervening `-e` flag between the empty-extension argument and
# the script must not disturb the operand indexing.
result=$(run_hook "sed -i '' -e 's/foo/bar/' README.md")
assert_deny "(g) sed -i '' -e <script> README.md -> deny, real target reported" "$result" \
    "$TMPROOT/README.md" "$TMPROOT/s/foo/bar"

# --- (h) AMBIGUOUS two-operand shape: `sed -i '' <file>`. Under GNU sed the
# `''` is the (empty) SCRIPT and README.md is a real in-place write; under BSD
# sed it is the backup extension and README.md is the script (no file at all).
# The guard must fail CLOSED on that ambiguity and keep denying with the real
# file as the target -- dropping the empty-quote token unconditionally would
# flip this to ALLOW and punch a hole in the #4178 confinement floor.
result=$(run_hook "sed -i '' README.md")
assert_deny "(h) ambiguous two-operand sed -i '' README.md -> still deny (fail closed), real target reported" "$result" \
    "$TMPROOT/README.md"

# --- (i) no `-i` at all: sed is a read-only filter here, so nothing may be
# reported as a write target even though a main-checkout file is named.
result=$(run_hook "sed -n 's/foo/bar/p' README.md")
assert_allow "(i) sed with no -i (read-only filter) -> allow (baseline)" "$result"

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
