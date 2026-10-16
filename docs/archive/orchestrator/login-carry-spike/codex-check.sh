#!/bin/bash
# THROWAWAY SPIKE. Does one Codex device-code sign-in, saved in a Docker volume, serve several containers?
# Writes pass/fail lines to results/codex.txt. Never prints or reads a token value.
set -u
S="$(cd "$(dirname "$0")" && pwd)"; R="$S/results"; RAW="$R/raw"; mkdir -p "$RAW"; OUT="$R/codex.txt"; : > "$OUT"
IMG=spike-codex; VOL=spike-codex-auth; HOST_BASELINE="${HOST_BASELINE:?set to the output of: stat -f %m ~/.codex/auth.json, taken before the container sign-in}"
PROMPT='Reply with one word in upper case: the capital of France.'
say(){ echo "$*" | tee -a "$OUT"; }
verdict(){ if [ "$1" = "$2" ]; then echo PASS; else echo "FAIL ($1/$2)"; fi; }

# 1. Fresh container sees the saved login.
docker run --rm -v $VOL:/home/node/codex-home $IMG codex login status > "$RAW/codex-1-status.txt" 2>&1
say "1 fresh container login status: $(head -1 "$RAW/codex-1-status.txt")"

# 2. Three containers at once on the one shared CODEX_HOME.
for n in 1 2 3; do docker run --rm -v $VOL:/home/node/codex-home $IMG sh -c "timeout 240 codex exec --skip-git-repo-check '$PROMPT'" > "$RAW/codex-2-shared-$n.out" 2> "$RAW/codex-2-shared-$n.err" & done; wait
say "2 three at once, shared home: $(verdict $(grep -l PARIS "$RAW"/codex-2-shared-*.out 2>/dev/null | wc -l | tr -d ' ') 3)"

# 3. Per-session home that links to the one live auth file.
docker run --rm -v $VOL:/auth $IMG sh -c "mkdir -p /tmp/h && ln -s /auth/auth.json /tmp/h/auth.json && CODEX_HOME=/tmp/h timeout 240 codex exec --skip-git-repo-check '$PROMPT'" > "$RAW/codex-3-linked.out" 2> "$RAW/codex-3-linked.err"
say "3 per-session home with linked login: $(verdict $(grep -c PARIS "$RAW/codex-3-linked.out") 1)"

# 4. Host login still works: status, unchanged file timestamp, one small turn.
say "4a host login status: $(codex login status 2>&1 | head -1)"
now=$(stat -f %m ~/.codex/auth.json); if [ "$now" = "$HOST_BASELINE" ]; then say "4b host login file untouched: PASS"; else say "4b host login file untouched: CHANGED ($HOST_BASELINE -> $now)"; fi
d=$(mktemp -d); ( cd "$d" && perl -e 'alarm 240; exec @ARGV' codex exec --skip-git-repo-check "$PROMPT" > "$RAW/codex-4-host.out" 2> "$RAW/codex-4-host.err" ); rmdir "$d" 2>/dev/null
say "4c host answers: $(verdict $(grep -c PARIS "$RAW/codex-4-host.out") 1)"
