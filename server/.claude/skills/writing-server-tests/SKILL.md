---
name: writing-server-tests
description: Write or update tests for the MedPerf Django REST Framework server (medperf/server) when adding an endpoint, feature, or bugfix. Encodes this codebase's exact conventions — one test file per URL, the MedPerfTest harness, REST-only setup, the base + parameterized-action + PermissionTest class structure (permission tests cover FORBIDDEN actions only), mock/create helpers, and per-entity validation/permission rules. Use whenever you touch server code with an HTTP surface.
---

# Writing MedPerf server tests

Tests for the Django REST Framework API under `medperf/server/`. Read this fully
before writing a new test file or extending an existing one. The conventions
below are enforced by convention, not tooling — match them exactly so the suite
stays uniform.

## The 4 golden rules (do not violate)

1. **Set up state only through the REST API, never through Django models
   directly.** Use `self.create_user(...)`, `self.create_mlcube(...)`,
   `self.shortcut_create_benchmark(...)`, etc. There are no `Model.objects.create`
   calls in tests, no fixtures, no `factory_boy`. The one allowed exception is
   promoting a user to admin, which the harness already does for you.
2. **One test file per URL.** The filename is derived mechanically from the
   endpoint path (see the naming table). The `utils/` folder is the sole
   exception: every `/me/...` endpoint is tested in the single file
   `utils/tests.py`.
3. **`PermissionTest` classes test only forbidden actions** (expected `403`/`401`),
   never the happy path. We care most about stopping users from doing what they
   must not do. Positive "this role is allowed" behavior is asserted implicitly
   by the action test classes (which run as an allowed `actor`), not in
   `PermissionTest`.
4. **For every HTTP method an endpoint supports, cover the three risk sources**
   (README): serializer validation rules (`serializers.py`), database constraints
   (`models.py`), and permissions (`views.py` `get_permissions`). Bias toward
   negative/edge cases over happy paths.

## How to run

Django's test runner (NOT pytest, despite the stale `.pytest_cache/`):

```bash
python manage.py test                              # whole suite
python manage.py test --parallel                   # faster
python manage.py test dataset.tests.test_pk        # one file
python manage.py test benchmark.tests.test_ -k BenchmarkPostTest      # one class
python manage.py test benchmark.tests.test_ -k test_creation_of_duplicate_name   # one method
```

Each parameterized instance runs **independently against a fresh database**, and
`setUp` runs before every single test method. `debug_tests.sh` runs an
interdependent subset with `--failfast` for ordered debugging.

## File naming & placement

Tests live in an `<app>/tests/` package (with `__init__.py`). The filename is the
endpoint path *relative to the app's URL root*, with `/`→`_`, `<int:pk>`→`pk`,
`<...:bid>`→`bid`, and the collection root spelled as the empty suffix `test_`.

| Endpoint | App | Test file |
|---|---|---|
| `POST`/`GET` `/mlcubes/` | `mlcube` | `tests/test_.py` |
| `GET`/`PUT`/`DELETE` `/mlcubes/<pk>/` | `mlcube` | `tests/test_pk.py` |
| `GET` `/mlcubes/<pk>/datasets/` | `mlcube` | `tests/test_pk_datasets.py` |
| `GET` `/benchmarks/<pk>/datasets/` | `benchmark` | `tests/test_pk_datasets.py` |
| `GET` `/benchmarks/<pk>/participants_info/` | `benchmark` | `tests/test_pk_participants_info.py` |
| `GET` `/benchmarks/<pk>/datasets_certificates/` | `benchmark` | `tests/test_datasets_certificates.py` |
| `POST` `/datasets/benchmarks/` (assoc create) | `dataset` | `tests/test_benchmarks.py` |
| `GET`/`PUT`/`DELETE` `/datasets/<pk>/benchmarks/<bid>/` | `dataset` | `tests/test_pk_benchmarks_bid.py` |
| `POST` `/models/benchmarks/` (assoc create) | `model` | `tests/test_benchmarks.py` |
| `GET` `/certificates/<pk>/encrypted_keys/` | `certificate` | `tests/test_pk_encrypted_keys.py` |
| `POST`/`PUT` `/encrypted_keys/bulk/` | `encrypted_key` | `tests/test_bulk.py` |
| all `/me/...` endpoints | `utils` | `tests.py` (single flat file) |

Note the model/dataset **association** endpoints are namespaced under
`/datasets/...` and `/models/...`, so their tests live in the `dataset`/`model`
apps — the `benchmarkdataset`/`benchmarkmodel` apps hold the models but have no
test files of their own.

## The harness: `MedPerfTest`

Every test class inherits from `medperf.tests.MedPerfTest` (which extends
`django.test.TestCase`). Its `setUp` configures mocked RS256 JWT auth, disables
SSL redirect, creates the admin user, and exposes:

| Attribute / method | What it gives you |
|---|---|
| `self.client` | DRF `APIClient` |
| `self.api_prefix` | `"/api/v0"` — prepend to every URL |
| `self.api_admin` | username `"api_admin"`, a superuser whose token is pre-loaded |
| `self.create_user(username)` | creates a user **via `GET /me/`**, stores its token, returns the user dict (`id`, `email`=`<username>@example.com`, `username`, ...) |
| `self.set_credentials(username)` | auth as that user; `self.set_credentials(None)` = unauthenticated |

### Mock builders (payload dicts)

Attached to `self` and importable from `medperf.testing_utils`. Each takes
`**kwargs` overrides and raises `ValueError` on an unknown key (so a typo fails
loudly). They return a plain dict — the request body — they do **not** hit the DB.

```
self.mock_mlcube(**kw)                       # name, container_config, image_hash, state, ...
self.mock_dataset(data_preparation_mlcube, **kw)
self.mock_benchmark(prep_id, reference_model_id, eval_id, **kw)
self.mock_model(**kw)                        # wraps mock_mlcube into {container:{...}, type:"CONTAINER"}
self.mock_result(benchmark, model, dataset, **kw)
self.mock_dataset_association(benchmark, dataset, **kw)   # NOTE: benchmark first
self.mock_model_association(benchmark, model, **kw)       # NOTE: benchmark first
self.mock_ca(**kw)                           # client/server/ca_mlcube default to id 1 (migration-seeded)
self.mock_certificate(ca, **kw)
self.mock_encrypted_key(certificate, container, **kw)
self.mock_asset(**kw) / self.mock_asset_model(**kw)
```

### Create helpers (POST via REST, assert `201`, return the `response`)

```
self.create_mlcube(data)        self.create_model(data)     self.create_asset(data)
self.create_dataset(data)       # if data["state"]=="OPERATION", does the 2-step create→PUT
self.create_result(data)
self.create_ca(data)            self.create_certificate(data)
self.create_encrypted_keys(list_of_keys)     # POSTs to /encrypted_keys/bulk/; .data is a LIST

self.create_benchmark(data, target_approval_status="APPROVED")
    # 2-step: creator POSTs, then api_admin PUTs approval_status. Restores caller creds.

self.create_dataset_association(data, initiating_user, approving_user, set_status_directly=False)
self.create_model_association(data, initiating_user, approving_user, set_status_directly=False)
    # initiating_user POSTs a PENDING assoc; if target status != PENDING, approving_user PUTs it.
    # set_status_directly=True forces the status in one shot (used to build REJECTED/edge states).

prep, ref_model, eval, benchmark = self.shortcut_create_benchmark(
    prep_mlcube_owner, ref_model_owner, eval_mlcube_owner, bmk_owner,
    target_approval_status="APPROVED",
    prep_mlcube_kwargs={}, ref_model_kwargs={}, eval_mlcube_kwargs={},
    **benchmark_kwargs,          # e.g. dataset_auto_approval_mode="ALWAYS", name="x"
)   # builds the 3 containers + benchmark end-to-end and returns their .data dicts
```

All create helpers preserve and restore the current credentials, so you can call
them mid-test without clobbering `self.current_user`.

## Anatomy of a test file

Three kinds of class, in this order:

```python
from rest_framework import status
from medperf.tests import MedPerfTest
from parameterized import parameterized, parameterized_class


class MlCubeTest(MedPerfTest):
    # Base: shared setup. NOT run by the test runner directly (no test_ methods).
    def generic_setup(self):
        # 1. create users (roles) via REST
        mlcube_owner = "mlcube_owner"
        other_user = "other_user"
        self.create_user(mlcube_owner)
        self.create_user(other_user)
        # 2. store role names as attributes
        self.mlcube_owner = mlcube_owner
        self.other_user = other_user
        # 3. set the URL template ({0}/{1} are pk/sub-id placeholders)
        self.url = self.api_prefix + "/mlcubes/{0}/"
        # 4. end unauthenticated
        self.set_credentials(None)


@parameterized_class([{"actor": "mlcube_owner"}])
class MlCubePutTest(MlCubeTest):
    """Test module for PUT /mlcubes/<pk>"""
    def setUp(self):
        super(MlCubePutTest, self).setUp()
        self.generic_setup()
        self.set_credentials(self.actor)      # act as an allowed role

    def test_put_modifies_editable_fields_in_development(self):
        # Arrange
        testmlcube = self.create_mlcube(self.mock_mlcube(state="DEVELOPMENT")).data
        new = {"name": "newname", "is_valid": False}
        url = self.url.format(testmlcube["id"])
        # Act
        response = self.client.put(url, new, format="json")
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for k, v in response.data.items():
            if k in new:
                self.assertEqual(new[k], v, f"{k} was not modified")


class PermissionTest(MlCubeTest):
    """Test module for permissions of /mlcubes/{pk} endpoint
    Non-permitted actions:
        GET: for unauthenticated users
        DELETE: for all users except admin
        PUT: for all users except mlcube owner and admin
    """
    def setUp(self):
        super(PermissionTest, self).setUp()
        self.generic_setup()
        self.set_credentials(self.mlcube_owner)
        self.testmlcube = self.create_mlcube(self.mock_mlcube()).data
        self.url = self.url.format(self.testmlcube["id"])

    @parameterized.expand([
        ("other_user", status.HTTP_403_FORBIDDEN),
        (None, status.HTTP_401_UNAUTHORIZED),
    ])
    def test_put_permissions(self, user, expected_status):
        # Arrange
        self.set_credentials(user)
        # Act
        response = self.client.put(self.url, {"name": "x"}, format="json")
        # Assert
        self.assertEqual(response.status_code, expected_status)
```

### Rules that always hold

- **`# Arrange` / `# Act` / `# Assert` comments** in every test method.
- The base class is named `<Entity>Test` and holds `generic_setup()`. It is
  subclassed by every action/permission class. (The generic runner won't run it
  because it has no `test_` methods.)
- Action classes decorate with `@parameterized_class([{"actor": "..."}])` and set
  credentials to that `actor` in `setUp`. Multiple actor rows = the same test body
  run once per allowed role.
- Admin-only actions (DELETE, benchmark approval) use `[{"actor": "api_admin"}]`.
- Association tests parametrize over `[{"initiator": ..., "actor": ...}]` pairs.
- Every file ends with a `PermissionTest` (named exactly that — files are separate
  modules so the name may repeat across files).

## Permission tests in depth

The heart of the suite. A `PermissionTest`:

- Has a **class docstring** listing "Non-permitted actions:" per method — write this
  first; it's your spec.
- Provides one `test_<method>_permissions` per HTTP method the endpoint supports.
- Uses `@parameterized.expand([...])` with **one row per forbidden role**, ending
  with `(None, status.HTTP_401_UNAUTHORIZED)` for the unauthenticated case.
- Enumerate every role that must be blocked — including "obvious" owners of related
  objects, because MedPerf permissions are frequently **cross-entity**: e.g. the
  benchmark owner (not the data owner) may list a benchmark's dataset associations;
  the *associated model owner* (not the certificate owners) may read
  `/benchmarks/<pk>/datasets_certificates/`; a certificate's CA owner cannot read
  the certificate. When in doubt, read `views.py` `get_permissions()` and the
  `permissions.py` classes: permission classes are OR-combined (`IsAdmin | IsOwner`)
  and a role passes only if at least one returns `True`.
- For a GET that every authenticated user may call, the list collapses to just
  `[(None, status.HTTP_401_UNAUTHORIZED)]`.

Two idioms for permission-blocked writes:

```python
# (a) single call, one forbidden status
def test_delete_permissions(self, user, expected_status):
    self.set_credentials(user)
    response = self.client.delete(self.url)
    self.assertEqual(response.status_code, expected_status)

# (b) per-field loop: PUT each field alone, all must be blocked identically
def test_put_permissions(self, user, expected_status):
    self.set_credentials(user)
    for key in payload:
        response = self.client.put(self.url, {key: payload[key]}, format="json")
        self.assertEqual(response.status_code, expected_status, f"{key} was modified")
```

When approval/status changes have their own permission rule, give them a dedicated
method (e.g. `test_put_approval_status_permissions`) with its own forbidden list —
benchmark approval, for instance, is admin-only even though plain PUT is
owner-allowed.

## Assertion idioms (copy these)

```python
# Created/returned fields match what was submitted (ignore server-added keys):
for k, v in response.data.items():
    if k in submitted:
        self.assertEqual(submitted[k], v, f"Unexpected value for {k}")

# Default values: delete the key from the mock, POST, assert the server default:
for key in default_values:
    testobj.pop(key, None)
response = self.client.post(self.url, testobj, format="json")
for key, val in default_values.items():
    self.assertEqual(val, response.data[key], f"unexpected default value for {key}")

# Read-only fields ignored on write: send them, expect 201, assert NOT applied:
testobj.update({"owner": 10, "created_at": "x", "modified_at": "x"})
response = self.client.post(self.url, testobj, format="json")
for key, val in readonly.items():
    self.assertNotEqual(val, response.data[key], f"readonly field {key} was modified")

# Non-editable-in-operation: PUT each field alone, expect 400 each:
for key in noneditable:
    response = self.client.put(url, {key: noneditable[key]}, format="json")
    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"{key} was modified")

# Not found:
url = self.url.format(9999)     # convention: invalid_id = 9999
# ... expect 404 on open detail endpoints; but see the 403-not-404 gotcha below.

# Delete round-trip:
self.assertEqual(self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT)
self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)

# Private/visible field allow-lists (nested list responses):
for item in response.data["results"]:
    for key in item:
        self.assertIn(key, self.visible_fields, f"{key} shouldn't be visible")

# ID membership (filtered/isolation tests):
ids = [x["id"] for x in response.data["results"]]
self.assertIn(expected_id, ids); self.assertNotIn(hidden_id, ids)

# Nested owner serialized as an object, not an FK id:
self.assertIsInstance(entry["owner"], dict)
```

### Response shape: paginated vs bare list

- **Paginated** (list/collection endpoints and `/me/...` and most nested lists):
  read `response.data["results"]`. The pagination is LimitOffset, page size 32.
- **Bare list** (the association-approval GET `/datasets|models/<pk>/benchmarks/<bid>/`,
  which returns *all* versions of that pair): index `response.data[0]`,
  `len(response.data)`. Check the view — if it calls `paginate_queryset`, it's
  paginated; if it returns `Response(serializer.data, many=True)`, it's bare.

## Association endpoints (dataset ⇄ benchmark, model ⇄ benchmark)

Associations carry an `approval_status` state machine
(`PENDING → APPROVED | REJECTED`, terminal) validated in
`utils/associations.py`. Build them only through
`create_dataset_association` / `create_model_association`. Key rules the tests
pin down:

- A new `PENDING` request is allowed only if the previous one was `REJECTED`; you
  can't create an already-`APPROVED` request; you can only `REJECT` a prior
  `APPROVED` one.
- On update, only a `PENDING` request may be approved/rejected, and **a user
  cannot approve their own initiated request** (approver ≠ initiator).
- PUT always acts on the **latest** association for the pair.
- Auto-approval: benchmark carries `{dataset,model}_auto_approval_mode`
  (`NEVER`/`ALWAYS`/`ALLOWLIST`) and `..._allow_list` (emails). Same-owner and
  allow-list flows auto-approve; the benchmark owner initiating never auto-approves.
  Use the `_info["email"]` returned by `create_user` to populate allow-lists.
- **Model associations are a 1:1 mirror of dataset associations, plus a `priority`
  field** (default `0`, read-only on create, and the model owner is forbidden from
  PUTing it). Dataset setup additionally requires the dataset be `state="OPERATION"`
  and prepared by the benchmark's prep cube; model setup only needs
  `state="OPERATION"`.

## Bulk endpoints (`/encrypted_keys/bulk/`)

- POST and PUT take a **JSON list**. Create via `self.create_encrypted_keys([...])`;
  `.data` is a list.
- PUT items must be `{"id", "is_valid", "encrypted_key_base64"}` and nothing else;
  `is_valid` may only go to `False`. Wrong field set or `is_valid=True` → `400`.
- All-or-nothing: one bad item rolls back the whole batch (assert nothing changed
  via a follow-up GET as `api_admin`).
- Because permission classes run **before** the view body, a bulk PUT missing an
  `id` fails the `IsKeyOwnerForPut` check and returns `403`, not `400`.

## Per-entity cheat sheet

| Entity | State machine / key rules | Editable in OPERATION | Private/owner-only fields |
|---|---|---|---|
| **mlcube** | unique `name`; `unique_together(image_hash, additional_files_tarball_hash, container_config, parameters_config)`; additional-files URL requires a hash (and vice-versa) | `is_valid`, `user_metadata`, `additional_files_tarball_url` | — |
| **dataset** | `state` DEVELOPMENT→OPERATION only (2-step via `create_dataset`); `generated_uid` unique among OPERATION datasets | `is_valid`, `user_metadata` | `report` |
| **model** | wraps a container (`type="CONTAINER"`); model `state`/`is_valid` must match its nested container | `is_valid`, `user_metadata` | — |
| **benchmark** | `approval_status` PENDING→APPROVED/REJECTED (admin-only, terminal); `state` DEVELOPMENT→OPERATION requires prep/refmodel/eval all OPERATION; only one PENDING benchmark per creator | most fields while owner; approval is admin-only | `dataset_auto_approval_allow_list`, `model_auto_approval_allow_list` |
| **result** | created by the **dataset owner**; needs an APPROVED dataset assoc **and** APPROVED model assoc (or the benchmark's reference model, which any dataset may use); `finalized`/`finalized_at` are read-only and flip to `True` as a side effect of PUTing `results`; a finalized result is locked (PUT → 400) | — | — |
| **certificate** | unique `name`; `UniqueConstraint(owner, ca, key_type)` only among `is_valid=True`; only `is_valid` editable and only →`False` | `is_valid` (→False) | — |
| **encrypted_key** | `UniqueConstraint(certificate, container)` only among `is_valid=True`; certificate must be valid at create; bulk-only writes | `is_valid`(→False), `encrypted_key_base64` | — |

## Gotchas

- **Migration-seeded objects exist in every fresh DB:** a superuser, one CA
  mlcube with **id `1`** (state OPERATION), and one CA with id `1`. This is why
  `mock_ca` defaults its three mlcube FKs to `1`, and why the `/mlcubes/` list test
  expects `len(results) == 2` after creating a single mlcube. Account for the +1.
- **403-instead-of-404:** on permission-gated detail endpoints (certificates,
  encrypted keys, results, some nested lists), requesting a non-existent id returns
  `403`, not `404`, because the permission check runs first and fails to find the
  object. Existing tests assert `403` here, sometimes with
  `# TODO: fixme after refactoring permissions. should be 404`. Match the actual
  behavior; carry the TODO if the endpoint is permission-gated.
- **Permission classes run before the view body** — expect permission failures
  (401/403) before validation failures (400).
- **Fresh DB per parameterized instance** — never rely on ordering or state leaking
  between test methods or between parameterized rows.
- **`self.url` formatting is done ad hoc** — some classes pre-format `self.url` in
  `setUp`, others keep the `{0}` template and `.format(...)` inside each method.
  Either is fine; be consistent within a class.
- **Untested apps** (no test files yet): `aggregator`, `asset`, `ca`, `training`,
  `trainingevent`, `traindataset_association`, and several `/me/` FL endpoints
  (`training`, `aggregators`, `training/events`, `datasets/training_associations`).
  These are newer FL/training features. If you add or fix an endpoint there, create
  the first test file for it following every convention above — start from the
  closest analog (a plain CRUD entity → mirror `mlcube`; an association → mirror
  `dataset/tests/test_benchmarks.py` + `test_pk_benchmarks_bid.py`).

## Checklist before you finish

- [ ] One file per URL, named per the table; placed in `<app>/tests/` with `__init__.py`.
- [ ] Base `<Entity>Test(MedPerfTest)` with `generic_setup()`; all setup via REST helpers.
- [ ] An action class per supported HTTP method, `@parameterized_class` over allowed `actor`(s).
- [ ] Serializer rules, model constraints, and default/read-only fields each covered.
- [ ] A `PermissionTest` with a "Non-permitted actions" docstring and a forbidden-role
      row (+ `(None, 401)`) for every method — **including cross-entity owners** that
      must be blocked.
- [ ] `# Arrange/# Act/# Assert` comments; correct response shape (`["results"]` vs bare list).
- [ ] `python manage.py test <app>.tests.<file>` passes.
