---
title: Agent code review
weight: 35
---

The implementing agent owns the repair loop. Start with a user-visible outcome and
an observable failure case from the request. Keep these criteria across attempts.
For behavior changes, pick an acceptance command before implementing. It should
exit nonzero on the wrong result. An existing regression test, Playwright scenario,
or trusted black-box check supplied outside the checkout can serve this purpose.

## Review a candidate

Use a local topic branch and commit the complete candidate. From the repository
root, pass the actual PR target and the original acceptance criteria. For example,
with a configured upstream remote and an advanced search change:

```sh
python3 -m tools.agent_review --base upstream/master \
  --intent 'An advanced search using the duplicate-value filter returns all matching entries once.' \
  --scenario tools/lite.sh test entry.tests.test_service.AdvancedSearchServiceTest.test_search_entries_with_duplicated_filter_key
```

The command needs Python, Git, and an authenticated Codex CLI supporting
`exec --ephemeral --output-schema`. Install the development dependencies with `uv sync --frozen --extra dev` using
a supported stable Python version. Frontend and client-generation checks also
need the project's npm dependencies. Run in your trusted development checkout.
Each attempt starts one model session using your Codex authentication. All
selected check commands execute locally with the invoking user's permissions.
Use your own acceptance command or one supplied by a trusted maintainer.

1. The runner resolves the target and candidate to commits, computes their common
   ancestor and checks the worktree is clean. All candidate commits are reviewed.
2. Changed paths select existing repo commands. Python changes run Ruff. Django
   changes run Lite by app, frontend changes run lint, type checks and Vitest,
   and mock E2E changes build the bundle and run Playwright. API definitions, model fields, generator inputs
   and committed client changes regenerate to a temporary directory and compare the
   output to the checked-in client. Every candidate
   gets a Git whitespace check. For Lite tests the runner points Django at the
   candidate SDK and temporarily links the tracked sample as `custom_view` (as in
   CI). Use a checkout with test settings, a free `custom_view` path or a link to
   that sample, and no local `.env`. Django generates initial migrations in the attempt's
   own directory before the first targeted Lite command. Repeat reviews start
   from the candidate models even if the checkout has older migration files. The optional `--scenario` consumes the remaining
   command arguments and runs after the selected checks.
3. A fresh, read-only reviewer reads the diff, callers, and tests against the
   intent. It selects an additional edge case and records what it observed.
   A failed command, an incomplete review, or a moving candidate blocks readiness.

Use the normal entry point for the scenario. For a UI change, drive the affected
control in a browser. For a schema change, regenerate the committed client and
verify it before reviewing. For live integrations, use the dedicated stack and
the instructions in `e2e/live/README.md`. Live E2E paths select static checks
automatically. Supply the live scenario separately. Lite search ranking and the
mock browser API have different fidelity from the real stack. Report which ran.

## Close the loop

| Exit | Report status | Implementing agent's action |
| --- | --- | --- |
| 0 | `passed` | Check the recorded HEAD is the PR head. Cite the acceptance result and reviewer observation in the PR. |
| 1 | `changes_requested` | Reproduce each finding. Fix confirmed defects and retain a regression case where practical. For a false positive, add verifiable counterevidence to the test or criteria. Commit and repeat the same review. |
| 2 | `blocked` | Inspect the failed command or reviewer log. Repair the cause and rerun, or report the exact unavailable prerequisite. |

Use at most three review rounds per candidate task. If the same finding persists
without new evidence or the budget is exhausted, report the outstanding finding
and its reproducer. Keep the original acceptance conditions when adding a test.
A clean local review is evidence for a PR. Record GitHub checks separately.

The latest result is `.artifacts/agent-review/report.json`. Each invocation keeps
its command logs, durations, base and head SHAs, and structured verdict under
`.artifacts/agent-review/run-*/`. Use these records to compare discovered
regressions, repeat findings, review rounds, and elapsed time across PRs.
Record defects found later by CI or human review to evaluate what the loop misses.

For a compatibility fix, run the same small reproducer on the target's merge
base and the candidate. Compare the observable result, including saved state.
If a worker can load older jobs, exercise a stored input as well as the public
request. After a repair, try a neighboring case outside the implementation's
new test, such as an omitted field versus an explicit null.

## Design references

The independent review and reproducible findings adapt the
[pstack interrogate workflow](https://github.com/cursor/plugins/blob/main/pstack/skills/interrogate/SKILL.md).
The acceptance scenario and repair loop follow the
[StrongDM Software Factory principles](https://factory.strongdm.ai/principles).
A scenario maintained outside the implementation checkout can act as a holdout.
Repository tests and cases described to the implementer are visible checks.
The implementation reuses Codex CLI and Pagoda's existing gates. StrongDM
publishes [Attractor](https://github.com/strongdm/attractor) as a specification
for building a full orchestration runtime. The coding session already provides
the orchestration needed for this local loop.
