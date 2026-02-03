---
name: Taggit migration
overview: Replace vendored django-tagging with no-op migrations (via MIGRATION_MODULES) for migration-history compatibility, and move runtime tagging to a Signbank-owned adapter backed by django-taggit tables/models. This avoids keeping legacy dependency code around.
todos:
  - id: add-taggit
    content: Add django-taggit dependency and enable it in INSTALLED_APPS.
    status: pending
  - id: no-op-migrations
    content: Create no-op migrations for tagging (0001_initial, 0002_on_delete, 0003_adapt_max_tag_length) in signbank.tagging.migrations and configure MIGRATION_MODULES to use them, allowing removal of vendored django-tagging dependency.
    status: pending
  - id: taggit-helpers
    content: Introduce a Signbank-owned tagging adapter API (stable surface) with a taggit backend implementation (no taggit usage in business code/templates).
    status: pending
  - id: data-migration
    content: Create migration to copy Tag/TaggedItem data from tagging tables into taggit tables.
    status: pending
  - id: allowedtags-migration
    content: Migrate AllowedTags M2M to point at taggit.Tag and copy existing relations.
    status: pending
  - id: code-switch
    content: Update dictionary/comments/admin/forms/tests to use taggit + helpers (remove django-tagging-specific calls).
    status: pending
  - id: template-tags
    content: Provide a `tagging_tags` template tag library backed by the adapter (so templates need minimal/no edits).
    status: pending
  - id: verify
    content: Run migrations + test suite to validate behavior and performance.
    status: pending
isProject: false
---

## What we have today (from repo scan)

- `django-tagging` is vendored at `vendor/django-tagging/` and installed via Poetry path dependency in [`/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/pyproject.toml`](/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/pyproject.toml).
- The Django app label `tagging` is installed in [`/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/settings/base.py`](/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/settings/base.py) and used broadly:
- Python code imports `from tagging.models import Tag, TaggedItem` (dictionary + comments + tests)
- Templates use `{% load tagging_tags %}` and `{% tags_for_object ... %}`
- Dictionary migrations create fixed tag rows via `apps.get_model("tagging","Tag")` and depend on `('tagging','0003_adapt_max_tag_length')`.

## Target state

- **Tag data lives in taggit’s tables** (`taggit_tag`, `taggit_taggeditem`).
- **All runtime usage goes through a Signbank-owned adapter**, so we can swap out taggit later with localized changes.
- **No legacy dependency code**: django-tagging is completely removed. Migration history is preserved via no-op migrations in `signbank.tagging.migrations` configured through `MIGRATION_MODULES`.
- **Templates keep using `{% load tagging_tags %}`**, but the implementation is ours and calls the adapter (not django-tagging).
- **All tagging code organized under `signbank.tagging.*` namespace**:
- `signbank.tagging.adapter` - adapter API (taggit backend)
- `signbank.tagging.templatetags` - template tags (`{% load tagging_tags %}`)
- `signbank.tagging.migrations` - no-op migrations for legacy compatibility

## Key design decisions for this repo

- **Adapter-first**: application code calls our adapter (e.g. `signbank.tagging.adapter.*`) rather than `taggit.*` directly.
- **No TaggableManager refactor initially**: your current usage tags arbitrary models via ContentTypes (Gloss, GlossRelation, `django_comments` Comment). We’ll keep a generic object-tagging approach using taggit’s `Tag` + `TaggedItem` tables behind the adapter.
- **Preserve forced-lowercase semantics**: current setting `FORCE_LOWERCASE_TAGS = True` is relied on; we’ll enforce lowercasing in the adapter.

## Implementation outline

### 1) Add taggit (storage backend)

- Add `django-taggit` dependency.
- Add `'taggit'` to `INSTALLED_APPS` in [`/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/settings/base.py`](/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/settings/base.py).

### 2) Create no-op migrations for tagging (avoid legacy dependency code)

- Create `signbank/tagging/` directory with `__init__.py` (minimal app structure, no models needed).
- Create `signbank/tagging/migrations/` directory with `__init__.py`.
- Create three no-op migration files matching django-tagging's migration names:
- `0001_initial.py`: depends on `('contenttypes', '0001_initial')`, uses `migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop)`
- `0002_on_delete.py`: depends on `('tagging', '0001_initial')`, uses no-op RunPython
- `0003_adapt_max_tag_length.py`: depends on `('tagging', '0002_on_delete')`, uses no-op RunPython
- Update `MIGRATION_MODULES` in settings to include `'tagging': 'signbank.tagging.migrations'` (alongside existing flatpages override, following the same pattern).
- Remove `'tagging'` from `INSTALLED_APPS` (no longer needed - migrations are handled via MIGRATION_MODULES).
- Remove vendored `django-tagging` dependency from Poetry and delete `vendor/django-tagging/`.

**Rationale**: Existing installations already have the tagging tables created, so no-op migrations are safe. New installations will run the no-ops (which do nothing) and then proceed with taggit migrations. This completely removes the legacy dependency without breaking migration history. Using `signbank.tagging.migrations` keeps migrations organized under the app name and follows Django conventions (same pattern as `signbank.contentpages.migrations`).

### 3) Create a Signbank-owned tagging adapter (single source of truth)

- Add adapter module `signbank/tagging/adapter.py` (or `signbank/tagging/adapter/` package if it grows) with a small stable API:
- `tags_for_object(obj)`
- `add_tag(obj, tag_name)` / `remove_tag(obj, tag_name)`
- `filter_queryset_with_all_tags(queryset_or_model, tag_names)` (intersection)
- `filter_queryset_with_any_tags(queryset_or_model, tag_names)` (union)
- `tags_usage_for_model(model_or_queryset, with_counts=False)`
- Implement the adapter’s backend with taggit models/tables:
- `taggit.models.Tag`
- `taggit.models.TaggedItem`
- ORM-based queries (annotate/count/distinct) rather than raw SQL.
- All tagging-related code lives under `signbank.tagging.*` namespace: `signbank.tagging.adapter`, `signbank.tagging.templatetags`, `signbank.tagging.migrations`.

### 4) Data migration: copy old tagging tables → taggit tables

**Decision: Use Django migration (not one-off script)**

**Rationale**: Django migrations are preferred because:

- They're version-controlled and part of migration history
- They run automatically on deploy (no manual step required)
- They can gracefully handle both existing installations (with legacy tables) and fresh installs (without legacy tables)
- They're idempotent and can be re-run safely

**Implementation**:

- Add a Django migration (most naturally in `signbank/dictionary/migrations/`) that depends on:
- the latest `taggit` migration (from installed taggit version)
- `('tagging','0003_adapt_max_tag_length')` (our no-op migration)
- Migration steps:
- Check if legacy tables exist using `connection.introspection.table_names()` or try/except around `apps.get_model("tagging", "Tag")`.
- If legacy tables exist:
- Use `apps.get_model("tagging", "Tag")` and `apps.get_model("tagging", "TaggedItem")` to access legacy tables.
- Copy `tagging.Tag` rows into `taggit.Tag` by `name` (lowercased), letting taggit auto-generate `slug`.
- Copy `tagging.TaggedItem` into `taggit.TaggedItem` by mapping tag name → new tag id, and copying `content_type_id` + `object_id`.
- Use `bulk_create(..., ignore_conflicts=True)` to respect unique constraints and make migration idempotent.
- If legacy tables don't exist (fresh install), migration does nothing (no-op) - taggit tables will be empty, which is correct.
- Use `migrations.RunPython` with proper forward/reverse functions, making reverse a no-op (can't restore deleted legacy data).

### 5) Move AllowedTags to taggit.Tag

- Update `AllowedTags.allowed_tags` in [`/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/models.py`](/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/models.py) to M2M with `taggit.Tag`.
- Add a migration to:
- create the new M2M table
- copy existing AllowedTags relations by tag name mapping old→new
- drop the old M2M field/table

### 6) Update all runtime code to use the adapter (not django-tagging, not taggit directly)

- Replace imports from `tagging.models` and `tagging.*` with `signbank.tagging.adapter.*` in:
- [`/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/update.py`](/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/update.py)
- [`/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/adminviews.py`](/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/adminviews.py)
- [`/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/admin.py`](/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/admin.py)
- [`/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/forms.py`](/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/forms.py)
- [`/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/views.py`](/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/views.py)
- [`/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/csv_import.py`](/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/dictionary/csv_import.py)
- [`/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/comments.py`](/Users/josh/Projects/github.com/odnzsl/nzsl-signbank/signbank/comments.py)
- associated tests under `signbank/dictionary/tests/`
- Remove usage of `tagging.registry.register()` and `Tag.objects.*` methods that are django-tagging-specific; replace with adapter calls.

### 7) Keep template API stable: provide `tagging_tags` backed by the adapter

- Add `signbank/tagging/templatetags/` directory and `__init__.py` to the existing `signbank/tagging/` directory (created in step 2).
- Implement `signbank/tagging/templatetags/tagging_tags.py` (same `{% load tagging_tags %}` usage) with at least:
- `{% tags_for_object obj as var %}`
- (optionally) `{% tags_for_model ... %}` / `{% tagged_objects ... %}` if we actually use them outside vendored tests/docs
- Internally these template tags call the adapter (taggit-backed), so templates can remain unchanged.
- Ensure the templatetags module is discoverable. Since `signbank.tagging` is a Python package (has `__init__.py`), Django should discover `signbank.tagging.templatetags` automatically. If needed, add `signbank.tagging` to INSTALLED_APPS, but it's not required for templatetags discovery.

### 8) Verify with tests and a migration dry-run

- Run migrations on a clean DB (or ephemeral DB) to ensure:
- the no-op `tagging` migrations apply successfully (they do nothing but satisfy dependencies)
- taggit tables are created
- our copy migration runs successfully (or skips gracefully on fresh installs)
- Run migrations on an existing DB (with legacy tagging tables) to ensure:
- no-op migrations don't break anything
- data migration successfully copies tags to taggit
- Run existing test suite (`bin/runtests.py`) focusing on dictionary/admin/comment flows that currently assert tag behavior.

### 9) Cleanup (follow-up, optional in same PR)

- Verify `vendor/django-tagging/` is removed and Poetry dependency is gone (should be done in step 2).
- Legacy tables (`tagging_tag`, `tagging_taggeditem`) remain in existing databases but are no longer used. They can be dropped in a future migration if desired, but keeping them doesn't hurt.
- Optional later project: migration-history squashing to reduce legacy baggage (not required to remove the unmaintained dependency).