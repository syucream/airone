---
title: Import and regular expression limits
---

# Import and regular expression limits

Pagoda limits YAML expansion and regular expression evaluation to protect
worker resources. Requests exceeding these limits return HTTP 400.

## YAML imports

These limits apply to API imports and import previews, including the common
import endpoint and role imports. Legacy entry, dashboard, and user/group
imports use the same loader.

| Resource | Limit |
| --- | --- |
| Input size | 10 MiB |
| Expanded scalar content, encoded as UTF-8 | 10 MiB |
| Source nodes and expanded nodes | 100,000 |
| Source nesting and expanded nesting | 64 levels |
| Numeric scalar length | 4,300 characters |

Ordinary anchors, aliases, and merge keys remain supported within these
limits. Recursive aliases are rejected. Expansion limits count each alias
reference, including references in unknown fields, before constructing Python
objects or serializing job parameters. Expanded node counts include mapping
keys and collection nodes, as well as scalar values.

The scalar limit measures YAML content before JSON escaping. JSON output can
therefore be larger than 10 MiB. Legacy upload handlers still read and decode
the uploaded file before invoking the loader; the loader limits parsing and
expansion rather than upload buffering.

## Entry name patterns and legacy text search

Entry name validation and `POST /entry/api/v1/search_entries/<entity_ids>`
use time-limited regular expression matching. Python regular expression
syntax, including lookarounds and backreferences, remains supported within
the following limits. Matching uses the `regex` package in VERSION0 mode;
Unicode character classifications can differ from the standard `re` module.

| Resource | Limit |
| --- | --- |
| Pattern length, including the legacy search's `.*` prefix | 1,024 characters |
| Text length for one match | 1,000,000 characters |
| Finite repetition expansion | 10,000 |
| Cumulative regex CPU time for one validation or search request | 0.1 seconds |

The CPU budget includes compilation and matching but excludes database queries.
Compilation is bounded by the length and complexity limits; its CPU use is
charged after it finishes. Each match also has a timeout. Finite repetitions
are checked before compiling the timeout-capable matcher, including nested
repetitions and repetitions inside lookarounds. The normal entity create/update
API rejects oversized or invalid name patterns. Imports can still store such
patterns, but entry name validation rejects them before matching. A match that
exhausts the time budget returns a validation error.

Entry name validation keeps prefix matching. Legacy text search keeps its
existing `.*` prefix and regular expression behavior; search input is not
converted to literal text.

## Regression checks

The YAML tests cover expanded aliases, merge keys, cycles, limit boundaries,
and rejection before validation or job serialization at import endpoints.
The regular expression tests exercise both affected APIs, valid Python syntax,
compile expansion, invalid stored patterns, and a shared search budget.
Dangerous regular expressions run in disposable subprocesses with an outer
timeout so a regression fails the test instead of hanging the suite.

Run the focused checks with:

```sh
tools/lite.sh test airone.tests.test_yaml airone.tests.test_yaml_import \
    airone.tests.test_regex entry.tests.test_regex_validation
```

These tests are also discovered by the existing per-app CI test jobs.
