#!/bin/bash
# THROWAWAY SPIKE. Does one agy sign-in, saved in a Docker volume, serve fresh containers?
# Writes pass/fail lines to results/agy.txt. Never prints or reads a token value.
set -u
S="$(cd "$(dirname "$0")" && pwd)"; R="$S/results"; RAW="$R/raw"; mkdir -p "$RAW"; OUT="$R/agy.txt"; : > "$OUT"
IMG=spike-agy; SEED=spike-agy-seed; HOME_MNT=/home/agent/.gemini
PROMPT='Reply with one word in upper case: the capital of France.'
MODEL_ARG=${MODEL:+--model $MODEL}
say(){ echo "$*" | tee -a "$OUT"; }
verdict(){ if [ "$1" = "$2" ]; then echo PASS; else echo "FAIL ($1/$2)"; fi; }

say "agy in container: $(docker run --rm $IMG agy --version 2>&1 | head -1)   model arg: '${MODEL_ARG}'"

# 1. What the sign-in left in the volume (file names and sizes only).
docker run --rm -v $SEED:$HOME_MNT $IMG sh -c 'f=~/.gemini/antigravity-cli/antigravity-oauth-token; [ -s "$f" ] && echo token_file=present || echo token_file=absent; find ~/.gemini -maxdepth 3 -type f -printf "%s %p\n" | sed "s#/home/agent/##" | head -40' > "$RAW/agy-1-storage.txt" 2>&1
say "1 storage after sign-in: $(grep -m1 token_file "$RAW/agy-1-storage.txt")"

# 2. Fresh container, authentication only (no inference).
docker run --rm -v $SEED:$HOME_MNT $IMG sh -c 'timeout 90 agy models' > "$RAW/agy-2-models.out" 2> "$RAW/agy-2-models.err"; rc=$?
if [ $rc -eq 0 ] && ! grep -qi 'sign in' "$RAW/agy-2-models.out" "$RAW/agy-2-models.err"; then say "2 fresh container lists models: PASS"; else say "2 fresh container lists models: FAIL (exit $rc)"; fi

# 3. Fresh container, one inference turn.
docker run --rm -v $SEED:$HOME_MNT $IMG sh -c "timeout 180 agy -p '$PROMPT' --print-timeout 150s $MODEL_ARG" > "$RAW/agy-3-single.out" 2> "$RAW/agy-3-single.err"; rc=$?
say "3 fresh container answers: $(verdict $(grep -c PARIS "$RAW/agy-3-single.out") 1) (exit $rc)"

# 4. Two containers at once sharing the one seed volume.
for n in 1 2; do docker run --rm -v $SEED:$HOME_MNT $IMG sh -c "timeout 180 agy -p '$PROMPT' --print-timeout 150s $MODEL_ARG" > "$RAW/agy-4-shared-$n.out" 2> "$RAW/agy-4-shared-$n.err" & done; wait
say "4 two at once, shared volume: $(verdict $(cat "$RAW"/agy-4-shared-*.out | grep -c PARIS) 2)"

# 5. Two containers at once, each with its own copy of the token file only.
for n in 1 2; do
  docker volume create spike-agy-s$n >/dev/null
  docker run --rm -v $SEED:/seed:ro -v spike-agy-s$n:$HOME_MNT $IMG sh -c 'mkdir -p ~/.gemini/antigravity-cli && cp /seed/antigravity-cli/antigravity-oauth-token ~/.gemini/antigravity-cli/ && chmod 600 ~/.gemini/antigravity-cli/antigravity-oauth-token' > "$RAW/agy-5-copy-$n.txt" 2>&1
done
for n in 1 2; do docker run --rm -v spike-agy-s$n:$HOME_MNT $IMG sh -c "timeout 180 agy -p '$PROMPT' --print-timeout 150s $MODEL_ARG" > "$RAW/agy-5-private-$n.out" 2> "$RAW/agy-5-private-$n.err" & done; wait
say "5 two at once, private token copies: $(verdict $(cat "$RAW"/agy-5-private-*.out | grep -c PARIS) 2)"

# 6. Host login still works (authentication only).
perl -e 'alarm 90; exec @ARGV' agy models > "$RAW/agy-6-host.out" 2> "$RAW/agy-6-host.err"; rc=$?
if [ $rc -eq 0 ] && ! grep -qi 'sign in' "$RAW/agy-6-host.out" "$RAW/agy-6-host.err"; then say "6 host login intact: PASS"; else say "6 host login intact: FAIL (exit $rc)"; fi
