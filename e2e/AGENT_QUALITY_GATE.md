# Agent approval quality gate

This gate is a local stopping condition for agent-led development. It does not configure or
require CI. A change is approvable only when the deterministic browser check and the selected
live-stack integration check both pass without waivers.

## Commands

- `npm run e2e:install`: install Chromium. This is an explicit environment setup step.
- `npm run e2e:client:generate`: regenerate and link the API client. This is an explicit source
  generation step.
- `npm run e2e:mock`: run the browser suite against the deterministic mock server without building.
- `npm run e2e:mock:full`: build the frontend and run the browser suite.
- `npm run e2e:live`: run the curated Django integration suite against local MySQL and
  Elasticsearch. The services must already be listening on ports 3306 and 9200.
- `npm run e2e:approval`: run both gates and emit one approval decision.

The final machine-readable decision is
`e2e/test-results/approval/gate-manifest.json`. Browser details are in
`approval-manifest.json`, `report.md`, the Playwright JSON/HTML reports, screenshots, traces,
videos, and attached metadata. An agent must treat a missing manifest, `reject`, a failed check,
or a non-empty waiver list as a reason to continue working or escalate.

## Covered risks

The deterministic browser layer runs 19 scenarios for UI rendering, CRUD, all 18 attribute
types, administration, advanced-search criteria, accessibility, viewport overflow, console and
page errors, failed requests, and local API/static HTTP errors. The live-stack layer runs 18 tests
using Django, MySQL, and Elasticsearch for:

- create, retrieve, and update round trips for all 18 public attribute types;
- readonly-user create, retrieve, update, delete, import, and restore boundaries;
- deletion of an entity that still owns an active entry;
- advanced-search filtering, joins, sorting, paging, and permission behavior.

## Measured local run

On 2026-07-13, the combined gate approved this branch in 137.9 seconds: 55.7 seconds for frontend
build plus 19 browser scenarios, and 82.2 seconds for migration preparation plus 18 live-stack
tests. The browser test body itself took 37.0 seconds and retained 13 evidence artifacts.

During stabilization, the gate rejected four gate defects before producing an approval:

- an internal enum flag was incorrectly counted as a public attribute type;
- advanced-search `count` was mistaken for the paged result length;
- a group-row locator assumed an incorrect HTML element;
- accessibility ran while a transient progress indicator was still present.

This was useful feedback: the aggregated failure paths made each false rejection diagnosable.
It also shows that a newly introduced gate has its own calibration cost and should not be trusted
only because it is strict.

## Expected effect on agent productivity

The gate improves unattended work by replacing several discovery and interpretation steps with a
single command and an explicit decision. Failures retain enough context for an agent to iterate
without asking a person to reproduce the screen. The live suite also prevents a mock-only approval
when persistence, search indexing, permissions, or deletion rules are broken.

The cost is approximately 2 minutes 18 seconds per full decision on the measured machine, plus
local service provisioning. Agents should run narrower tests while editing and use the full gate at
a candidate stopping point. Running it after every small edit would reduce throughput.

## Remaining gaps

This is a stronger stopping condition, not proof of production readiness. Further project-level
work should include:

1. A small browser journey against a real Django server so frontend/backend contract drift is not
   split between a mocked browser suite and API integration tests.
2. Reproducible one-command service provisioning with health checks, architecture checks, and
   isolated container/database names. The current command assumes existing local services.
3. Change-aware routing that always runs the baseline gate but adds domain-specific tests for the
   files and APIs changed by an agent.
4. Performance budgets, concurrency/race tests, migration compatibility, security scanning, and
   backup/restore checks as separate evidence-producing gates.
5. Historical flake and duration tracking. Quarantines or waivers must be explicit, owned, and
   expiring; silent retries must never turn a rejection into approval.
6. Artifact retention and a stable schema/version for manifests so other agents and review tools
   can compare decisions across commits.

