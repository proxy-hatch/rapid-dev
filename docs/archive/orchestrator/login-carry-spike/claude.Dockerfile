# Throwaway spike image: Claude Code from npm, pinned to the host's version.
FROM node:22-bookworm-slim
RUN npm i -g @anthropic-ai/claude-code@2.1.287
USER node
RUN mkdir -p /home/node/work
WORKDIR /home/node/work
