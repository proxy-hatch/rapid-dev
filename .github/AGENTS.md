# GitHub workflows

- [workflows/ci.yml](workflows/ci.yml) runs [the shared validation command](../scripts/check.py) on supported Python versions: navigation, the vendored-Kit check (`rapid-ship status --strict`), static checks, tests, a distribution build and the distribution smoke.
- [workflows/docs.yml](workflows/docs.yml) builds documentation for relevant changes and deploys successful main-branch builds.
- [CODEOWNERS](CODEOWNERS) was seeded by `rapid-ship init`, so this repository owns it now. In Walk its one active line, `* @proxy-hatch`, assigns every path to the owner. The Protected set follows, commented out for Flight. GitHub reads the file from the pull request's base branch and requests the owner's review; it blocks a merge only when a ruleset or branch protection requires code-owner review. Edit the login or the Protected set here, not in `rapid_ship/templates`.

Keep pull-request checks separate from deployment permissions.
When adding a build input, update the docs workflow path filters if that input affects the website.
Change Python/repository validation stages in `scripts/check.py` so local runs and CI stay identical.
Keep the distribution smoke after the build; a working checkout does not establish that the wheel ships every template or that the installed `rapid-ship` runs.
Preserve locked dependency installation and the existing per-job permission boundaries.
Run the affected workflow's commands locally where supported; report hosted matrix and deployment checks separately from local results.
