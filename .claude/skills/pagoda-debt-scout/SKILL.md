---
name: pagoda-debt-scout
description: Inspect Pagoda technical-debt candidates on demand using cognitive complexity and duplicate-code signals. Use after a feature change, before modifying a complex area, or when asked to find safe refactoring opportunities. Do not use as a routine CI or completion gate.
---

# Pagoda Debt Scout

Use the scanners as evidence for investigation, not as an instruction to reduce scores blindly. The desired outcome is at most three concrete maintenance tasks, or a reasoned conclusion that no change is worthwhile.

## Choose the scope

- For a repository inventory, run `npm run debt:report`.
- For machine-readable Python findings, run `npm run debt:complexity:python:json`; read `.cache/debt/complexipy` and apply the threshold during triage because this inventory contains all functions.
- For a feature or branch, resolve the actual base revision first. Prefer the PR base or its merge base over a fixed branch name.
- For an already merged feature, record the feature base, merge commit, and current revision. Check later commits before treating the historical file location as a current candidate.
- For new duplicate blocks, run `npx jscpd --config .jscpd.json --baseline-from-ref <base-ref> --reporters json --output .cache/debt/jscpd-diff .`.
- For changed frontend files, run `npx biome lint --javascript-linter-enabled=true --only=complexity/noExcessiveCognitiveComplexity --changed --since=<base-ref> --max-diagnostics=none --no-errors-on-unmatched frontend/src e2e`.

Biome's changed mode selects files, not newly introduced diagnostics. Complexipy's CLI diff output includes low-value entries and is not a ready-made task list. Compare the relevant functions before and after the base revision when an exact regression claim matters.

Record the base revision, current revision, tool versions, and scan time with the findings. If an existing report's provenance is unknown or its configuration differs, use it only as a hint and rerun before making a regression claim. A jscpd `isNew` value is meaningful only for the baseline used by that scan.

## Review a frontend change with an agent

Start with the component being edited and its existing siblings, including any newly created source files. A scan of only the changed file can miss a copy in an untouched file. Inspect the diff to decide whether either occurrence belongs to this change.

For a PR review, prioritize a clone introduced or extended by the PR. For a maintenance run, select a frequently changed area and include existing clones. Record which mode led to the patch so that a cleanup of historical code is credited to the maintenance run.

The locked jscpd CLI supports both token matches and JS/TS function AST comparison. The following entry-form scan uses the `*Field.tsx` glob to select the widgets.

```sh
npx --no-install jscpd --config .jscpd.json --reporters ai,json \
  --output .cache/debt/entry-form/exact frontend/src/components/entry/entryForm/*Field.tsx
npx --no-install jscpd --config .jscpd.json --similarity 0.90 --kind ast --reporters ai,json \
  --output .cache/debt/entry-form/ast frontend/src/components/entry/entryForm/*Field.tsx
```

Read the compact `ai` console output first. The local JSON report has paths and ranges for individual matches. Use Git history to check whether the two sites have required the same fix before. Check the tests at each caller for cases where their contracts differ. Treat multiple hits inside one pair of widgets as one decision.

When a cleanup was requested, select one candidate. Record the baseline test result, make the patch, rerun the same tests and both scans, then run the usual frontend checks. Include the shared file in the second scan. Report the change in maintenance work (for example, how many places need editing for a selection behavior change), a rejected candidate with its reason, and any failing checks. A review can finish with zero patches.

The [Pagoda pilot](references/pilot.md) records one accepted pair, one rejected pair, and comparisons with similarity and Qlty.

## Triage findings

Prioritize signals in this order:

1. The same recent feature increases complexity and creates duplicate logic.
2. A new function exceeds cognitive complexity 15.
3. An existing function ends above 15 and increases by at least 5.
4. A duplicate block represents a business rule that future changes would otherwise require editing in multiple places.
5. A complex function is about to be changed for another reason and has a separable responsibility.

Group overlapping clone pairs into one maintenance task. Separate production code from tests. Treat imports, type declarations, UI boilerplate, fixtures, and parallel API contract tests as low-priority until their maintenance cost is demonstrated.

For each proposed task, inspect callers, semantic differences, and relevant tests. Never infer that a duplicate was AI-generated from the duplicate alone.

## Decide whether to change code

Scanning must not change tracked source. The commands above write ignored reports under `.cache`; if the task prohibits all filesystem writes, inspect existing reports and source instead. Refactor only when the user requested optimization or the active implementation task clearly includes it.

When refactoring:

- Keep the change to one responsibility and one reviewable patch.
- Preserve caller-specific behavior instead of forcing superficially similar code into one abstraction.
- Add or strengthen characterization tests before changing poorly covered behavior.
- Run the smallest relevant tests and static checks, then report the before/after complexity or duplication evidence.
- Prefer no change when the abstraction would be harder to explain than the duplication.

Do not change CI, hooks, public APIs, ACL behavior, persistence semantics, or test coverage policy without explicit authorization. Do not commit, push, or merge unless the user requests it.

## Report

Return no more than three candidates. For each candidate include:

- location and detected signal;
- why it creates maintenance cost;
- semantic differences that must remain;
- available regression tests;
- estimated impact, risk, and effort;
- recommendation: refactor, investigate, intentionally retain, or delete after reference analysis.

Record intentional or deferred findings by stable function or normalized-fragment identity when the surrounding workflow provides a decision log. Do not repeatedly propose an unchanged rejected candidate.
