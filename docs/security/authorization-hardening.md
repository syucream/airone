# Authorization hardening (2026-10)

This document records the response to the 2026-10-22 security review, focusing on
the "privilege escalation / IDOR" cluster: the endpoints that let a regular
account either widen its own privileges, or reach another user's objects by
supplying an id.

## Why this class of bug kept appearing

Pagoda's authorization lives in three different layers, and each layer has a
failure mode that the others do not cover:

| Layer | Where | Failure mode seen in the review |
|---|---|---|
| Object permission | `BasePermission.has_object_permission` | DRF never calls it for collection actions (`create`, plain `GenericAPIView` handlers), so "superuser only" rules written there were dead code (F16, F57, F6, F15 — fixed upstream since then). |
| Model level ACL | `User.has_permission()` | Parent objects are only verified through `isinstance` branches; passing a bare `ACLBase` row skips the Entry/EntityAttr/Attribute parent checks (F52, F53). |
| Id resolution | `Model.objects.get(id=...)` in views/tasks | The id comes from the request body, so anything not scoped to the parent object is an IDOR (F7, F24, F30, F42, F138, F40/F55). |

The response therefore is not a set of one-off patches, but three rules plus tests
that enforce them.

## Rules

1. **Collection actions need `has_permission`.** Any permission class that decides
   something for `create` (or for a non-viewset DRF view) must implement
   `has_permission`. `IsSuperuser` in `airone/lib/drf.py` is the shared helper.
2. **Authorize the concrete object.** Never call `user.has_permission()` with an
   `ACLBase` instance; resolve it with `get_subclass_object()` first. Both ACL
   entry points do this now.
3. **Scope every user supplied id to its parent.** Resolve ids from the parent's
   queryset (`entity.attrs`, `entity.isolation_rules`, `entity.webhooks`,
   `param["entry"]`) and reject a mismatch instead of looking them up globally.
   When the id is only known inside a Celery job, re-validate it in the job as
   well, because job params are attacker controlled through the legacy views.

## Findings addressed by this change

Reviewed against `dmm-com/pagoda` master (the branch is rebased on it), so the
following are the findings that are still open upstream:

| Ref | Endpoint | Fix |
|---|---|---|
| F5 | `PUT /user/api/v2/<id>/` | `UserUpdateSerializer` rejects `is_superuser` / `username` changes unless the caller is a superuser. |
| F49 | `POST /user/do_edit/<id>` | Owner or superuser; the `token_lifetime` branch no longer runs before the check. |
| F152 | `PATCH /user/api/v2/<id>/auth` | Owner or superuser. |
| F40/F55 | `DELETE /api/v1/job/` | Owner or superuser (matches `job/api_v2`). |
| F52 | `GET/PUT /acl/api/v2/acls/<id>` | Resolves the concrete subclass before authorizing, so parent Entity/Entry permissions apply. |
| F51 | `GET /acl/api/v2/acls/<id>/history` | Requires Readable on the resolved object. |
| F53 | `POST /acl/set` | Ignores the client supplied `object_type` and resolves the stored row. |
| F24 | `POST /entity/do_edit/<id>` + `EDIT_ENTITY` job | Attribute ids must belong to the target Entity; the job re-validates and always clears `STATUS_EDITING` (a failed job used to lock the Entity forever). |
| F30 | `PUT /entity/api/v2/<id>/` | `isolation_rules[].id` must belong to the Entity being edited. |
| F138 | `POST /entry/api/v1/create_entry_attr/<id>` | Requires Writable on the Entry and the EntityAttr must belong to the Entry's Entity. |
| F42 | `POST /entry/api/v2/alias/`, `alias/bulk/`, `DELETE /entry/api/v2/alias/<id>` | New `EntryAliasPermission` plus a `Writable` check in `EntryAliasSerializer.validate` (create never reaches object permissions). |
| F143 | `EntryCreateSerializer` | Creating an Entry requires Writable on the schema. The serializer is shared by the API, plugin overrides and async jobs, so the check belongs there. |

## Findings fixed upstream, kept as regressions

These were open in the 2026-10-22 snapshot and have already been fixed on
`upstream/master`; the tests are kept so the decisions cannot silently regress:

| Ref | Upstream state | Covered by |
|---|---|---|
| F16 | `group.api_v2.views.UserPermission.has_permission` requires a superuser for create | `test_group_create_requires_superuser`, `test_group_create_is_allowed_for_superuser` |
| F57 | `GroupImportAPI` is superuser only | `test_group_import_requires_superuser` |
| F6 | `UserImportAPI` is superuser only | `test_user_import_requires_superuser` |
| F15 | `RoleImportAPI` is superuser only | `test_role_import_requires_superuser` |
| N1 | `SpecificJobAPI` (`/api/v1/job/run/<id>`) was removed | — |

## Regression gate

`airone/tests/test_authorization_matrix.py` is the gate. It runs as part of the
existing `airone` test target in `.github/workflows/build-core.yml`
(`ls -d */tests/` picks it up automatically).

* Functional cases pin the decision for each endpoint above (403 / 400 for a
  regular user, success for the owner or a superuser).
* `test_no_object_only_permission_class_is_added` walks the URLconf, collects the
  permission classes of every registered viewset and fails when a class that does
  not define `has_permission` is discovered. The three intentionally allowed
  exceptions carry a comment explaining where their collection level decision
  lives instead.
* `test_privileged_views_keep_their_gates` fails when a superuser gate is removed
  from `GroupAPI`, `GroupImportAPI`, `UserImportAPI` or `RoleImportAPI`.

When adding an endpoint, prefer adding a row to that module over adding a test in
an app module: the matrix is reviewed as a single list of authorization
decisions.

## Known follow-ups

Not fixed here, deliberately:

* `IsolationParent.save_conditions()` still resolves `attr_id` / `ref_cond_id`
  globally (`isolation/models.py`). The impact is limited (conditions are
  evaluated against the parent Entity's entries), but they should be scoped too.
* `EntryAttrUpdateSerializer.validate_id()` falls back to a global lookup when the
  serializer is used outside `EntityUpdateSerializer`. Production paths always
  provide the parent instance, so the fallback is unused, but it is a latent trap.
* Group membership is still readable by every authenticated user (`GET
  /group/api/v2/groups`, `/groups/tree`), and so is the user list (`GET
  /user/api/v2/`), because the UI needs them to build selects and the user table.
  Only the write side (`create` / `update` / `destroy` / import) is gated. Both
  directions are pinned by tests so that neither silently flips.
* Renaming a user is now superuser only (renaming a group already is). If a
  non-superuser workflow is required, it needs an explicit permission model, not
  a removal of the gate.

## Running the gates locally

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy ./
uv run python manage.py test airone.tests.test_authorization_matrix
```

The full test matrix is what CI runs; see `.github/workflows/build-core.yml`.
