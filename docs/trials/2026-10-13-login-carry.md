# Carrying subscription sign-ins into containers

On 2026-10-13, one sign-in per Provider served several Docker containers at once for Claude Code, Codex CLI and Antigravity CLI on one Mac. This was a supervised live trial. It shows the route works today; it does not show that it keeps working.

## Conditions

- Host: macOS 15 on Apple silicon, Docker 29.4.0 on OrbStack (`linux/arm64`, 4 GiB VM).
- Versions inside the containers: Claude Code 2.1.287, Codex CLI 0.162.0, agy 1.3.4. Google's installer takes the latest release; the host had agy 1.3.3.
- Every turn was a live call on the owner's subscriptions. No API key was used.
- The owner performed every sign-in. The agent ran the checks and read only pass or fail output.
- Prompt for every turn: `Reply with one word in upper case: the capital of France.` A turn passes when its output contains `PARIS`. The expected word is absent from the prompt, so an echoed prompt cannot pass.
- Models: Claude `haiku` (reported as `claude-haiku-4-5-20251001`), Codex's default, agy `gemini-3.8-flash-low`.

## Images

```dockerfile
# Antigravity CLI from Google's installer
FROM debian:bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -u 1000 agent && mkdir /work && chown agent /work
USER agent
RUN mkdir -p /home/agent/.gemini \
 && curl -fsSL https://antigravity.google/cli/install.sh -o /tmp/i.sh \
 && bash /tmp/i.sh --dir /home/agent/.local/bin \
 && rm /tmp/i.sh
ENV PATH=/home/agent/.local/bin:$PATH
WORKDIR /work
```

```dockerfile
# Codex CLI from npm
FROM node:22-bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git \
 && rm -rf /var/lib/apt/lists/* \
 && npm i -g @openai/codex@0.162.0
USER node
RUN mkdir -p /home/node/codex-home /home/node/work
ENV CODEX_HOME=/home/node/codex-home
WORKDIR /home/node/work
```

```dockerfile
# Claude Code from npm
FROM node:22-bookworm-slim
RUN npm i -g @anthropic-ai/claude-code@2.1.287
USER node
RUN mkdir -p /home/node/work
WORKDIR /home/node/work
```

## Sign-in, performed by the owner

| Harness | Command | What it stores |
| --- | --- | --- |
| agy | `docker run --rm -it -v spike-agy-seed:/home/agent/.gemini spike-agy agy`, then Google sign-in by URL and pasted code | A token file in the volume |
| Codex | `docker run --rm -it -v spike-codex-auth:/home/node/codex-home spike-codex codex login --device-auth` | `auth.json` in the volume |
| Claude Code | `claude setup-token` on the host | Nothing; the token is passed by variable name as `-e CLAUDE_CODE_OAUTH_TOKEN` |

Codex device-code sign-in must be enabled in the ChatGPT security settings first.

## Results

| Check | Claude Code | Codex | agy |
| --- | --- | --- | --- |
| A fresh container answers from the saved sign-in | Pass | Pass | Pass |
| Several containers at once | 3 of 3 | 3 of 3 on one shared `CODEX_HOME` | 2 of 2 on one shared volume |
| Per-session home | Not applicable | Pass, with `auth.json` linked to the one live file | Pass, with a private copy of the token file |
| Host sign-in afterwards | Unchanged | `auth.json` timestamp unchanged; one host turn answered | Three host turns answered |

Further observations:

- **Claude Code.** Inside the container, `claude auth status --json` reported `loggedIn: true` and `authMethod: oauth_token`. No `ANTHROPIC_*` variable and no credentials file were present.
- **Codex.** `codex login status` in a fresh container printed `Logged in using ChatGPT`.
- **agy.** With no D-Bus session in the container, the sign-in wrote `~/.gemini/antigravity-cli/antigravity-oauth-token` (1,672 bytes). A fresh container listed models from it. Copying only that file into an empty home was enough; copying the installation ID and cache as well made no observed difference.
- **agy service errors.** 5 of 18 container turns failed at Google's eligibility check: four with HTTP 503 and one with 502. None was a sign-in failure. The last 10 container turns succeeded, and all 3 host turns succeeded. The owner's interactive sign-in session hit the same 503. The sample cannot say whether containers are more exposed or the service had a brief outage.

## Limits

- The trial lasted about one hour. Codex refreshes its token near expiry and agy refreshes hourly; neither was confirmed across a refresh. The two sign-in volumes are kept for a later recheck.
- Only Claude Code's route is documented by its vendor. OpenAI's guidance is one `auth.json` per runner. Google documents an API key for headless use.
- Each turn was a one-word reply. Resume by session ID, tool use, network allowlists and memory limits were not tested.
- Passing here does not qualify unattended delivery.

## Lessons for Setup

- A Claude setup token can wrap onto two lines when copied. The first probe read one line from a hidden prompt, passed an incomplete token, and received `401 OAuth access token is invalid`. The rest of the token was typed into the terminal. Read the token from the clipboard and strip whitespace, or accept several lines.
- Pass a token to Docker by variable name, never as a `KEY=VALUE` argument.
