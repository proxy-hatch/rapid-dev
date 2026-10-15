# GitHub workflows

- [workflows/devctl-check.yml](workflows/devctl-check.yml) is the managed Kit workflow. It installs gitleaks, then runs `./devctl check --tier full`, the same command as a local full check; the `python-3.12` step covers the oldest supported Python. Change it only through its template, `rapid_ship/templates/common/.github/workflows/devctl-check.yml`, then sync.
- [workflows/docs.yml](workflows/docs.yml) builds documentation for relevant changes and deploys successful main-branch builds.
- [CODEOWNERS](CODEOWNERS) was seeded by `rapid-ship init`, so this repository owns it now. In Walk its one active line, `* @proxy-hatch`, assigns every path to the owner. The Protected set follows, commented out for Flight. GitHub reads the file from the pull request's base branch and requests the owner's review; it blocks a merge only when a ruleset or branch protection requires code-owner review. Edit the login or the Protected set here, not in `rapid_ship/templates`.

Keep pull-request checks separate from deployment permissions.
When adding a build input, update the docs workflow path filters if that input affects the website.
Preserve locked dependency installation and the existing per-job permission boundaries.
Run the affected workflow's commands locally where supported; report hosted runs and deployments separately from local results.
