# GitHub workflows

- [workflows/ci.yml](workflows/ci.yml) runs [the shared validation command](../scripts/check.py) on supported Python versions: navigation, static checks, tests, a distribution build and the distribution smoke.
- [workflows/docs.yml](workflows/docs.yml) builds documentation for relevant changes and deploys successful main-branch builds.

Keep pull-request checks separate from deployment permissions.
When adding a build input, update the docs workflow path filters if that input affects the website.
Change Python/repository validation stages in `scripts/check.py` so local runs and CI stay identical.
Keep the source-distribution smoke after the build; a working checkout wheel does not establish that the archive retains its resources.
Preserve locked dependency installation and the existing per-job permission boundaries.
Run the affected workflow's commands locally where supported; report hosted matrix and deployment checks separately from local results.
