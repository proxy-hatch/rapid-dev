#!/bin/bash
# THROWAWAY SPIKE, run by the owner. Does one Claude setup token serve several containers?
# Reads the token with echo off, passes it to Docker by variable name, and writes only
# pass/fail lines to results/claude.txt. The token is not stored and not printed.
set -u
S="$(cd "$(dirname "$0")" && pwd)"; R="$S/results"; RAW="$R/raw"; mkdir -p "$RAW"; OUT="$R/claude.txt"; : > "$OUT"
IMG=spike-claude
PROMPT='Reply with one word in upper case: the capital of France.'
say(){ echo "$*" | tee -a "$OUT"; }
verdict(){ if [ "$1" = "$2" ]; then echo PASS; else echo "FAIL ($1/$2)"; fi; }

# Take the token from the clipboard, so nothing is pasted into the terminal and a token that
# wrapped onto two lines when copied is joined again. Only its length is ever shown.
CLAUDE_CODE_OAUTH_TOKEN="$(pbpaste | tr -d '[:space:]')"
case "$CLAUDE_CODE_OAUTH_TOKEN" in
  sk-ant-*) : ;;
  *) echo "The clipboard does not hold a Claude token (it should start with sk-ant-). Copy the whole token printed by 'claude setup-token', including any part on a second line, and run this again."; unset CLAUDE_CODE_OAUTH_TOKEN; exit 1 ;;
esac
say "0 token read from clipboard: ${#CLAUDE_CODE_OAUTH_TOKEN} characters"
printf '' | pbcopy
export CLAUDE_CODE_OAUTH_TOKEN

# 1. Fresh container, one inference turn on the cheapest model.
docker run --rm -e CLAUDE_CODE_OAUTH_TOKEN $IMG claude -p "$PROMPT" --model haiku --output-format json > "$RAW/claude-1-single.out" 2> "$RAW/claude-1-single.err"; rc=$?
say "1 fresh container answers: $(verdict $(grep -c PARIS "$RAW/claude-1-single.out") 1) (exit $rc)"

# 2. Three containers at once on the one token.
for n in 1 2 3; do docker run --rm -e CLAUDE_CODE_OAUTH_TOKEN $IMG claude -p "$PROMPT" --model haiku --output-format json > "$RAW/claude-2-multi-$n.out" 2> "$RAW/claude-2-multi-$n.err" & done; wait
say "2 three at once: $(verdict $(grep -l PARIS "$RAW"/claude-2-multi-*.out 2>/dev/null | wc -l | tr -d ' ') 3)"

# 3. How the container says it is signed in (no secret in this output).
docker run --rm -e CLAUDE_CODE_OAUTH_TOKEN $IMG claude auth status --json > "$RAW/claude-3-status.json" 2> "$RAW/claude-3-status.err"
say "3 container sign-in: $(tr -d '\n' < "$RAW/claude-3-status.json" | grep -o '"\(loggedIn\|authMethod\|apiProvider\|subscriptionType\)"[^,}]*' | tr '\n' ' ')"

# 4. Nothing else Anthropic-related is in the container.
docker run --rm -e CLAUDE_CODE_OAUTH_TOKEN $IMG sh -c 'echo "anthropic_env=$(env | grep -c "^ANTHROPIC_")"; [ -e ~/.claude/.credentials.json ] && echo credentials_file=present || echo credentials_file=absent' > "$RAW/claude-4-clean.txt" 2>&1
say "4 container holds only the token: $(tr '\n' ' ' < "$RAW/claude-4-clean.txt")"

# 5. The token must not appear in any saved output.
leaks=$(grep -rlF -- "$CLAUDE_CODE_OAUTH_TOKEN" "$R" 2>/dev/null)
if [ -n "$leaks" ]; then echo "$leaks" | while read -r f; do rm -f "$f"; done; say "5 token in saved output: FOUND AND DELETED"; else say "5 token in saved output: none"; fi
unset CLAUDE_CODE_OAUTH_TOKEN
echo; echo "Done. Results are in $OUT"
