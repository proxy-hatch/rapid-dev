---
status: accepted
---

# This repository's agents use subscription sign-ins only

This is this repository's own rule, not a product rule. Agents that work on rapid-ship sign in with each Provider's subscription, through the vendor's own unmodified Harness and sign-in flow, once per Provider. They use no API key, and no model gateway or proxy sits between a Harness and its Provider (LiteLLM, OmniRoute, credential-rewriting proxies). API billing would give up the subscription quotas that pay for this repository's agent work. A third-party client or gateway that presents a subscription sign-in is what Providers have suspended accounts for.

rapid-ship the product works with any Provider: a vendor subscription, an API key or a gateway. For example, pi running a GLM model through OpenRouter works like any other Harness. Nothing rapid-ship ships needs an API key, and its CI needs no model sign-in. The product's documents therefore state no sign-in rule; this repository records its own in its root AGENTS.md.

## Considered options

- **Make subscription sign-ins a product rule.** Rejected on 2026-10-16: which Provider a Harness uses is each owner's choice, and rapid-ship starts no Session, so it could not enforce the rule anyway ([ADR 0004](0004-team-management-boundary.md)).
- **API keys for this repository's unattended work.** Rejected: they give up the subscription quotas, which are the reason for the rule.
- **A credential proxy that keeps tokens outside the sandbox** (Docker Sandboxes, AstraBox with LiteLLM). Rejected: it terminates TLS and rewrites the authorization header on Provider traffic, which is the intermediary pattern this rule excludes.

## Consequences

- Tools that accept only API keys are unavailable to this repository, including OpenAI's Codex GitHub Action.
- When this repository's Lead runs `claude -p` from another Harness's shell, it never passes `--bare`: bare mode skips the subscription sign-in and needs an API key.
- Google's consumer terms say that wrapping `agy` inside third-party applications is not supported. The owner accepted that risk on 2026-10-13, and again on 2026-10-15 when agy ran from inside a Codex CLI session. The acceptance covers `devctl doctor`'s agy probes and Roster routes that run `agy -p` from another Harness's shell. For other owners, `rs-lead` warns about those terms when it offers such a route.
- Backlog item PRO-107, API billing support, is closed as unneeded: the product already works with any Provider.
