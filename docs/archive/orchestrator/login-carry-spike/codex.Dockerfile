# Throwaway spike image: OpenAI Codex CLI from npm, pinned to the host's version.
FROM node:22-bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git \
 && rm -rf /var/lib/apt/lists/* \
 && npm i -g @openai/codex@0.162.0
USER node
RUN mkdir -p /home/node/codex-home /home/node/work
ENV CODEX_HOME=/home/node/codex-home
WORKDIR /home/node/work
