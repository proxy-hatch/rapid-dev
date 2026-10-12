# Trial evidence

This directory records observations and reproduction artifacts, including unsuccessful probes.
[2026-10-11-runtime-comparison.md](2026-10-11-runtime-comparison.md) links the frozen runtime bundles and their checksums.
The selected integration decision belongs in [runtime-choice.md](../runtime-choice.md).

Record the tested versions, conditions, commands, results, and limits for each trial.
Identify deterministic simulations, live provider calls, and later reruns separately.
Preserve the relationship between each report, its saved artifacts, and the revision actually tested.
When replacing an artifact, update its recorded checksum and explain which observations the replacement reproduces.
Check bundles for credentials and private paths before publication; the website publishes these reports.
Passing unit tests or one successful probe does not qualify unattended delivery.
