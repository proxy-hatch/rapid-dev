# Diagnose a defect

Start with the reported symptom, relevant code, local logs and accepted decisions. Apply [ponytail.md](ponytail.md). Keep credentials and private artifacts local; show only redacted evidence.

1. Build a small, repeatable check that detects the actual symptom: a failing test, CLI fixture, local request, captured-input replay or browser assertion. Repository inspection may help construct it. Run it and record the observed result before declaring a cause.
2. Reduce the inputs while preserving the failure. For intermittent behavior, record a baseline failure rate and control timing, data or concurrency where useful. Stay within the task's resource budget; do not stress shared services without authorization.
3. List plausible causes with a prediction that would distinguish each. Test one change or probe at a time. Prefer a targeted trace, debugger or timing measurement to broad logging.
4. Fix the demonstrated cause. Follow [tdd.md](tdd.md) for a regression check that reaches the real failure path. Re-run both the minimal check and the original scenario. If you forced a failure by mutation, verify the mutation actually landed before trusting the result.
5. Remove temporary instrumentation and fixtures that are no longer needed. Report the cause, fix and actual check results. Request independent review through [review.md](review.md).

If reproduction needs unavailable access or data, state what was tried and the specific missing input. Mark the conclusion uncertain and pause only affected work. Do not invent a cause, expand permissions or label an offline simulation as a live fix. If the existing interface prevents a useful regression check, record that concrete limitation for [architecture.md](architecture.md).
