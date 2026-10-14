# Throwaway spike image: Antigravity CLI from Google's own installer.
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
