#!/usr/bin/env bash
# Regression test for .loom/hooks/guard-destructive-generic.sh's
# worktree-write-confinement* deny category (issue #17).
#
# Usage: ./.loom/hooks/tests/test-guard-destructive-worktree-confinement.sh
#
# Bug: resolve_var() (inside extract_write_targets(), #4881's same-command
# variable resolution) only resolved an UNQUOTED `$VAR/path` write target
# back to a same-command `VAR="..."` assignment. A QUOTED write target
# (`"$VAR/path"`) reaches resolve_var() with its surrounding quote
# characters attached (qsplit's contract), so `substr(tok, 1, 1) != "$"`
# was true on the leading `"` and the function returned the token
# unresolved on its very first line -- even when VAR was assigned an
# unambiguous, in-worktree literal earlier in the SAME command. That made
# the guard deny the recommended, shellcheck-clean
#   WORKTREE_ABS="<worktree>"
#   cp f "$WORKTREE_ABS/design/x.sch"
# idiom as an "unresolved variable" worktree-isolation bypass, even though
# every write target was provably confined.
#
# This suite covers:
#   - the exact minimal repro (quoted $VAR write, same-command literal
#     assignment, target confined to the worktree) -> ALLOW
#   - the full multi-line repro from the guard-decisions.log entry cited in
#     issue #17 -> ALLOW
#   - the pre-existing UNQUOTED form (baseline -- must not regress) -> ALLOW
#   - a quoted $VAR write that resolves INSIDE the main checkout -> still
#     DENY (worktree-write-confinement) -- the fix must not blanket-trust
#     every quoted variable
#   - a quoted $VAR with NO matching same-command assignment (genuinely
#     unresolvable) -> still DENY (worktree-write-confinement-unresolved-var)
#   - a quoted $VAR reassigned to two DIFFERENT values in the same command
#     (the #4914 AMBIG-sentinel case) -> still DENY, quoted exactly as
#     unquoted already did
#   - a SINGLE-quoted '$VAR/path' write target -> still DENY unresolved; a
#     real shell never expands $VAR inside single quotes, so this fix must
#     NOT start treating single-quoted tokens as variable references (that
#     would be a genuine confinement bypass, not a false-positive fix)
#
# Issue #144 (same-command `mktemp -d` sandbox) extends the same suite: a
# guard self-test script that mints its own throwaway tree
# (`TMPROOT="$(mktemp -d)"`) and writes only inside it was denied at the
# catastrophic -unresolved-var tier seven times in this repo's guard telemetry
# (2026-08-15..17), because record_assign() stored the value TRUNCATED at the
# space inside the substitution. Cases (h)-(t) below cover the flip to ALLOW
# and, more importantly, every neighbouring shape that must keep denying:
# `mktemp` without -d, a repo-relative template, an explicit `-p` parent,
# `-u`, a reassigned/ambiguous binding, a concatenated value, a bare
# `$(mktemp -d)` target, and a TMPDIR pointing inside the checkout.
#
# The hook under test is the canonical source at .loom/hooks/ (this repo
# ships no defaults/ tree and no .claude/skills/repo/hooks/ canonical Repo
# Skills guard -- see the file's own banner -- so this vendored copy is the
# only thing enforcing worktree-write-confinement here), copied into an
# isolated temp git tree alongside its config-resolver.sh/canonical-path.sh
# lib dependencies so MAIN_ROOT/git-common-dir resolve inside the temp tree,
# exactly like test-guard-worktree-paths.sh already does for the sibling
# Edit/Write guard. Exit 0 = all pass, 1 = fail.

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

# Same, with an explicit TMPDIR in the hook's environment — the parent
# directory a bare `mktemp -d` would use, and therefore the parent of the
# stand-in the #144 exception resolves such a binding to.
run_hook_tmpdir() {
    local tmpdir="$1" command="$2"
    local exit_code=0 output
    output=$(cd "$TMPROOT" && TMPDIR="$tmpdir" bash "$HOOK" < <(make_input "$command") 2>/dev/null) || exit_code=$?
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
# substring, so an ALLOW-vs-DENY flip on the wrong deny TAG (e.g.
# worktree-write-confinement vs. -unresolved-var) still fails loudly.
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

echo "=== guard-destructive-generic.sh worktree-write-confinement tests (#17) ==="

# --- Fixture: one managed worktree at $TMPROOT/.loom/worktrees/issue-6 -----
WT="$TMPROOT/.loom/worktrees/issue-6"
mkdir -p "$WT/design/netlist" "$WT/sim"
cat >"$WT/.loom-managed" <<'EOF'
# Loom-managed worktree marker
EOF

# --- (a) minimal repro: quoted $VAR write, same-command literal assignment,
# target confined to the worktree -> ALLOW (was the reported false positive)
result=$(run_hook "WORKTREE_ABS=\"$WT\"
cp /tmp/x.sch \"\$WORKTREE_ABS/design/x.sch\"")
assert_allow "(a) quoted \"\$WORKTREE_ABS/...\" write, confined to worktree -> allow" "$result"

# --- (b) full multi-line repro from the guard-decisions.log entry cited in
# issue #17 -> ALLOW
result=$(run_hook "WORKTREE_ABS=\"$WT\"
source \"\$WORKTREE_ABS/sim/env.sh\"
mkdir -p \"\$WORKTREE_ABS/design/netlist\"
cp /tmp/xschem_test/labtest.sch \"\$WORKTREE_ABS/design/labtest_scratch.sch\"
cd \"\$WORKTREE_ABS/design\"
find \"\$WORKTREE_ABS/design/netlist\" -iname \"*labtest*\"")
assert_allow "(b) full multi-line issue-#17 repro -> allow" "$result"

# --- (c) baseline: pre-existing UNQUOTED form must not regress -> ALLOW
result=$(run_hook "WORKTREE_ABS=\"$WT\"
cp /tmp/x.sch \$WORKTREE_ABS/design/x.sch")
assert_allow "(c) unquoted \$WORKTREE_ABS/... write, confined -> allow (baseline, no regression)" "$result"

# --- (d) quoted $VAR write that resolves INSIDE the main checkout -> still
# DENY (worktree-write-confinement, the ordinary confined-resolution tag,
# NOT -unresolved-var -- the token DID resolve, it just resolves somewhere
# this guard protects).
result=$(run_hook "WORKTREE_ABS=\"$TMPROOT\"
cp /tmp/f.txt \"\$WORKTREE_ABS/evil.txt\"")
assert_deny "(d) quoted \$VAR resolving into the main checkout -> still deny" "$result" \
    "resolves to the main repository checkout"

# --- (e) quoted $VAR with NO matching same-command assignment -> still DENY
# (worktree-write-confinement-unresolved-var) -- genuinely unresolvable
# targets must stay fail-closed.
result=$(run_hook 'cp /tmp/f.txt "$NEVER_ASSIGNED/evil.txt"')
assert_deny "(e) quoted \$VAR with no same-command assignment -> still deny (unresolved)" "$result" \
    "unexpanded shell variable"

# --- (f) quoted $VAR reassigned to two DIFFERENT values in the same command
# (the #4914 AMBIG-sentinel case) -> still DENY, quoted exactly as unquoted
# already did.
result=$(run_hook "WORKTREE_ABS=\"$WT\" || WORKTREE_ABS=\"/tmp/outside\"
cp /tmp/f.txt \"\$WORKTREE_ABS/evil.txt\"")
assert_deny "(f) quoted \$VAR, conflicting same-command assignment (AMBIG) -> still deny" "$result" \
    "unexpanded shell variable"

# --- (g) SINGLE-quoted '$VAR/path' write target -> still DENY unresolved.
# A real shell never expands $VAR inside single quotes, so this must NOT be
# treated as a resolved variable reference even when VAR is assigned the
# in-worktree literal earlier in the same command -- doing so would be a
# genuine confinement bypass (a single-quoted token whose LITERAL first path
# component is unknown-looking must still fail closed), not the false
# positive this issue fixes.
result=$(run_hook "WORKTREE_ABS=\"$WT\"
cp /tmp/f.txt '\$WORKTREE_ABS/evil.txt'")
assert_deny "(g) single-quoted '\$VAR/...' write target -> still deny (never expands in real shell)" "$result"

echo "--- same-command 'mktemp -d' sandbox bindings (#144) ---"

# --- (h) the reported false positive: a guard self-test script mints its own
# throwaway tree with `mktemp -d` and copies into it -> ALLOW. Before the fix
# the assignment scan truncated the value at the space inside the command
# substitution (`TMPROOT="$(mktemp`), resolve_var() substituted that fragment,
# and the phantom target denied at the catastrophic
# worktree-write-confinement-unresolved-var tier.
result=$(run_hook 'TMPROOT="$(mktemp -d)"
cp /etc/hosts "$TMPROOT/hosts"')
assert_allow "(h) quoted \$(mktemp -d) sandbox, cp into it -> allow" "$result"

# --- (i) unquoted assignment + `>` redirection, same shape -> ALLOW
result=$(run_hook 'TMPROOT=$(mktemp -d)
echo hi > "$TMPROOT/x"')
assert_allow "(i) unquoted \$(mktemp -d) sandbox, > redirect into it -> allow" "$result"

# --- (j) backtick spelling -> ALLOW
result=$(run_hook 'TMPROOT=`mktemp -d`
cp /etc/hosts "$TMPROOT/hosts"')
assert_allow "(j) backticked \`mktemp -d\` sandbox -> allow" "$result"

# --- (k) the telemetry's own shape: a subdirectory of the sandbox is named in
# a second variable before being written to -> ALLOW (chain rooted at the
# sandbox is followed one step per assignment, in stream order).
result=$(run_hook 'TMPROOT="$(mktemp -d)"
WT="$TMPROOT/.loom/worktrees/issue-99"
cp /etc/hosts "$WT/f"')
assert_allow "(k) chained \$WT under a \$(mktemp -d) sandbox -> allow" "$result"

# --- (l) NEGATIVE: `mktemp` with no -d creates a FILE, not a sandbox
# directory -> still DENY unresolved.
result=$(run_hook 'F=$(mktemp)
cp /etc/hosts "$F/hosts"')
assert_deny "(l) \$(mktemp) without -d (file, not directory) -> still deny (unresolved)" "$result" \
    "unexpanded shell variable"

# --- (m) NEGATIVE: a repo-relative template really can land inside the
# checkout -> still DENY unresolved.
result=$(run_hook 'TMPROOT=$(mktemp -d ./scratch.XXXX)
cp /etc/hosts "$TMPROOT/hosts"')
assert_deny "(m) mktemp -d with a repo-relative template -> still deny (unresolved)" "$result" \
    "unexpanded shell variable"

# --- (n) NEGATIVE: a RELATIVE explicit parent is joined against a cwd this
# scan is not tracking for the substituted command -> still DENY unresolved.
result=$(run_hook 'TMPROOT=$(mktemp -d -p .)
cp /etc/hosts "$TMPROOT/hosts"')
assert_deny "(n) mktemp -d -p . (relative parent) -> still deny (unresolved)" "$result" \
    "unexpanded shell variable"

# --- (n2) an ABSOLUTE template names its own parent, so it is resolvable the
# same way the default one is -> ALLOW. This is the exact shape of one of the
# telemetry hits (`mktemp -d /tmp/gc94-XXXX`).
result=$(run_hook 'SCRATCH=$(mktemp -d /tmp/gc94-XXXX)
cp /etc/hosts "$SCRATCH/f"')
assert_allow "(n2) mktemp -d with an absolute out-of-repo template -> allow" "$result"

# --- (n3) ditto for an absolute `-p` parent.
result=$(run_hook 'SCRATCH=$(mktemp -d -p /var/tmp)
cp /etc/hosts "$SCRATCH/f"')
assert_allow "(n3) mktemp -d -p /var/tmp (absolute out-of-repo parent) -> allow" "$result"

# --- (n4) NEGATIVE, the mirror of (t): an absolute template INSIDE the main
# checkout is judged as the literal path it is -> DENY, and with the ordinary
# confinement tag rather than the unresolved one.
result=$(run_hook "SCRATCH=\$(mktemp -d $TMPROOT/gc-XXXX)
cp /etc/hosts \"\$SCRATCH/f\"")
assert_deny "(n4) mktemp -d with a template inside the main checkout -> deny" "$result" \
    "resolves to the main repository checkout"

# --- (n5) NEGATIVE: a template carrying an unexpanded \$ is exactly the kind
# of unknown this guard fails closed on -> still DENY unresolved.
result=$(run_hook 'SCRATCH=$(mktemp -d "$BASE/gc-XXXX")
cp /etc/hosts "$SCRATCH/f"')
assert_deny "(n5) mktemp -d with a \$-carrying template -> still deny (unresolved)" "$result" \
    "unexpanded shell variable"

# --- (o) NEGATIVE: -u only PRINTS a name, creating nothing -> still DENY.
result=$(run_hook 'TMPROOT=$(mktemp -u -d)
cp /etc/hosts "$TMPROOT/hosts"')
assert_deny "(o) mktemp -u -d (dry run, nothing created) -> still deny (unresolved)" "$result" \
    "unexpanded shell variable"

# --- (p) NEGATIVE: the sandbox binding is reassigned to the main checkout in
# a LATER segment -> the AMBIG sentinel must still poison it.
result=$(run_hook "TMPROOT=\"\$(mktemp -d)\"
TMPROOT=\"$TMPROOT\"
cp /etc/hosts \"\$TMPROOT/evil\"")
assert_deny "(p) sandbox var reassigned to the main checkout -> still deny (AMBIG)" "$result" \
    "unexpanded shell variable"

# --- (q) NEGATIVE: the `||` fallback shape, which qsplit() does not segment
# after a QUOTED command substitution, so the second binding is invisible to
# the assignment scan -> the exception must refuse the whole recognition
# rather than trust the first branch.
result=$(run_hook 'TMPROOT="$(mktemp -d)" || TMPROOT=/some/other
cp /etc/hosts "$TMPROOT/hosts"')
assert_deny "(q) sandbox var with a same-segment || fallback binding -> still deny" "$result" \
    "unexpanded shell variable"

# --- (r) NEGATIVE: concatenation onto the substitution is a different value
# than the sandbox root -> still DENY unresolved.
result=$(run_hook 'TMPROOT=$(mktemp -d)/sub
cp /etc/hosts "$TMPROOT/hosts"')
assert_deny "(r) X=\$(mktemp -d)/sub concatenation -> still deny (unresolved)" "$result" \
    "unexpanded shell variable"

# --- (s) NEGATIVE: a bare `$(mktemp -d)` used DIRECTLY as the write target
# (no binding to follow) keeps its existing root-unknown deny.
result=$(run_hook 'cp /etc/hosts $(mktemp -d)/hosts')
assert_deny "(s) bare \$(mktemp -d) as the write target itself -> still deny" "$result" \
    "unexpanded shell variable"

# --- (t) NEGATIVE, the security hinge: with TMPDIR pointing INSIDE the main
# checkout, a real `mktemp -d` creates its directory there. The stand-in is a
# judged path in that same parent, so the ordinary literal containment test
# catches it -- no special case, and this is why the exception is fail-closed
# rather than a blanket trust of `mktemp`.
mkdir -p "$TMPROOT/intmp"
result=$(run_hook_tmpdir "$TMPROOT/intmp" 'TMPROOT="$(mktemp -d)"
cp /etc/hosts "$TMPROOT/hosts"')
assert_deny "(t) TMPDIR inside the main checkout -> deny (sandbox stand-in lands in the checkout)" "$result" \
    "resolves to the main repository checkout"

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
