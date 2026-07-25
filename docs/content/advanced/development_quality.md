# Development Experience and Internal Quality Report

Date: 2026-07-25

## Outcome

Pagoda now has five additional, stack-specific safeguards. They complement the
existing Ruff, mypy, Jest coverage, and Playwright gates instead of replacing
them:

1. a mandatory fast completion gate for AI agents;
2. executable Python architecture contracts;
3. a zero-warning OpenAPI contract;
4. a production JavaScript bundle-size budget; and
5. a reproducible one-command cross-stack quality gate.

`npm run quality:fast` runs the repository-wide fast profile used by AI agent
hooks.
`npm run quality:full` runs the cross-stack review profile.

## Selection method

Candidates were scored for defect prevention, feedback speed, fit with the
Django/DRF and React/TypeScript stack, maintenance cost, and incremental
adoptability. The implementation follows established practices from
[Cookiecutter Django](https://github.com/cookiecutter/cookiecutter-django),
[pre-commit](https://pre-commit.com/),
[Import Linter](https://import-linter.readthedocs.io/en/latest/),
[webpack](https://webpack.js.org/configuration/performance/), and
[GitHub code scanning](https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-code-scanning).

| Rank | Measure | Prevention | Feedback | Maintenance | Current evidence |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | AI agent completion gate | High | High | Low | All tracked files pass in 6.67 s |
| 2 | Architecture contracts | High | High | Low | 343 files and 994 imports checked |
| 3 | Strict OpenAPI | High | Medium | Low | Warnings reduced from 1 to 0 |
| 4 | Bundle budget | Medium | Medium | Low | Raw and gzip budgets pass |
| 5 | Cross-stack full gate | High | Medium | Low | Backend and frontend suites pass together |

## 1. AI agent completion gate

Codex and Claude Code use repository-local `SessionStart` and `Stop` hooks. The
session hook records the initial worktree fingerprint. If the fingerprint
changes, the stop hook runs `tools/quality_fast.sh`; a failure is returned to
the agent and blocks successful completion until it changes the worktree and
the gate passes.

`.pre-commit-config.yaml` remains the tool runner behind the fast gate. It runs
Ruff lint and format for Python, Biome for JavaScript/TypeScript, verifies
`uv.lock`, and checks Python architecture contracts. It is not installed as a
mandatory human Git hook.

The all-file benchmark passed in 6.67 seconds. Normal commits check fewer files,
so their feedback path is shorter. The hooks use the repository's existing
tools and environments; they do not create a second formatting or linting
policy.

Expected effect:

- formatting and simple lint failures are repaired by the agent before handoff;
- stale `uv.lock` changes cannot be handed off as completed work;
- `npm run quality:fast` gives humans and agents the same reproducible entry
  point.

## 2. Executable architecture contracts

`.importlinter` introduces two enforced boundaries:

- the plugin SDK cannot add direct dependencies on Pagoda core; and
- API v2 modules cannot add dependencies on API v1 modules.

The existing intentional adapters are explicit debt: three lazy task imports
from the SDK and one `entry.api_v2` import from `api_v1`. New exceptions require
an explicit contract change and review.

The current graph contains 343 Python files and 994 imports and builds in
0.018 seconds once the tool starts. A fault-injection test added a forbidden
`pagoda_plugin_sdk -> airone` import; `lint-imports` exited 1 and reported the
exact import line. The probe was then removed and both contracts passed.

Expected effect:

- prevents invisible coupling during ongoing API and plugin work;
- makes architectural intent reviewable as code;
- bounds existing debt without requiring a disruptive refactor first.

## 3. Zero-warning OpenAPI contract

The previous CI script failed only on a grep pattern and allowed schema warnings.
The baseline had one warning caused by an anonymous serializer for user
activity. `UserActivitySerializer` now describes the response and the endpoint
declares its list response explicitly.

CI now runs:

```shell
DJANGO_CONFIGURATION=DRFSpectacularExcludeCustomView \
  uv run python manage.py spectacular --fail-on-warn
```

The strict command passes with zero warnings and generates a 130,933-byte
schema. This follows drf-spectacular's recommended
[schema customization workflow](https://drf-spectacular.readthedocs.io/en/latest/customization.html).

Expected effect:

- prevents warning accumulation from degrading generated TypeScript clients;
- turns API documentation drift into an immediate, actionable CI failure;
- removes brittle parsing of human-readable command output.

## 4. Production bundle-size budget

`npm run quality:bundle` builds the production bundle and measures both raw and
gzip size. Both matter: raw size captures parse/compile pressure while gzip size
approximates transfer cost.

Current measurements:

| Metric | Current | Budget | Used |
| --- | ---: | ---: | ---: |
| Raw | 1,710,543 bytes | 1,800,000 bytes | 95.0% |
| gzip | 489,552 bytes | 520,000 bytes | 94.1% |

A fault-injection test lowered the limits below the current bundle. The checker
exited 1 and reported overruns of 10,543 raw bytes and 9,552 gzip bytes. The
normal budgets then passed. The frontend CI build now runs this gate.

Expected effect:

- makes bundle growth visible at the pull request that introduces it;
- protects load and JavaScript parse cost from gradual regression;
- creates a concrete trigger for code splitting rather than relying on webpack
  warnings that currently do not fail CI.

The small remaining headroom is intentional: the current bundle is already
large. The next optimization should split routes or large dependencies, then
lower both budgets to the new measured baseline.

## 5. One-command cross-stack quality gate

`npm run quality:full` now runs the lockfile, Python lint and format, mypy,
architecture contracts, strict OpenAPI generation, frontend lint, the complete
Jest suite, and the production bundle budget in a fixed order.

Observed effect:

- one command reproduced the checks used across the backend and frontend;
- the complete run passed with 148 Jest suites, 801 passed tests, 2 skipped
  tests, and 30 passing snapshots;
- backend type checking passed across 389 source files; and
- the gate preserves the original failure code, so an agent or CI runner cannot
  report success after an earlier stage failed.

The Jest run still prints existing React `act`, Suspense, and invalid
DOM-property console messages. They do not fail the current suite, so converting
those warnings into a clean-console policy is a useful follow-up rather than
being silently treated as completed here.

## Additional safeguard: security and dependency-change gates

`.github/workflows/security.yml` adds:

- CodeQL `security-extended` analysis for Python and JavaScript/TypeScript on
  pushes, pull requests, and a weekly schedule; and
- dependency review on pull requests, failing when a newly introduced
  dependency has a high or critical known vulnerability.

Actions are pinned to immutable commit SHAs. The workflow YAML parses locally.
This is intentionally outside the top-five verified ranking: the GitHub-hosted
analysis result becomes authoritative after the workflow runs, and local
validation cannot substitute for GitHub's dependency graph and code scanning
service. GitHub documents both
[CodeQL's supported languages](https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-code-scanning)
and how
[dependency review blocks vulnerable additions](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review).

Expected effect:

- catches data-flow vulnerabilities beyond syntax and type checking;
- blocks new vulnerable transitive dependencies at review time;
- rescans unchanged code as the query and advisory databases improve.

## Candidates tested but not selected

### Type-aware ESLint

`@typescript-eslint/no-floating-promises`,
`no-misused-promises`, and `await-thenable` found 130 errors, but increased a
full frontend lint run to 24.40 seconds. Enabling all three as errors now would
block unrelated work and encourage blanket suppressions. The right follow-up is
to burn down the existing promise findings feature by feature, then enable the
official
[typed linting preset](https://typescript-eslint.io/getting-started/typed-linting/)
as a ratchet.

### Fail-on-console Jest policy

The full test suite passes, but several tests emit React `act`, Suspense, and
invalid DOM-property warnings. A console-clean policy would improve signal
quality, but should first land with targeted fixes or a reviewed baseline so it
does not turn pre-existing noise into an unbounded migration.

### Django deployment checks

`manage.py check --deploy` reported 33 issues in the local configuration. Most
were legacy schema warnings or environment-specific proxy/TLS settings, so
making the command fatal today would be noisy and could encourage unsafe global
silencing. It should be revisited with an explicit production-settings fixture.
Django notes that deployment checks must be invoked explicitly because they are
not run in the WSGI stack
([system check framework](https://docs.djangoproject.com/en/5.2/topics/checks/)).

### Mutation testing

Mutation testing offers strong test-quality evidence but has a poor first-step
cost on this database-heavy Django suite. It should be trialed later on pure
validation and serializer modules after collecting a stable runtime baseline.

### Storybook and broad visual regression

Both can improve component review, but they add a second fixture and snapshot
maintenance surface. Existing Testing Library and Playwright approval gates
already cover more immediate risks. Add focused visual baselines only for
stable, high-value screens.

## Operating rules

- AI agents must not bypass the repository `Stop` hook.
- Human contributors can run `npm run quality:fast` without installing a Git
  hook.
- Run `npm run quality:full` before requesting review.
- Do not increase bundle budgets to make a pull request pass without a measured
  and documented reason.
- Prefer removing architecture exceptions; adding one requires explaining why
  the dependency cannot point in the intended direction.
- Keep OpenAPI warnings at zero. Annotate the endpoint or serializer rather than
  weakening `--fail-on-warn`.
- Review weekly CodeQL findings and keep action SHAs current through dependency
  update automation.
