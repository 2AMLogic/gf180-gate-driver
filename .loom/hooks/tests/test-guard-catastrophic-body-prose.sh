#!/usr/bin/env bash
# Regression test for .loom/hooks/guard-destructive-generic.sh's
# catastrophic-tier ALWAYS_BLOCK_PATTERNS scan false-denying a non-heredoc
# `--body` argument whose DOUBLE-quoted prose merely quotes/describes the
# catastrophic recursive-force-remove-root pattern, rather than invoking it
# (issue #149).
#
# Usage: ./.loom/hooks/tests/test-guard-catastrophic-body-prose.sh
#
# Provenance: `.loom/logs/guard-decisions.log`'s `2026-08-15T12:24:01Z` entry
# recorded a DENY on a plain `gh issue comment "$ISSUE_NUMBER" --body "..."`
# call -- no heredoc, no `rm` ever executed -- whose double-quoted body was a
# Champion review comment quoting the catastrophic pattern as documentation,
# via bash's standard escaped-backtick idiom (`\`rm -rf /\`` inside a
# double-quoted argument -- a literal backslash-backtick pair in the raw
# command text, which bash itself would parse as one inert literal backtick
# once actually executed, but which the guard hook scans as raw,
# UN-shell-parsed source text).
#
# Issue #149's own curator investigation (see the issue body) bisected this
# to ALREADY FIXED on `main`, as an incidental side effect of PR #119
# ("delimit escaped double-quoted flag values the way bash does", closes
# #112) and PR #142 ("make strip_literal_text() quote-context-aware across
# real bash argument boundaries", closes #120) -- both landed to fix a
# DIFFERENT reported symptom (the ask-tier `git clean -fd` pattern; see
# test-guard-git-clean-scope.sh) but generalized to this issue's
# catastrophic-tier `--body`-flag shape too, since both scans share
# strip_literal_text()'s COMMAND_NO_LITERAL_TEXT buffer. No production code
# change is expected from this issue -- it exists purely to pin the
# already-correct behavior with a regression test, so a future refactor of
# strip_literal_text() can't silently reintroduce the false DENY with
# nothing to catch it.
#
# This shape is deliberately kept in its own file, sibling to (not appended
# to) test-strip-literal-text-bsq.sh: that suite's ALLOW cases for "dangerous
# phrase quoted as prose in --body" exercise the SINGLE-quote
# apostrophe-escaping bug (#56/BSQ) specifically, whereas this issue's
# repro is a DOUBLE-quoted --body value using bash's escaped-backtick idiom
# -- a different masking code path through strip_literal_text() (compare
# this file's PART 2 case (a) against that file's case (d), which
# deliberately keeps an UNESCAPED backtick inside a double-quoted span as a
# live-shell-syntax safety floor that must stay ASK/DENY).
#
# Covers, end-to-end through the real PreToolUse JSON protocol:
#   (a) the exact historical repro from guard-decisions.log (double-quoted
#       --body, escaped-backtick-wrapped dangerous phrase, embedded in a
#       real multi-line Champion-review comment body) -> ALLOW
#   (b) the issue's own minimal reproduction shape: plain, UNBACKTICKED
#       prose mentioning the catastrophic pattern in a --body value, no
#       heredoc -> ALLOW
#   (c) a `gh pr comment` variant of (b), confirming the fix isn't
#       `gh issue comment`-specific -> ALLOW
#   (d)-(g) paired safety-floor cases: a REAL rm -rf /-family invocation
#       (bare, sudo-prefixed, &&-chained, and bash -c-smuggled) must still
#       resolve DENY, so (a)-(c) can't be satisfied by an over-broad mask
#
# The hook under test is the canonical source at .loom/hooks/ (this repo
# ships no defaults/ tree -- see the file's own banner), copied into an
# isolated temp git tree alongside its config-resolver.sh/canonical-path.sh
# lib dependencies so MAIN_ROOT/git-common-dir resolve inside the temp tree,
# exactly like test-strip-literal-text-bsq.sh's PART 2 does for the same
# hook. Exit 0 = all pass, 1 = fail.

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
# contains the literal substring "rm -rf /" contiguously -- avoids tripping
# this same guard on any future Bash invocation that greps/cats this file
# (matching the convention already used by every sibling suite in this
# directory).
RMRF="rm -r""f /"

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT
git init -q "$TMPROOT"
mkdir -p "$TMPROOT/.loom/hooks" "$TMPROOT/.loom/scripts/lib"
cp "$SRC_HOOK" "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
chmod +x "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
cp "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" "$TMPROOT/.loom/scripts/lib/config-resolver.sh"
cp "$REPO_ROOT/.loom/scripts/lib/canonical-path.sh" "$TMPROOT/.loom/scripts/lib/canonical-path.sh"
HOOK="$TMPROOT/.loom/hooks/guard-destructive-generic.sh"

# Build stdin JSON for a Bash tool_input, with cwd fixed at TMPROOT (the
# synthetic main checkout).
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

echo "=== guard-destructive-generic.sh end-to-end ALLOW/DENY tests (#149) ==="

# --- (a) the EXACT historical repro from guard-decisions.log's
# 2026-08-15T12:24:01Z entry: a real, multi-line script that ends in a
# `gh issue comment "$ISSUE_NUMBER" --body "..."` call whose double-quoted
# body is Champion's full review-verdict prose, quoting the catastrophic
# pattern several times via bash's escaped-backtick idiom
# (`\`rm -rf /\`` -- a literal backslash-backtick pair in the raw source
# text). Captured via a single-quoted heredoc (so no part of the original
# text is reinterpreted/expanded) with the dangerous phrase itself replaced
# by a placeholder token, substituted back in afterward via the
# parts-built $RMRF above -- byte-for-byte faithful to the logged command
# otherwise. -> ALLOW (was DENY on 2026-08-15; fixed by #119/#142).
CMD_HIST_TEMPLATE=$(cat <<'HISTORICAL_REPRO_EOF'
cd /Users/rwalters/GitHub/gf180-gate-driver
ISSUE_NUMBER=58

# Verdict-time recheck
RECHECK_LABELS=$(gh issue view "$ISSUE_NUMBER" --json labels --jq '[.labels[].name] | join(",")')
echo "RECHECK_LABELS=$RECHECK_LABELS"
if ! echo ",$RECHECK_LABELS," | grep -q ",loom:evaluating,"; then
  echo "ABORT: claim lost"
  exit 1
fi

gh issue edit "$ISSUE_NUMBER" \
  --remove-label "loom:auditor" \
  --remove-label "loom:evaluating" \
  --add-label "loom:issue" \
  --add-label "tier:maintenance"

gh issue comment "$ISSUE_NUMBER" --body "**Champion Review: APPROVED**

This issue has been evaluated and promoted to \`loom:issue\` status. All quality criteria passed:

- Clear problem statement: catastrophic \`@@RMRF@@\` guard false-denies heredoc-written test fixtures that mention the dangerous phrase as literal text
- Technical feasibility: verified against \`.loom/hooks/guard-destructive-generic.sh\` -- the \`ALWAYS_BLOCK_PATTERNS\` catastrophic scan (including the \`@@RMRF@@\` pattern at line ~2884) runs on \`COMMAND_NO_LITERAL_TEXT\`, which is only redacted via \`strip_literal_text()\` when specific flags (\`--body\`/\`--message\`/\`--title\`/\`--notes\`/\`--comment\`/\`-m\`/\`--search\`/\`--arg\`) are present. A plain \`cat > file << 'EOF'\` heredoc write triggers none of those, so heredoc body text reaches the scan unmasked -- confirms the reported false-positive mechanism
- Implementation clarity: recommends extending heredoc-body masking (the repo already has \`mask_heredoc_bodies\`/\`mask_heredoc_bodies_selective\`, currently wired into \`extract_write_targets()\`) to also cover the catastrophic \`ALWAYS_BLOCK_PATTERNS\`/\`extract_rm_targets()\` scan, preserving full scanning for unquoted/expanding heredoc delimiters where \$(...) / backticks really do execute
- Value alignment: reduces false-positive friction on the safety guard without relaxing the actual \`@@RMRF@@\` DENY floor
- Scope appropriateness: bounded to one additional masking call site, reusing existing masking primitives
- Quality standards: technical references verified accurate against current \`main\`
- Risk assessment: touches a safety-critical guard -- implementation must preserve DENY on real \`@@RMRF@@\` (bare, sudo-prefixed, \`&&\`-chained, smuggled via \`bash -c\`/unquoted heredoc) while only masking genuinely inert literal heredoc bodies; Builder/Judge should add regression tests for both directions
- Completeness: problem, root cause, and recommended fix are all present with file/line-level grounding

**Goal Alignment**: Tier 3 (maintenance) -- this is Loom guard/tooling infrastructure for this repo's own automation, not gf180-gate-driver design work. Current tier:maintenance backlog is 1, well under the 5-issue cap.

**Ready for Builder to claim.**

---
*Automated by Champion role*"
HISTORICAL_REPRO_EOF
)
CMD_HIST="${CMD_HIST_TEMPLATE//@@RMRF@@/$RMRF}"
result=$(run_hook "$CMD_HIST")
assert_allow "(a) exact historical guard-decisions.log repro: double-quoted --body, escaped-backtick dangerous phrase -> allow" "$result"

# --- (b) the issue's own minimal reproduction shape: plain, UNBACKTICKED
# prose in a double-quoted --body value mentioning the catastrophic
# recursive-force-remove-root pattern -- no heredoc, no backticks at all
# (deliberately distinct from (a), which is wrapped in escaped backticks).
result=$(run_hook "gh issue comment 123 --body \"This pattern blocks a catastrophic recursive-force-remove-root command such as ${RMRF} when found outside quotes.\"")
assert_allow "(b) minimal repro: plain unbackticked prose describing the pattern in --body -> allow" "$result"

# --- (c) same minimal shape via `gh pr comment` instead of
# `gh issue comment` -- confirms the fix isn't tied to one specific
# subcommand.
result=$(run_hook "gh pr comment 45 --body \"Note: this guard's job is to deny a bare ${RMRF}-style invocation, not prose describing one.\"")
assert_allow "(c) gh pr comment variant of the minimal repro -> allow" "$result"

# --- (d) safety floor: a REAL, bare invocation (no --body flag involved at
# all) must still resolve DENY, so (a)-(c) can't be satisfied by an
# over-broad mask.
result=$(run_hook "$RMRF")
assert_deny "(d) safety floor: real bare invocation, no --body -> still deny" "$result" \
    "dangerous pattern"

# --- (e) safety floor: sudo-prefixed real invocation -> still DENY.
result=$(run_hook "sudo $RMRF")
assert_deny "(e) safety floor: real sudo-prefixed invocation -> still deny" "$result" \
    "dangerous pattern"

# --- (f) safety floor: &&-chained real invocation trailing an otherwise
# inert --body comment (mirrors the exact shape a compromised/careless
# script might use to smuggle a live invocation behind a legitimate-looking
# comment call) -> still DENY.
result=$(run_hook "gh issue comment 123 --body \"just a status update\" && $RMRF")
assert_deny "(f) safety floor: real invocation &&-chained after an inert --body call -> still deny" "$result" \
    "dangerous pattern"

# --- (g) safety floor: real invocation smuggled via `bash -c` -> still
# DENY.
result=$(run_hook "bash -c '$RMRF'")
assert_deny "(g) safety floor: real invocation smuggled via bash -c -> still deny" "$result" \
    "dangerous pattern"

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
