# Tests that catch behavior changes

Use the public interface and acceptance cases already approved for the task. Existing agreement is sufficient; do not ask the user to approve each test boundary again. If the interface itself is materially ambiguous, use [clarify.md](clarify.md); consult [design.md](design.md) for a genuine design trade-off.

For a behavior change, work in small cycles:

1. Add one test for the next observable behavior or reported defect. Derive the expected result independently from acceptance, a known example or the specification.
2. Run it and inspect the failure. Confirm it fails because the behavior is missing or wrong, not because setup is broken. If the regression is already covered, use that failing test.
3. Implement only enough to make it pass. Run the focused tests, then repeat for another necessary behavior.
4. Run the required checks on the final change. Simplify when useful while preserving behavior; avoid unrelated restructuring.

Test through interfaces callers use. Prefer real components and temporary test resources; substitute external services, time or randomness where necessary. Do not mock internal collaborators merely to assert call order. A passing mock is not a live integration trial.

Avoid assertions that reproduce the implementation, private-helper tests that only enforce structure, and tests for speculative functionality. Retain useful existing coverage. For mechanical documentation or low-impact edits, use the relevant validator instead of inventing a unit test.

A defect check must fail on the original bug and pass on the fix. If no practical test can observe the defect, report that limitation rather than claiming coverage.
