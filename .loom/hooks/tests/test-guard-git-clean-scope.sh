#!/usr/bin/env bash
# Test suite for the `git clean -fd` scoped sim-artifact allowlist added to
# .loom/hooks/guard-destructive-generic.sh (gf180-gate-driver#15).
#
# Unlike the other .loom/hooks/tests/*.sh files in this repo, this test
# targets THIS repo's own installed hook directly (.loom/hooks/…) rather than
# a `defaults/` source tree — this consumer repo has no `defaults/` directory
# (that only exists in the Loom source repo itself; see the header comment on
# test-guard-worktree-paths.sh, which is inert here for exactly that reason).
# `.loom/**` is intentionally excluded from this repo's own CI lint
# (.github/scripts/lint.sh: "vendored .loom/… tree… installed and regenerated
# by external tooling"), so this file is not wired into any CI job — it is a
# standalone regression check to run manually after touching the guard.
#
# Usage:
#   bash .loom/hooks/tests/test-guard-git-clean-scope.sh
#
# Covers the #15 refinement:
#   - bare `git clean -fd` (no path args)                       -> ask
#   - a target confined to <own worktree>/sim/**                -> allow
#   - a target touching a `records/` path segment                -> ask
#   - a mixed invocation (one safe target, one records/ target)  -> ask
#   - the bare `sim` dir itself (no subpath)                     -> ask
#   - a target escaping the worktree (`../`)                     -> ask
#   - cwd not inside ANY managed worktree (primary checkout)     -> ask
#   - a `cd <worktree> && …` prefix resolves against the cd target -> allow
#   - the exact multi-line `cd <worktree>\ngit clean -fdn …` shape
#     observed in .loom/logs/guard-decisions.log                 -> allow
#   - a violating target BEYOND any target-count bound           -> ask
#     (regression: `head -N` truncation of the extracted target list
#      silently dropped later targets, turning "no violation seen"
#      into an ALLOW — PR #19 review)
#   - a target list larger than the scan bound fails safe        -> ask
#   - fail-open contract preserved: exit is always 0
#
# Exit 0 = all pass, 1 = fail.

set -uo pipefail

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
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "${RED}FAIL${NC} %s\n" "$1 -- $2"; }

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT
git init -q "$TMPROOT"
git -C "$TMPROOT" config user.email test@example.com
git -C "$TMPROOT" config user.name "Test"
mkdir -p "$TMPROOT/.loom/hooks" "$TMPROOT/.loom/scripts/lib"
cp "$SRC_HOOK" "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
chmod +x "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
# Stage the real config-resolver.sh at the installed-layout relative path
# (../scripts/lib/config-resolver.sh from the hook's own dir) so the
# guards.worktreeIsolation-adjacent cold-path config reads exercise the real
# resolver rather than degrading to its "unsourceable" fallback.
cp "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" "$TMPROOT/.loom/scripts/lib/config-resolver.sh"
HOOK="$TMPROOT/.loom/hooks/guard-destructive-generic.sh"

# A managed worktree: a real .loom-managed sentinel plus a sim/ tree shaped
# like the actual gf180-gate-driver repo (corners/netlist-snapshots/.work as
# generated working dirs, records/ as the tracked evidence dir).
WT="$TMPROOT/.loom/worktrees/issue-99"
mkdir -p "$WT/sim/device-mv-fet/corners" "$WT/sim/device-mv-fet/netlist-snapshots" \
         "$WT/sim/device-mv-fet/records" "$WT/sim/smoke-mv-inverter/corners" \
         "$WT/.work"
touch "$WT/.loom-managed"

# Build stdin JSON for a Bash tool_input.command + cwd.
make_input() {
    local command="$1" cwd="$2"
    jq -n --arg cmd "$command" --arg cwd "$cwd" '{tool_input: {command: $cmd}, cwd: $cwd}'
}

# Run the hook. Prints "<exit_code>|<permissionDecision-or-allow>".
# permissionDecision is read from stdout JSON when present; a silent-allow
# (no stdout, exit 0) reports "allow".
run_hook() {
    local command="$1" cwd="$2"
    local exit_code=0 output decision
    output=$(cd "$TMPROOT" && bash "$HOOK" < <(make_input "$command" "$cwd") 2>/dev/null) || exit_code=$?
    if [[ -z "$output" ]]; then
        decision="allow"
    else
        decision=$(echo "$output" | jq -r '.hookSpecificOutput.permissionDecision // "allow"' 2>/dev/null) || decision="parse-error"
    fi
    printf '%s|%s' "$exit_code" "$decision"
}

assert_decision() {
    local desc="$1" command="$2" cwd="$3" expected="$4"
    local result exit_code decision
    result=$(run_hook "$command" "$cwd")
    exit_code="${result%%|*}"
    decision="${result##*|}"
    if [[ "$exit_code" != "0" ]]; then
        fail "$desc" "non-zero exit ($exit_code), fail-open contract violated"
        return
    fi
    if [[ "$decision" == "$expected" ]]; then
        pass "$desc"
    else
        fail "$desc" "expected '$expected', got '$decision'"
    fi
}

echo "== git clean -fd scoped sim-artifact allowlist (#15) =="
echo

assert_decision \
    "bare 'git clean -fd' (no path args) still asks" \
    "git clean -fd" \
    "$WT" \
    "ask"

assert_decision \
    "target confined to own worktree's sim/** allows" \
    "git clean -fd sim/device-mv-fet/corners/" \
    "$WT" \
    "allow"

assert_decision \
    "multiple targets all confined to own worktree's sim/** allows" \
    "git clean -fd sim/device-mv-fet/corners/ sim/device-mv-fet/netlist-snapshots/ sim/smoke-mv-inverter/corners/ sim/.work" \
    "$WT" \
    "allow"

assert_decision \
    "target touching records/ still asks" \
    "git clean -fd sim/device-mv-fet/records/" \
    "$WT" \
    "ask"

assert_decision \
    "mixed invocation (one safe target, one records/ target) still asks" \
    "git clean -fd sim/device-mv-fet/corners/ sim/device-mv-fet/records/" \
    "$WT" \
    "ask"

assert_decision \
    "the bare sim dir itself (no subpath) still asks" \
    "git clean -fd sim" \
    "$WT" \
    "ask"

assert_decision \
    "a target escaping the worktree via .. still asks" \
    "git clean -fd ../../etc" \
    "$WT" \
    "ask"

assert_decision \
    "cwd not inside any managed worktree still asks" \
    "git clean -fd sim/device-mv-fet/corners/" \
    "$TMPROOT" \
    "ask"

assert_decision \
    "'cd <worktree> && …' prefix resolves against the cd target" \
    "cd $WT && git clean -fd sim/device-mv-fet/corners/" \
    "$TMPROOT" \
    "allow"

# The exact multi-line shape observed in .loom/logs/guard-decisions.log:
#   cd .loom/worktrees/issue-N
#   git clean -fdn sim/smoke-mv-inverter sim/.work
assert_decision \
    "observed multi-line 'cd <worktree>' + 'git clean -fdn …' shape allows" \
    "$(printf 'cd %s\ngit clean -fdn sim/smoke-mv-inverter sim/.work' "$WT")" \
    "$TMPROOT" \
    "allow"

# Also confirm every -fdn scoped invocation matches even though the
# observed log commands additionally pipe through `| head -20` — the guard
# only reasons about targets, not what a later pipeline stage does with
# stdout.
assert_decision \
    "observed shape with a trailing pipe still allows" \
    "git clean -fdn sim/.work 2>&1 | head -20" \
    "$WT" \
    "allow"

# --- Target-count bound must FAIL SAFE, never truncate silently (PR #19) -----
# The scope check flips its default to "allow unless a violation is seen" as
# soon as any target is extracted, so a bound that DROPS later targets turns a
# violating argument past the cutoff into a silent ALLOW. The original wiring
# capped extraction with `| head -50`; these cases pin the contract that a
# violation ANYWHERE in the full argument list still asks, regardless of how
# many arguments precede it.
gen_confined_targets() {
    local n="$1" i out=""
    for ((i = 0; i < n; i++)); do
        out+=" sim/device-mv-fet/corners/run-$i"
    done
    printf '%s' "$out"
}

assert_decision \
    "many confined targets (well past the old 50 cap) still allows" \
    "git clean -fd$(gen_confined_targets 120)" \
    "$WT" \
    "allow"

assert_decision \
    "records/ target at position 61 (past the old 50 cap) still asks" \
    "git clean -fd$(gen_confined_targets 60) sim/device-mv-fet/records/" \
    "$WT" \
    "ask"

assert_decision \
    "worktree-escaping target at position 121 still asks" \
    "git clean -fd$(gen_confined_targets 120) ../../etc" \
    "$WT" \
    "ask"

assert_decision \
    "records/ target as the LAST of a very long argument list still asks" \
    "git clean -fd$(gen_confined_targets 400) sim/device-mv-fet/records/summary.md" \
    "$WT" \
    "ask"

# Beyond the bound the target list can no longer be verified in full, so the
# guard must fall back to the ordinary ask (fail safe) rather than allow on a
# partial scan — even when every visible target is confined.
assert_decision \
    "target list exceeding the scan bound fails safe (asks)" \
    "git clean -fd$(gen_confined_targets 800)" \
    "$WT" \
    "ask"

echo
echo "== Summary: $PASS/$TOTAL passed =="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
