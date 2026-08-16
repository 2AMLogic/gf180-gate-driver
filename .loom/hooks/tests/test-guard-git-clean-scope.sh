#!/usr/bin/env bash
# Test suite for the `git clean -fd` scoped sim-artifact allowlist added to
# .loom/hooks/guard-destructive-generic.sh (gf180-gate-driver#15).
#
# Unlike the other .loom/hooks/tests/*.sh files in this repo, this test
# targets THIS repo's own installed hook directly (.loom/hooks/…) rather than
# a `defaults/` source tree — this consumer repo has no `defaults/` directory
# (that only exists in the Loom source repo itself; see the header comment on
# test-guard-worktree-paths.sh, which is inert here for exactly that reason).
# `.loom/**` is intentionally excluded from this repo's own CI *lint*
# (.github/scripts/lint.sh: "vendored .loom/… tree… installed and regenerated
# by external tooling"), but this suite IS gated: the `test` job in
# .github/workflows/ci.yml runs it (with the four other hook suites) under
# `set -euo pipefail`, so a failing case fails the PR. Run it manually after
# touching the guard too — it needs nothing but bash and jq.
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
# Plus the #90 / PR #92-review group at the bottom of this file:
#   - inert prose mentioning the phrase (zero real invocations)  -> allow
#   - a LIVE invocation anywhere inside a `$(...)`/backtick
#     substitution nested in a quoted span — glued to the opener
#     or merely preceded by other text in the same substitution  -> ask
#   - a double-spaced `git  clean  -fd` invocation               -> ask
#
# Plus the #112 group at the bottom of this file (backslash-escaped example
# code quoted as prose inside a double-quoted flag value):
#   - `--body "example: \"\$(true; git clean -fd .)\""`          -> allow
#   - the full PR #103 approval comment body that hit this live  -> allow
#   - an UNESCAPED `$(...)`/backtick in the same position        -> ask
#
# Plus the #94 coexistence group:
#   - a directly-recognized, CONFINED invocation coexisting with a
#     hidden one inside a nested `$(...)`, in either order      -> ask
#   - the same confined invocation alongside a prose-only
#     substitution mention                                      -> allow
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

# --- ASK-tier false-positive redaction (gf180-gate-driver#41) ---------------
# The `git clean -fd` ask-tier scan (COMMAND_ASK_SCAN) previously fired on a
# command that merely MENTIONS the phrase as inert prose — never invoking
# `git clean` at all — inside a plain `echo "..."` argument, or a
# `--body "$(cat <<'EOF' ... EOF)"` heredoc-via-command-substitution value
# used to author a static issue/PR body. Both shapes below reproduce
# guard-decisions.log entries cited in #41. Every case still confirms a REAL
# invocation (bare, interpreter-fed heredoc, unquoted-delimiter heredoc with
# a live `$(...)`, or mixed with an inert mention on an earlier line) keeps
# asking exactly as before — the redaction must only ever narrow, never widen.

assert_decision \
    "plain echo prose mentioning the phrase no longer asks" \
    "$(printf 'echo "=== search git clean -fd ask ==="\ngh issue list --state all --search "something" --limit 20')" \
    "$WT" \
    "allow"

assert_decision \
    "--body \"\$(cat <<'EOF' ... EOF)\" heredoc authoring a static issue body no longer asks" \
    "$(printf '%s\n' \
        "./.loom/scripts/create-issue.sh --title 'test' --body \"\$(cat <<'EOF2'" \
        "This issue discusses the git clean -fd ask-tier false positive." \
        "EOF2" \
        ')" --label bug')" \
    "$WT" \
    "allow"

# strip_literal_text()'s own mask_flag_cat_heredocs() pre-pass already masks
# the --body/-m/--title/--notes/--comment heredoc-via-$(cat) shape above; this
# case exercises the NEW COMMAND_ASK_SCAN heredoc-masking step specifically —
# a heredoc feeding --search, a flag mask_flag_cat_heredocs() does not cover.
assert_decision \
    "--search \"\$(cat <<'EOF' ... EOF)\" heredoc mentioning the phrase no longer asks" \
    "$(printf '%s\n' \
        "gh issue list --search \"\$(cat <<'EOF2'" \
        "mentions git clean -fd only as prose" \
        "EOF2" \
        ')"')" \
    "$WT" \
    "allow"

assert_decision \
    "plain echo mention on an earlier line does not hide a REAL invocation later (narrows, never widens)" \
    "$(printf 'echo "mentions git clean -fd only as text"\ngit clean -fd .')" \
    "$WT" \
    "ask"

assert_decision \
    "quoted-delimiter heredoc mention does not hide a REAL invocation on a later line (narrows, never widens)" \
    "$(printf '%s\n' \
        "gh issue create --title x --body \"\$(cat <<'EOF'" \
        "mentions git clean -fd only as prose" \
        "EOF" \
        ')"' \
        'git clean -fd .')" \
    "$WT" \
    "ask"

assert_decision \
    "interpreter-fed heredoc (bash <<EOF … git clean -fd … EOF) still asks" \
    "$(printf '%s\n' \
        "bash <<EOF" \
        "cd $WT" \
        "git clean -fd ." \
        "EOF")" \
    "$TMPROOT" \
    "ask"

assert_decision \
    "unquoted-delimiter heredoc whose body performs a LIVE git clean -fd via \$(...) still asks" \
    "$(printf '%s\n' \
        "gh issue comment 1 --body \"\$(cat <<EOF" \
        "\$(git clean -fd .)" \
        "EOF" \
        ')"')" \
    "$WT" \
    "ask"

# --- Command-substitution re-scan guard (gf180-gate-driver#90) -------------
# extract_git_clean_fd_targets()'s whitespace tokenizer cannot resolve a LIVE
# invocation sitting anywhere inside a `$(...)`/backtick substitution that is
# nested in an outer quoted span: mask_ws()'s flat quote-tracking does not
# reset at the substitution boundary, so every space for the REST of the
# outer span is masked and the invocation collapses into one token. The
# zero-real-invocation allow must therefore be backed by a re-scan of every
# command-substitution BODY, not just the narrow "glued directly onto the
# `$(` opener" shape — a real invocation that is merely PRECEDED by other
# text inside the same substitution (`$(true; git clean -fd .)`) is just as
# live, and was silently allowed by the glued-only guard (PR #92 review).

assert_decision \
    "backtick-glued LIVE git clean -fd inside a heredoc body still asks" \
    "$(printf '%s\n' \
        "gh issue comment 1 --body \"\$(cat <<EOF" \
        "\`git clean -fd .\`" \
        "EOF" \
        ')"')" \
    "$WT" \
    "ask"

# The PR #92 review's exact repro: a plain quoted command substitution whose
# invocation is NOT the first token after the opener. No heredoc involved.
assert_decision \
    "nested-but-not-glued LIVE invocation in a quoted \$() still asks (PR #92 repro)" \
    "echo \"\$(true; git  clean  -fd .)\"" \
    "$TMPROOT" \
    "ask"

assert_decision \
    "nested-but-not-glued LIVE invocation, single-spaced, still asks" \
    "echo \"\$(true; git clean -fd .)\"" \
    "$TMPROOT" \
    "ask"

assert_decision \
    "nested-but-not-glued LIVE invocation after && still asks" \
    "echo \"\$(echo hi && git clean -fd .)\"" \
    "$TMPROOT" \
    "ask"

assert_decision \
    "nested-but-not-glued LIVE invocation in a quoted backtick span still asks" \
    "echo \"\`true; git clean -fd .\`\"" \
    "$TMPROOT" \
    "ask"

# The same gap in the heredoc shape the glued guard was written for — the
# invocation is inside the heredoc body's own \$(...), just not glued to it.
assert_decision \
    "nested-but-not-glued LIVE invocation inside a heredoc body still asks (PR #92 repro)" \
    "$(printf '%s\n' \
        "gh issue comment 1 --body \"\$(cat <<EOF" \
        "\$(true; git  clean  -fd .)" \
        "EOF" \
        ')"')" \
    "$WT" \
    "ask"

# A substitution-nested invocation is unresolvable by the tokenizer, so the
# scoped sim/** allowlist can never prove its confinement — it asks even when
# its target text would have been confined had it been written plainly. The
# guard only ever asks here; it never denies.
assert_decision \
    "substitution-nested invocation asks even with a sim/** target (cannot prove confinement)" \
    "echo \"\$(true; git clean -fd sim/device-mv-fet/corners/)\"" \
    "$WT" \
    "ask"

# Whitespace-tolerant pre-check: a double-spaced invocation previously missed
# the block's literal single-space gate entirely and never asked at all.
assert_decision \
    "double-spaced bare unconfined 'git  clean  -fd .' asks" \
    "git  clean  -fd ." \
    "$TMPROOT" \
    "ask"

assert_decision \
    "double-spaced confined sim/** target still allows (gate widening adds no false ask)" \
    "git  clean  -fd sim/device-mv-fet/corners/" \
    "$WT" \
    "allow"

# Narrows, never widens: prose living INSIDE a command substitution is still
# prose — the re-scan recognizes invocations, not mentions.
assert_decision \
    "prose mention inside a command-substitution body still allows" \
    "gh issue comment 1 --body \"\$(printf '%s' 'mentions git clean -fd only as prose')\"" \
    "$WT" \
    "allow"

# --- Coexistence: confined direct target + hidden invocation (#94) ----------
# The substitution-body re-scan above was originally reached ONLY when the
# direct extraction returned zero targets. A command that pairs a
# directly-recognized, CONFINED invocation with a second invocation hidden
# inside a nested command substitution therefore skipped the re-scan
# entirely: the confinement loop proved the one target it could see was
# inside sim/**, saw no violation, and allowed — while the hidden,
# unconfined invocation executed unseen. The re-scan now runs regardless of
# whether the direct extraction found targets, and a hit there is an
# INDEPENDENT reason to ask that a confined direct target cannot suppress.

assert_decision \
    "confined direct target does not mask a hidden invocation in a nested \$() (#94 repro)" \
    "git clean -fd sim/device-mv-fet/corners/ && echo \"\$(true; git clean -fd /etc/passwordfile)\"" \
    "$WT" \
    "ask"

# Order-independence: the same coexistence shape with the hidden invocation
# FIRST must ask too — the re-scan is not positional.
assert_decision \
    "hidden invocation BEFORE the confined direct target still asks (reversed order)" \
    "echo \"\$(true; git clean -fd /etc/passwordfile)\" && git clean -fd sim/device-mv-fet/corners/" \
    "$WT" \
    "ask"

# Narrows, never widens: running the re-scan unconditionally must not turn a
# confined invocation into an ask merely because some substitution elsewhere
# in the command MENTIONS the phrase as prose.
assert_decision \
    "confined direct target plus a prose-only substitution mention still allows" \
    "git clean -fd sim/device-mv-fet/corners/ && echo \"\$(printf '%s' 'mentions git clean -fd only as prose')\"" \
    "$WT" \
    "allow"

# --- Zero-real-invocation substring false positives (gf180-gate-driver#90) --
# The line-5666 pre-check in the GIT CLEAN -fd SCOPED SIM-ARTIFACT ALLOWLIST
# block is a raw substring scan over the WHOLE command text and fires on the
# phrase appearing ANYWHERE, including inside a quoted prose/description
# argument passed to an unrelated tool. extract_git_clean_fd_targets() then
# correctly finds ZERO real `git clean -fd` invocations for these shapes
# (no segment's first three tokens are literally `git clean -fd*`) — that
# "zero real invocations" case must resolve to a trivial allow, not fall
# through to ask.

assert_decision \
    "check-duplicate.sh description mentioning the phrase in prose (with an unrelated backtick elsewhere) no longer asks" \
    "./.loom/scripts/check-duplicate.sh \"guard false positive\" \"The ask pattern (^|[;\&|(\`[:space:]])git clean -fd blocks check-duplicate.sh calls that merely describe it.\"" \
    "$WT" \
    "allow"

assert_decision \
    "gh issue list --jq test(\"git clean -fd\"...) query string no longer asks" \
    "gh issue list --repo 2AMLogic/gf180-gate-driver --jq '.[] | select(.title | test(\"git-clean-fd|git clean -fd\"; \"i\"))'" \
    "$WT" \
    "allow"

assert_decision \
    "bare unconfined 'git clean -fd' outside any worktree still asks (narrows, never widens)" \
    "git clean -fd" \
    "$TMPROOT" \
    "ask"

# --- Backslash-escaped example code inside a --body value (#112) ------------
# strip_literal_text()'s double-quoted span regex used to end at the FIRST raw
# quote byte, i.e. INSIDE a `\"` escape that bash does not treat as a closing
# quote. It therefore redacted only the head of a `--body` value and left the
# rest standing as apparently-UNQUOTED text; qsplit() then split at the (now
# unquoted-looking) `;` and handed extract_git_clean_fd_targets() a PHANTOM
# segment whose first three tokens are literally `git clean -fd`. The result
# was an ask on a comment body that runs nothing at all — which in a headless
# run stalls the agent, since there is nobody to answer it.
#
# Both rows of the #112 repro table are pinned below. Row 1 (no `;` in the
# escaped span) already allowed before the fix, but only by luck: with no
# separator there was nothing for the desynchronized parser to split on. It is
# kept here so the pair can never silently diverge again.
#
# All payloads below are written inside SINGLE quotes so the string handed to
# the hook is byte-for-byte what a real shell would receive.

assert_decision \
    "escaped-\$( example prose in a --body, no separator, allows (#112 repro row 1)" \
    'gh pr comment 1 --body "example: \"\$(git clean -fd .)\""' \
    "$WT" \
    "allow"

assert_decision \
    "escaped-\$( example prose in a --body with a ;-separated segment allows (#112 repro row 2)" \
    'gh pr comment 1 --body "example: \"\$(true; git clean -fd .)\""' \
    "$WT" \
    "allow"

assert_decision \
    "escaped-backtick + escaped-\$( example prose in a --body allows (#112)" \
    'gh pr comment 1 --body "e.g. \`echo \"\$(true; git clean -fd .)\"\`"' \
    "$WT" \
    "allow"

# The literal historical repro: the Judge approval comment on PR #103 that
# produced the two retried ask-tier entries in .loom/logs/guard-decisions.log
# (2026-08-16T03:31:48Z / 03:31:56Z) — a multi-line double-quoted --body whose
# prose quotes PR #92's own example, escaped to keep it inert.
assert_decision \
    "the full PR #103 approval comment body allows end-to-end (#112 historical repro)" \
    "$(printf '%s\n' \
        'gh pr comment 103 --body "LGTM — approving.' \
        '' \
        'The fix adds a 4th boundary-shape bullet (command-substitution embedding,' \
        'e.g. \`echo \"\$(true; git clean -fd .)\"\`) to the adversarial-testing' \
        'checklist in builder.md, matching what #96 required going forward.' \
        '' \
        'Approving."')" \
    "$WT" \
    "allow"

# Narrows, never widens. The escape is what makes the span inert, so the SAME
# shapes with a LIVE (unescaped) opener must keep asking — including the
# even-backslash-run spelling, where `\\` is a literal backslash and the
# substitution that follows it is genuinely expanded by bash.
assert_decision \
    "UNESCAPED \$( in the same --body position still asks (#112 narrows, never widens)" \
    'gh pr comment 1 --body "$(true; git clean -fd .)"' \
    "$WT" \
    "ask"

assert_decision \
    "UNESCAPED backtick span in the same --body position still asks (#112)" \
    'gh pr comment 1 --body "e.g. `true; git clean -fd .`"' \
    "$WT" \
    "ask"

assert_decision \
    "even-backslash run (literal backslash + LIVE \$( ) in a --body still asks (#112)" \
    'gh pr comment 1 --body "\\$(true; git clean -fd .)"' \
    "$WT" \
    "ask"

assert_decision \
    "escaped-quote prose in a --body does not hide a REAL invocation after it" \
    'gh pr comment 1 --body "x \" y" && git clean -fd .' \
    "$WT" \
    "ask"

assert_decision \
    "escaped-\$( prose --body does not hide a REAL invocation on a later line" \
    "$(printf '%s\n' \
        'gh pr comment 1 --body "a \"\$(true; git clean -fd .)\""' \
        'git clean -fd .')" \
    "$WT" \
    "ask"

# --- Escaped example code inside an UNQUOTED-delimiter heredoc body, itself
# the body of a live `$(cat <<EOF ... EOF)` substitution (#122) -------------
# #112 fixed the shape where the escaped example lived directly inside a
# --body value's own double-quoted span. This is a distinct shape: the
# ENTIRE --body value is `$(cat <<EOF ... EOF)` (unquoted delimiter, so
# mask_flag_cat_heredocs()/strip_literal_text() correctly leave it fully
# visible -- it genuinely executes `cat`). Nested TWO levels deep inside that
# live heredoc body is a backtick-delimited inline-code span, itself
# containing a `"..."`-quoted escaped `$(...)`, both escaped with backslashes
# so neither actually expands. The exact minimal repro from the issue body.
assert_decision \
    "escaped-backtick example quoting an escaped \$(git clean -fd) inside a LIVE, unquoted-delimiter \$(cat <<EOF...) heredoc body allows (#122 repro)" \
    "$(printf '%s\n' \
        'gh pr comment 1 --body "$(cat <<EOF' \
        'Example: \`git clean -fd sim/x/ && echo "\$(true; git clean -fd /etc/passwordfile)"\`' \
        'EOF' \
        ')"')" \
    "$WT" \
    "allow"

# Narrows, never widens: a GENUINELY live (unescaped) nested $(...) inside
# the very same heredoc shape -- sitting right alongside the escaped/inert
# backtick example above -- must still ask.
assert_decision \
    "genuinely LIVE nested invocation (unescaped \$(...)) inside the same heredoc shape still asks (#122 narrows, never widens)" \
    "$(printf '%s\n' \
        'gh pr comment 1 --body "$(cat <<EOF' \
        'Example: \`git clean -fd sim/x/\` and also $(true; git clean -fd /etc/passwordfile)' \
        'EOF' \
        ')"')" \
    "$WT" \
    "ask"

# Regression pin for the SILENT-ALLOW half of the #122 root cause: an
# ordinary parenthetical remark ("hello (world)") inside a nested
# double-quoted string, sitting BEFORE a real `git clean -fd` invocation in
# the same `$(...)` substitution, previously made
# extract_command_substitution_bodies() close the substitution body early on
# the parenthetical's own literal `)` -- truncating the extracted body before
# the real invocation was ever reached, and silently ALLOWING it. Found while
# diagnosing #122, not itself the reported symptom, but fixed by the same
# `!dq[depth]` guard.
assert_decision \
    "LIVE invocation reachable past an unrelated parenthetical earlier in the same substitution still asks (#122 silent-allow found while diagnosing the false ask)" \
    'echo "$(echo "hello (world) test" && git clean -fd .)"' \
    "$TMPROOT" \
    "ask"

echo
echo "== Summary: $PASS/$TOTAL passed =="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
