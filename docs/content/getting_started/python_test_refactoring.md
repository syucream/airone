---
title: Python Test Refactoring
weight: 45
---

# Python test refactoring assessment and pilot

Assessment date: 2026-11-07. Baseline: `742f2f997983e1ecd345ff64c3417d8c0cb03404`.
This assessment covers the Python test modules, their shared fixtures, and the
small refactoring pilot in `user/tests` and `group/tests`. Application code and
dependencies are unchanged.

## Inventory

Counts come from parsing tracked Python files under `*/tests/` at the baseline.
A file is included when it contains a `test_*` function; helper-only files are
excluded. Lines include the whole file. A long test has at least 100 source
lines, including its body and comments. These are static definitions, not
runner-discovered cases: inheritance can execute a definition more than once.
Counts describe maintenance scope, not test quality or behavior coverage.

| Module | Files | Test definitions | Lines | Long tests |
| --- | ---: | ---: | ---: | ---: |
| entry | 21 | 537 | 24,343 | 42 |
| entity | 7 | 244 | 8,742 | 8 |
| api_v1 | 7 | 92 | 4,306 | 6 |
| airone | 24 | 241 | 4,124 | 4 |
| user | 5 | 139 | 3,050 | 2 |
| plugin/sdk | 8 | 153 | 2,319 | 0 |
| job | 7 | 97 | 2,051 | 0 |
| dashboard | 2 | 40 | 2,049 | 5 |
| trigger | 2 | 32 | 1,827 | 4 |
| acl | 4 | 59 | 1,622 | 2 |
| plugin/examples/pagoda-hello-world-plugin | 4 | 81 | 1,388 | 0 |
| role | 4 | 59 | 1,327 | 0 |
| group | 5 | 49 | 1,037 | 0 |
| isolation | 2 | 19 | 468 | 0 |
| webhook | 3 | 15 | 390 | 0 |
| common | 2 | 25 | 376 | 0 |
| tools | 2 | 11 | 243 | 0 |
| category | 1 | 9 | 207 | 0 |
| custom_view_sample | 1 | 3 | 68 | 0 |

## Findings by module

The findings below are source-review candidates. Except for the user/group
pilot, they have not been changed or validated with runtime experiments.

| Module | Evidence and proposed next step | Priority / risk |
| --- | --- | --- |
| user | `test_api_v2.py` mixed user management, credentials, activity queries, and typed activity values. `RecentActivityAPITest(ViewTest)` inherited 44 runnable tests. `test_model.py` changed `MAX_USERS` directly and placed four operations inside one `assertRaises`. Pilot below. | First pilot / moderate |
| group | `test_model.py` created four hierarchical groups and a member for every case, including unrelated limit and referral cases. `MAX_GROUPS` was changed directly, and `test_delete_parent_lonely_group` never deleted the parent. Pilot below. | First pilot / low |
| entry | `test_api_v2.py` mutates dictionaries from `AironeTestCase.ALL_TYPED_ATTR_PARAMS_FOR_CREATING_ENTITY`, storing a database object in shared class data. Copy each dictionary before adding `ref`. Then split the 343-line retrieval test and large import/export scenarios by contract. | High for fixture isolation; high risk for broad restructuring |
| job | `test_view.py` assigns `self.old_config = CONFIG.conf`, mutates that dictionary, then restores the same reference. Use a scoped `patch.dict` to restore values. Preserve the already separate params/task-boundary suites. | High / moderate |
| category | `test_get_include_deleted_model` is only `pass`. Rejected delete/update cases inspect stale instances without `refresh_from_db`; successful update misses assertions for changed scalar fields. Repair these checks before introducing abstractions. | High / low |
| role | Invalid create/update API tests combine multiple failure reasons and login changes. Separate permission and validation scenarios; share only construction of a valid payload. | Next / moderate |
| webhook | Small API tests repeat payloads and verification-response mocks. A local payload builder and mock helper could help while keeping success, unreachable-server, and permission cases distinct. | Next / low |
| entity | Invalid create/update tests in `test_api_v2.py` are 379 and 567 lines. Separate required-field, type, duplicate, and permission cases. Use named `subTest` cases only when request shape and setup are equivalent. | Next / moderate to high |
| trigger | `test_models.py` has a 198-line `setUp` for all 15 model cases; API setup is also large. Separate condition evaluation, action execution, and legacy UI adapters, creating only required attribute types. | Later / high |
| dashboard | `test_view.py` mixes search rendering, CSV export, and job checks in long cases. Split those contracts before sharing typed input data with entry export tests. Search semantics require real Elasticsearch validation. | Later / high |
| acl | The nobody-control API test repeatedly changes public/default/role permissions in one scenario. Give each starting permission state its own fixture; retain explicit last-administrator and recursive ACL checks. | Later / high |
| api_v1 | `tests/entry/test_api_search_chain.py` builds a five-level graph in a 136-line setup and restores configuration/functions manually. Introduce minimal graph builders and scoped patches without changing legacy response contracts. | Later / high |
| airone | Elasticsearch tests contain large complete-query expectations. Split input scenarios while retaining the full query contract. Changing `AironeTestCase` to separate DB and search setup has broad impact and should be a separate project. | Later / high for shared fixtures |
| common | `tests/compat.py:post_import` performs a common-API probe, database rollback, search-index cleanup, logging suppression, and the legacy request. Preserve that compatibility comparison; treat it as more than a simple POST wrapper. | Later / high for helper changes |
| plugin/sdk | `tests/test_models.py` defines serializers inside the test module and tests those helpers; a protocol check also catches `TypeError` and passes. Map assertions to shipped SDK contracts before removing apparent redundancy. Keep this package independent of Django tests. | Later / moderate |
| plugin example | API view tests repeat RequestFactory/mock-user setup and use DB-backed `TestCase` for some mock-only scenarios. Consider `SimpleTestCase` where appropriate, preserving the example's readability. | Low / moderate |
| isolation | Existing small condition helpers and short scenario tests already provide good locality. No additional shared base is justified by duplication alone. | Low / low |
| custom_view_sample | Three cases need little restructuring. Name API-version subcases, while keeping synchronous task patches visible. | Low / low |
| tools | Small focused regression suites cover mypy comparison and index-update tooling. Preserve their standalone execution and avoid coupling them to application fixture bases. | Low / low |

## Pilot design

User and group were chosen because they expose concrete discovery, isolation,
and assertion problems at a manageable size. They also exercise both useful
refactoring scales: a large module needs file boundaries, while a small one
can remain readable with classes inside its existing files.

### User

The former 1,835-line API file now has four responsibility boundaries:

| File | Responsibility |
| --- | --- |
| `user/tests/test_api_v2.py` | User management, permissions, import/export |
| `user/tests/test_api_v2_authentication.py` | Passwords, authentication mode, tokens |
| `user/tests/test_api_v2_activity.py` | Activity queries, time windows, visibility |
| `user/tests/test_api_v2_activity_values.py` | Typed attribute-value serialization |

The largest resulting file is 554 lines. Existing API test names, bodies,
decorators, and assertion helpers are unchanged, verified by AST comparison.
`UserFixtureMixin` contains only the existing user/group constructors. It does
not inherit `TestCase` or contain test methods; runnable classes inherit the
appropriate shared test base directly.

The model pilot also moves the social-auth record from global setup into the
deletion scenario that needs it, scopes `MAX_USERS` changes with `self.settings`,
and gives each invalid history operation its own `assertRaises` and named
`subTest`. Previously the first exception prevented the remaining operations
from executing.

### Group

Model classes separate deletion, referrals, and limits. API classes separate
read, write, and import/export behavior without adding more files. One-line
creation wrappers have been replaced with explicit ORM calls. Each model case
creates the minimum relevant relationships rather than inheriting a full tree.

The limit test now admits groups below and at the configured limit, rejects the
next group, and verifies that rejection did not persist a row. Unlimited mode
has its own test. Both settings overrides restore automatically. The parent
deletion test now deletes and checks the parent after deleting its child.

## Self-review and repairs

Review used five criteria: scenario preservation, local readability, failure
diagnosis, fixture isolation, and proportionate abstraction.

* **Scenario preservation:** the initial group simplification replaced the
  unreferenced parent with an unrelated group. That weakened the assertion
  that referencing a child does not reference its parent, despite identical
  line/branch coverage. The parent-child relationship was restored. Leaf
  deletion also retains its explicit parent and checks persisted state.
* **Readability:** the initial `UserProfileAPITest` name hid create/delete and
  import/export behavior. It was renamed `UserManagementAPITest`. File moves
  leave requests and expected payloads visible within each test.
* **Failure diagnosis:** invalid history operations now report their method
  name independently. Group limit and unlimited cases have separate identities.
* **Fixture isolation:** settings use automatic restoration, social auth is
  created only where used, and no runnable test class inherits another suite.
* **Abstraction:** typed activity cases stay explicit because their payloads
  and expectations differ. The existing small fixture mixin is sufficient;
  no generic factory framework or new dependency was introduced.

The pilot remains incremental. Long activity scenarios and legacy user/group
HTML/API-v1 tests are retained. A new maintainer still needs the common
`AironeViewTest` conventions and the import compatibility helper. Test IDs
containing renamed classes or moved modules change; method names are retained.
CI and tooling contained no references to the former class-specific labels.

## Validation

All runtime results below are local SQLite, in-memory search, and memory-broker
evidence. They do not establish MySQL/Elasticsearch, GitHub CI, or production
behavior. The local migration set needed regeneration for the existing group
`display_name` field; generated migrations are not part of this change.
An initial concurrent order-variation run stopped during application startup
because version discovery exceeded its one-second Git subprocess timeout.
Both suites passed when rerun with staggered startup; that initial run is not
counted as a successful test execution.

| Check | Baseline | Pilot |
| --- | ---: | ---: |
| User test definitions | 139 | 139 |
| User runner-discovered tests | 183 | 139 |
| Group test definitions / discovered tests | 49 | 50 |
| User suite: executed application lines / branches | 1,128 / 223 | 1,128 / 223 |
| Group suite: executed application lines / branches | 785 / 78 | 785 / 78 |

The 44 removed executions are inherited duplicates; no original test method
was removed. Group adds the independently selectable unlimited-limit case.
Coverage collection includes production modules under `user` and `group`,
excluding tests and migrations. Per-file executed-line and executed-branch
sets are compared, rather than percentages alone. This is a preservation
check, not proof of equivalent assertions or complete coverage.

The baseline was executed from its Git source in separate test processes with
the same application code, environment, and generated migrations. Normal and
shuffled pilot runs use one process per app. Two temporary in-memory mutation
probes also check the repaired assertions: accepting an invalid history-modify
target, and skipping deletion of a parent with deleted children. The old cases
accept those mutations; the repaired cases fail as intended. No mutation is
written to application source.

Ruff lint/format passed. The mypy source-regression ratchet reported
`base=1, current=0`, with no new diagnostics. Both complete pilot suites passed
in normal order and with shuffle seed `20261107`. Run each application
separately, including an order-variation check:

```bash
AIRONE_MYSQL_MASTER_URL=sqlite://:memory: AIRONE_ES_BACKEND=inmemory \
  AIRONE_RABBITMQ_URL=memory:// tools/lite.sh test user
AIRONE_MYSQL_MASTER_URL=sqlite://:memory: AIRONE_ES_BACKEND=inmemory \
  AIRONE_RABBITMQ_URL=memory:// tools/lite.sh test group
# Repeat each app with --shuffle=20261107 to vary execution order.
uv run ruff check user/tests group/tests
uv run ruff format --check user/tests group/tests
PAGODA_LITE=1 uv run python tools/mypy_ratchet.py --base-ref 742f2f99
```

For subsequent refactors, fix shared-state leaks and ineffective assertions
first, then expand responsibility boundaries one module at a time. Preserve
scenario inputs and expected persisted effects alongside discovery and coverage
checks. Real-stack validation remains necessary when search or database
semantics are changed.
