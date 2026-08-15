#!/usr/bin/env bash
# Regression test for .loom/hooks/guard-destructive-generic.sh's
# worktree-write-confinement heredoc masking (issue #68).
#
# Bug: extract_write_targets() masked heredoc bodies with
# mask_heredoc_bodies_selective(), which leaves the body VISIBLE whenever the
# opener line feeds ANY recognized interpreter (#5351). That carve-out exists
# so a real redirection inside `bash <<'EOF' ... > <main>/f ... EOF` still
# reaches the confinement check -- reasoning that only holds for a SHELL inner
# interpreter. For `python3 <<'EOF' ... EOF` no layer ever parses the body as
# shell (the outer shell never scans a heredoc body for operators, and Python
# does not speak shell), so ordinary Python source was tokenized as shell
# redirection:
#
#     if len(methods) >= 10:      ->  redirection into a file named `=`
#     if x > 3:                   ->  redirection into a file named `3`
#
# resolved against the main checkout and DENIED as a worktree-isolation
# bypass, for a script that only reads files and prints findings.
#
# Fix: extract_write_targets() now calls
# mask_heredoc_bodies_selective_shell_only(), which masks a body fed to a
# NON-shell interpreter (python/perl/ruby/node) through an explicitly QUOTED
# delimiter, and leaves everything else exactly as visible as before.
#
# This suite covers, in both directions:
#   FALSE POSITIVES THAT MUST NOW ALLOW
#     - the exact `>=` repro from issue #68
#     - the same class with a bare `>` comparison (not fixed by narrowing the
#       `>=` token alone -- this is why the fix is at the masking layer)
#     - a non-Python non-shell interpreter (`node`)
#     - the piped spelling (`cat <<'EOF' | python3`)
#   GENUINE POSITIVES THAT MUST STILL DENY (the #5351 property)
#     - `bash <<'EOF'` / `cat <<'EOF' | bash` / `sudo bash <<'EOF'` bodies
#       that really do write into the main checkout
#     - `$SHELL <<'EOF'` -- an unresolvable command word, fail-closed (#5226)
#     - `python3 <<EOF` with a BARE delimiter (the outer shell still expands
#       inside that body, so it is not provably inert)
#     - a real write in the SAME command but OUTSIDE the masked body
#     - `cat > <main>/f <<'EOF'`: the redirection is on the OPENER line, which
#       is never masked
#   NO REGRESSION ON THE INERT-SINK FIXES (#5000/#5181)
#     - `cat <<'EOF' ... EOF` body carrying write-idiom prose -> allow
#
# The hook under test is the canonical source at .loom/hooks/ (this repo ships
# no defaults/ tree -- see test-guard-destructive-worktree-confinement.sh for
# the same note), copied into an isolated temp git tree alongside its
# config-resolver.sh/canonical-path.sh lib dependencies so MAIN_ROOT /
# git-common-dir resolve inside the temp tree. Exit 0 = all pass, 1 = fail.

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

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); printf "${GREEN}PASS${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "${RED}FAIL${NC} %s\n" "$1"; }

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

echo "=== guard-destructive-generic.sh heredoc interpreter masking tests (#68) ==="

# --- Fixture: one managed worktree at $TMPROOT/.loom/worktrees/issue-6 -----
# Its mere existence is what arms the worktree-write-confinement check.
WT="$TMPROOT/.loom/worktrees/issue-6"
mkdir -p "$WT/sim"
cat >"$WT/.loom-managed" <<'EOF'
# Loom-managed worktree marker
EOF
CONFINED="resolves to the main repository checkout"

# --- (a) the exact reproduction from issue #68: a read-only Python script fed
# through a QUOTED-delimiter heredoc, containing a `>=` comparison. Before the
# fix this denied with a write target of literally "<main-checkout>/=".
result=$(run_hook "python3 - <<'PYEOF'
import ast, pathlib

files = list(pathlib.Path(\"sim\").rglob(\"*.py\"))
for f in files:
    tree = ast.parse(f.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
            if len(methods) == 0:
                continue
            if len(methods) >= 10:
                continue
PYEOF")
assert_allow "(a) issue-#68 repro: python3 <<'EOF' body with '>=' comparison -> allow" "$result"

# --- (b) same class, bare `>` comparison. Deliberately separate from (a):
# narrowing only the `>=` token would leave this one denying (target "3"), so
# this case is what forces the fix to live in the heredoc-masking layer.
result=$(run_hook "python3 - <<'PYEOF'
x = 5
if x > 3:
    print(\"big\")
PYEOF")
assert_allow "(b) python3 <<'EOF' body with bare '>' comparison -> allow" "$result"

# --- (c) the carve-out is per INTERPRETER FAMILY, not python-specific.
result=$(run_hook "node <<'JSEOF'
if (a >= b) { console.log(1); }
JSEOF")
assert_allow "(c) node <<'EOF' body with '>=' comparison -> allow" "$result"

# --- (d) piped spelling: the interpreter is not the opener command word.
result=$(run_hook "cat <<'PYEOF' | python3
if a >= b:
    pass
PYEOF")
assert_allow "(d) cat <<'EOF' | python3, body with '>=' -> allow" "$result"

# --- (e) THE #5351 PROPERTY: a SHELL-fed body really is live code, so a
# redirection into the main checkout inside it must still DENY.
result=$(run_hook "bash <<'SHEOF'
echo pwned > $TMPROOT/evil.sh
SHEOF")
assert_deny "(e) bash <<'EOF' body writing into the main checkout -> still deny" "$result" "$CONFINED"

# --- (f) same, piped spelling.
result=$(run_hook "cat <<'SHEOF' | bash
echo pwned > $TMPROOT/evil.sh
SHEOF")
assert_deny "(f) cat <<'EOF' | bash body writing into the main checkout -> still deny" "$result" "$CONFINED"

# --- (g) same, behind a wrapper command (the #5205/#5226 normalization).
result=$(run_hook "sudo bash <<'SHEOF'
cp /tmp/a $TMPROOT/evil.sh
SHEOF")
assert_deny "(g) sudo bash <<'EOF' body cp-ing into the main checkout -> still deny" "$result" "$CONFINED"

# --- (h) FAIL-CLOSED TAIL (#5226): an unresolvable command word could be a
# shell, so its body must stay visible under the shell-only rule too.
result=$(run_hook "\$SHELL <<'SHEOF'
echo pwned > $TMPROOT/evil.sh
SHEOF")
assert_deny "(h) \$SHELL <<'EOF' (unresolvable command word) body writing into main -> still deny" "$result" "$CONFINED"

# --- (i) BARE delimiter: the outer shell still performs expansion inside the
# body, so it is not provably inert prose and must stay visible.
result=$(run_hook "python3 <<PYEOF
x = 1
echo pwned > $TMPROOT/evil.sh
PYEOF")
assert_deny "(i) python3 <<EOF (BARE delimiter) body writing into main -> still deny" "$result" "$CONFINED"

# --- (j) masking is confined to the BODY: a real write later in the same
# command must still be found.
result=$(run_hook "python3 - <<'PYEOF'
if x >= 3:
    pass
PYEOF
echo done > $TMPROOT/evil.sh")
assert_deny "(j) masked python3 body + real write AFTER the block -> still deny" "$result" "$CONFINED"

# --- (k) the OPENER line is never masked: `cat > <main>/f <<'EOF'` writes.
result=$(run_hook "cat > $TMPROOT/evil.sh <<'SHEOF'
hello
SHEOF")
assert_deny "(k) redirection on the heredoc OPENER line -> still deny" "$result" "$CONFINED"

# --- (l) NO REGRESSION on the inert-sink fixes (#5000/#5181): a `cat`-fed
# quoted heredoc carrying write-idiom PROSE stays masked -> allow.
result=$(run_hook "cat <<'SHEOF'
echo pwned > $TMPROOT/evil.sh
SHEOF")
assert_allow "(l) inert cat <<'EOF' sink body quoting a write idiom -> allow (no #5000/#5181 regression)" "$result"

# --- (m) a masked python3 body alongside a write that is legitimately OUTSIDE
# the protected checkout must still allow -- the fix must not turn the scan off.
result=$(run_hook "python3 - <<'PYEOF'
if x >= 3:
    pass
PYEOF
echo done > /tmp/loom-issue-68-scratch.txt")
assert_allow "(m) masked python3 body + /tmp scratch write -> allow" "$result"

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
