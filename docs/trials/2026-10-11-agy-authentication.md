# Antigravity authentication probe

On 2026-10-11, one supervised native authentication request succeeded with agy 1.3.3 and exact model `gemini-3.7-flash-high`. The CLI's current catalog contained that model. No account, default model or global settings were changed.

The probe used an empty temporary directory, `--mode plan`, streamed JSON and a timeout. After the CLI identified the requested model and session, it received one message:

> Hi. Reply with exactly RAPID_SHIP_AUTH_OK. Do not use tools or access files.

The result reported `SUCCESS` with the exact marker and a successful process exit. No tool-step events were observed. Inference took about 3 seconds; the complete check took about 7 seconds. Reported usage was 12,731 input tokens and 84 output tokens, including 76 thinking tokens. A tiny user message can still carry substantial CLI context.

Initialization advertised 60 tools and reported `request-review` permission mode despite the `plan` argument. This is why authentication no longer depends on an empty tool list. The prompt is a request to avoid tools, not an isolation mechanism. The result records `tool_activity` separately; `tool_event_count` counts reported tool-step updates, not unique calls. Partial or unobserved activity stays unknown.

The authentication parser checks the exact model/session, complete successful marker response and process exit. It rejects malformed, interrupted, mismatched and failed responses. It does not reuse the stricter coding-worker parser: successful authentication makes no claim about worker permissions, sandbox credentials, reviewer independence or unattended delivery. Those qualification gates remain unchanged.

Regression tests use simulated CLI events, including advertised tools, actual tool activity, quota failure, model/session mismatch and incomplete results. This live request confirms only host authentication and access to the named model at the time of the check. It is not a production execution trial.
