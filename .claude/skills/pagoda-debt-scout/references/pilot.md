# Agent-assisted code review in Pagoda

Local pilot on 2026-11-21 JST. The starting revision was `5df41d3a`. The frontend comparison used that revision and the working tree after refactoring the group and role entry widgets. The Python comparison used the same starting revision and its first parent, `8e41f1a5`.

## Frontend outcome

The two widgets had separate implementations of autocomplete, fuzzy filtering, loading, selection, dirty state and validation. For example, commit `6b90ac25` added fuzzy matching to both widgets. A shared field now handles those behaviors. The group adapter still reads page 1 of a paginated response. The role adapter still reads a list. The existing component entry points, labels, form keys and SWR cache keys are preserved. Their combined implementation went from 322 lines in two files to 195 lines in three.

| Detector | Before | After | Matches involving the selected widgets |
| --- | ---: | ---: | --- |
| jscpd 5.3.0, repository token thresholds | 12 | 10 | Two blocks of 39 and 54 lines disappeared |
| jscpd 5.3.0, AST only, similarity at least 0.90 | 14 | 13 | One function pair disappeared |
| similarity-ts v0.5.0, functions only, similarity at least 0.90, minimum 8 lines | 2 | 1 | The pair of selection handlers scored 100% and disappeared |

These are tool-reported pairs or blocks. Several reports can describe one maintenance task. Both scans included the same component subtree and the second scan included the new shared file. The input grew from 120 to 121 TS/TSX files. jscpd counted 111 then 110 sources under its size filters. Its reported duplicated lines for token matches fell from 364 to 273.

The other similarity-ts match scored 90.14%. One function selects autocomplete options and the other schedules DOM focus after inserting a row. They have different callers, effects and reasons to change. Combining them would offer no shared behavior. These two decisions describe the reviewed sample.

The same 24 Vitest cases passed against both implementations, including selection in single and multiple modes, translated captions, and a full-width query with zero server matches that falls back to local filtering. For the comparison, the original widgets were loaded directly from Git. Both runs used the strengthened test and a role-list mock that matches the test server's port. Both used Node 22.23.4, one worker and a 30-second test timeout. Dependencies were copied from a local checkout with an identical npm lockfile. The development build, frontend type check and lint command passed locally.

The initial full coverage run used four workers. Of 1,133 tests, 1,080 passed, 51 failed and two were skipped. There were 46 five-second timeouts, four assertion failures and one role-list request that missed the mock. After the mock fix, a one-worker run of the widgets and both suites containing the four assertion failures passed all 36 tests at the default timeout. A separate two-worker rerun without coverage used a 30-second timeout and passed all 51 originally failing cases, matched by file and full test name. The final full run with coverage passed all 161 test files in 202.89 seconds on two workers with the same 30-second timeout. It recorded 1,131 passes, two skips and zero failures. Line coverage was 73.30% and branch coverage was 63.30%. These results were collected locally.

## Which tool earns its place?

| Tool | Evidence from this checkout | Adoption decision |
| --- | --- | --- |
| jscpd | Both existing token detection and optional AST comparison found the useful pair. On the post-change AST run, the console output from the `ai,json` reporters was 901 bytes and the JSON file was 41,006 bytes. | Use the locked dependency. Give the agent the console summary and let it retrieve source ranges as needed. |
| similarity | The official v0.5.0 release was checked against the GitHub release digest. The TS tool found the same useful pair and one unrelated pair. The Python tool returned 21 pairs across three files at 0.90, including import and export jobs with different responsibilities. | Optional second opinion. Upstream describes TS as production-ready and Python as beta. [Upstream status](https://github.com/mizchi/similarity/tree/v0.5.0) |
| Qlty CLI | Version 0.566.0 scanned copies of three Python files in an isolated Git repository, with telemetry and upgrade checks disabled. SARIF contained 3 file complexity, 21 function complexity, 14 return-count and 2 similar-code results. The latter referred to the two sides of one 15-line group/role history serialization pattern. jscpd reported zero blocks at the repository's 20-line minimum on these files. | Use on demand when smaller structural matches or SARIF matter. Confirm the cost of changing both sites and the scope of the diff. The test exercised local `smells`. [Qlty duplication](https://docs.qlty.sh/duplication) |
| Complexipy and Biome | Complexipy 8.0.1 scored `EntryRetrieveSerializer::get_attrs` at 95 in both revisions. In the same three-file sample, the new `rollback_bulk_update_entries` scored 24 and `ItemRollbackAPI::post` fell from 76 to 19. | Keep the existing complexity checks. Compare scores for the same function against the base before assigning work. Biome also selects whole files in changed mode. [Biome VCS integration](https://biomejs.dev/guides/integrate-in-vcs/) |
| Knip | The frontend lint command already includes Knip. Its fixes can remove exports and dependencies. | Inspect entry points and plugin consumers for each removal. [Knip auto-fix](https://knip.dev/features/auto-fix) |
| SonarQube Cloud | Documentation review only. The built-in agentic AI gate sets new-code coverage at 80% or higher and duplication at 3% or lower. It supports a shared policy across projects. | Consider when cross-repository reporting and central policy justify service integration. [SonarQube agentic AI quality gate](https://docs.sonarsource.com/sonarqube-cloud/standards/ai-code-assurance/quality-gate-for-agentic-ai) |

Qlty's engine fingerprints syntax trees while discarding literal details. Its CLI and its hosted AI features have separate operational requirements. The existing agents can run CLI checks directly. [Qlty agent integration](https://docs.qlty.sh/cli/coding-with-ai-agents)

## Reproduce the comparison

The frontend sample comprised Git-listed `.ts` and `.tsx` files under `frontend/src/components`, excluding filenames matching `\.test\.|credential|secret|password|token|privatekey|api.?key` case-insensitively. Include untracked source files when testing a working-tree refactor. Pass the resulting files as separate arguments. The focused entry-form commands in the [skill](../SKILL.md) are sufficient to investigate this example.

- For token matches, use `--config .jscpd.json --reporters ai,json`.
- For AST matches, add `--similarity 0.90 --kind ast` and use a different output directory. The pinned 5.3.0 CLI supports JS/TS function comparison. [jscpd documentation](https://jscpd.dev/)
- For an independent comparison, use `similarity-ts --no-types --threshold 0.90 --min-lines 8`.
- The Python input consisted of `entry/tasks.py`, `entry/api_v2/serializers.py` and `entry/api_v2/views.py`. Supply the same files to `similarity-py --threshold 0.90 --min-lines 8`, jscpd, and Complexipy. For the Qlty pilot copy them into an isolated repository with a minimal `.qlty/qlty.toml` containing `config_version = "0"`, add the files to Git, and run `QLTY_TELEMETRY=off qlty smells --no-upgrade-check --no-snippets --sarif entry`. [Qlty telemetry](https://docs.qlty.sh/cli/telemetry)

For a separate baseline control, the two original widget files were committed to a temporary repository. jscpd reported two existing blocks and zero new ones against its HEAD. Adding an exact third copy of the group widget and rescanning against the same HEAD produced three blocks and one new block. The frontend pilot above reports absolute counts on identical scopes, so it also captures removals.
