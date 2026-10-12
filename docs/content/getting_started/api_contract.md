---
title: Local API contract checks
weight: 26
---

# Local API contract checks

Compare the public APIv2 schema at a Git merge base with the schema generated
from your working tree, including staged, unstaged, and untracked Python source
changes. The command produces an agent-readable JSON report, a Markdown report,
and the exact input schemas and raw differences. It does not generate a
TypeScript client or change CI/publication behavior.

## Setup and use

Use the repository's Python development environment. No containers, database,
private API client package, Java, Go compiler, or registry credentials are
required. The explicit installation step needs access to GitHub:

```sh
uv run --locked python tools/api_contract.py install
uv run --locked python tools/api_contract.py check --base-ref upstream/master
```

The installer downloads **oasdiff 1.33.0**, verifies the archive against a
committed SHA256, and installs only its executable under
`.cache/api-contract/bin/oasdiff`. macOS (Intel/Apple Silicon) and Linux
(amd64/arm64) are supported. Checks never download or upload schemas. For a
preinstalled executable, use `--oasdiff /absolute/path/to/oasdiff`; its version
must match the pinned version. The report records the binary hash as well.

Choose the target branch explicitly. The command compares
`git merge-base <base-ref> HEAD` with the working tree, not necessarily the
target branch tip or GitHub's synthetic merge commit. It does not fetch:
refresh remote refs yourself when appropriate. To examine edits since your
last commit, use `--base-ref HEAD`.

```sh
# JSON only on stdout; subprocess diagnostics are captured in evidence files.
uv run --locked python tools/api_contract.py check \
  --base-ref upstream/master --format json

# Preserve evidence in a chosen NEW directory. Existing output is never reused.
uv run --locked python tools/api_contract.py check \
  --base-ref HEAD --output-dir /tmp/my-api-contract-review
```

The default output is `.cache/api-contract/<UTC-time>-<run-id>/`. Each invocation
has a fresh directory, including failed checks. `--timeout` bounds each schema
generator and oasdiff subprocess (120 seconds by default), not the whole run.

## Interpretation

| Status | Meaning | Exit code |
| --- | --- | --- |
| `compatible` | No consumer-impact error/warning detected in the declared contract | 0 |
| `review_required` | oasdiff found changes whose compatibility needs review | 0 |
| `breaking` | oasdiff found a declared-contract breaking change | 1 |
| `error` | The comparison could not be completed reliably | 2 |

`compatible` does **not** mean the implementation, permissions or deployment
are proven compatible. Description-only changes remain visible in `diff.json`
and `has_changes`, even when the consumer-impact findings are empty. Additive
changes appear as non-breaking findings where supported by the pinned engine.
Severity depends on request/response direction and the precise schema rule;
do not classify every removed property or new enum value identically.

On `error`, counts and `has_changes` are `null`, never a false zero. An error
contains the failed stage and an actionable message. Errors before creating an
output directory (for example, an existing `--output-dir`) are returned on
stderr and, with `--format json`, as a JSON setup-error envelope on stdout.
Argument usage errors use argparse's normal exit code 2 and diagnostics.

## Evidence and JSON contract

`report.json` has `schema_version: 1`. Consumers should reject unsupported
versions and check `status` before interpreting counts. The fields include:

- `comparison`: requested base, resolved merge-base SHA and HEAD SHA,
  dirty-tree flag, aggregate source digests, changed source paths, included
  untracked files, file counts and schema settings policy/hash. Full per-file
  hashes and excluded paths are in `comparison.json`.
- `environment`: Python version and installed-distribution digest. Full
  distribution names/versions are in `environment.json`. Both source snapshots
  use this same environment.
- `engine`: exact oasdiff version, executable/configuration SHA256 and flags.
- `generation`: input schema digests, warning counts and log paths.
- `summary`: counts for `breaking`, `review_required`, `non_breaking`.
- `findings`: stable diagnostic ID, engine rule ID, severity, HTTP method,
  path, message, arguments, schema section and index into `findings.json`.
- `has_changes`: whether the complete schema diff is nonempty.
- `error`: failed stage/message or `null`.
- `artifacts`, `output_dir`, `limitations`, `duration_seconds`, `run_id`, `exit_code`.

The primary report intentionally contains summaries and pointers rather than
duplicating hundreds of file hashes/package records in an agent's context.
Read the manifests only when investigating reproducibility or excluded input.

Findings link back to the engine's raw evidence rather than inventing a Python
source line. The raw diff supplies before/after detail where the engine emits
it. Diagnostic IDs ignore temporary source file locations; a rule/tool update
can still change them and must be reviewed together with the pinned version.

The evidence directory contains `report.md`, `report.json`, `comparison.json`,
`environment.json`, `base.openapi.json`, `head.openapi.json`, generation logs,
`diff.json`, and `findings.json`. Failed runs retain only artifacts produced
before failure. The JSON error envelope is authoritative even when an earlier
schema artifact exists. Reports are local artifacts, not committed API baselines.

## Generation boundaries

The wrapper creates source-only snapshots in a temporary directory. Relevant
tracked and non-ignored untracked `.py`/`.html` files are copied. Deleted tracked
files remain deleted in the head snapshot. Symlink sources fail explicitly.
Concurrent changes while assembling snapshots are rejected; later edits are
not part of an already captured snapshot. Match source digests when reusing
evidence after an edit.

Deployment `.env`/credential/key files, ignored sources, and local
`airone/settings.py` are not copied or read. The generated settings subclass
`Common`, preserve its schema hooks, and append the public-client exclusion
hook. SQLite in-memory, in-process search, and a memory broker are selected;
external plugins are disabled. Tracked `custom_view_sample` is installed as
`custom_view`, matching the repository's core CI setup. The child process uses
a small fixed environment and the snapshot's plugin SDK sources. Python runs
with `-I -S` and explicit installed library directories, bypassing `.pth` and
editable-install hooks that could otherwise import a different checkout after
a source file is deleted. Editable third-party dependencies are consequently
unsupported by this isolated generation environment.

oasdiff also runs with an explicit empty configuration, fixed flags, a temporary
working directory and a minimal environment. User `.oasdiff.*` files and
`OASDIFF_CONFIG` cannot suppress findings or change severity silently.

This is process/source isolation, **not a sandbox for malicious Python code**.
Schema generation imports the selected source revision. Run it only for code
you would otherwise execute locally.

Malformed/empty schemas, external references, generation error diagnostics,
unsupported engine versions, nonzero engine exits and malformed engine JSON
fail closed. Schema warnings are retained in the logs and counted; they do not
by themselves make a comparison fail.

Local deployment settings, ignored custom extensions and non-Python schema
input resources are outside the supported source snapshot. If a module needs a
missing resource, generation should fail; the wrapper never substitutes a
previous generated schema. The exclusion inventory explains the comparison
scope. Both revisions run under the current dependencies, so changes caused
solely by upgrading the generator or dependency environment need a separate
released-schema comparison. This check is not a substitute for behavioral
tests, published-client verification or actual MySQL/ES/worker tests.

## Maintenance and tests

The pin and platform checksums live in `tools/api_contract_support/engine.py`.
Update them together after inspecting the official release, exercise the JSON
adapter against the actual new binary, and rerun the meaningful change/failure
cases. Do not silently relax severity rules or suppress findings to make a
breaking API edit pass.

```sh
uv run --locked python -m unittest \
  tools.tests.test_api_contract \
  tools.tests.test_api_contract_engine \
  tools.tests.test_api_contract_snapshot
```

The tests exercise working-tree/new-file/deletion behavior, diagnostic identity,
failure reporting, binary version/JSON validation, and checksum/archive handling.
They use temporary repositories and fake executables for failure injection;
release validation should additionally run the pinned binary against real
Pagoda schemas and deliberate changes in a disposable checkout.

An opt-in integration test performs that real-schema journey, including a
removed endpoint, new required input, changed property type, description-only
edit, untracked endpoint and generation failure:

```sh
PAGODA_CONTRACT_INTEGRATION=1 uv run --locked python -m unittest \
  tools.tests.test_api_contract_integration
```

It needs the installed pinned binary and a working Python dependency environment.
It never changes the original API sources. Evidence is retained under
`.cache/api-contract/`, including `integration-results.json`. The fast engine
tests also exercise a real-binary configuration-contamination regression when
the local pinned binary is installed; otherwise that one case is skipped.

Sources:

- [Pinned oasdiff release](https://github.com/oasdiff/oasdiff/releases/tag/v1.33.0)
- [Breaking changes and output formats](https://github.com/oasdiff/oasdiff/blob/v1.33.0/docs/BREAKING-CHANGES.md)
- [drf-spectacular schema customization](https://drf-spectacular.readthedocs.io/en/latest/customization.html)
