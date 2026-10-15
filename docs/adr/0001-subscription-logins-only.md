---
status: accepted
---

# Subscription logins only

Agent Sessions sign in with each Provider's subscription, through the vendor's own unmodified Harness and sign-in flow, once per Provider. API keys are not used, and no model gateway or proxy sits between a Harness and its Provider (LiteLLM, OmniRoute, credential-rewriting proxies). API billing defeats the purpose of the subscription quotas, and a third-party client or gateway presenting a subscription login is what Providers have suspended accounts for.

## Considered options

- **API keys for unattended work.** Rejected: it gives up the subscription quotas, which are the reason for the rule.
- **A credential proxy that keeps tokens outside the sandbox** (Docker Sandboxes, AstraBox with LiteLLM). Rejected: it terminates TLS and rewrites the authorization header on Provider traffic, which is the intermediary pattern this rule excludes.

## Consequences

- Only rapid-orchestrator, deferred by [ADR 0003](0003-walk-on-bare-sessions-orchestrator-deferred.md), would run Sessions in containers. There the one sign-in per Provider would be copied into each container as that vendor's own token or token file, so the token would be readable inside the container. Walk runs no containers.
- Tools that accept only API keys are unavailable, including OpenAI's Codex GitHub Action.
- Google's consumer terms say that wrapping `agy` inside third-party applications is not supported. The owner accepted that risk on 2026-10-13 and the Antigravity adapter is on by default.
- These consequences assume subscription sign-ins only. API billing support is a possible future option under consideration, not a decision. If it is added (a backlog item), this ADR is revisited.
