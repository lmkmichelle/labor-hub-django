<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 2.0.0
Ratification: Initial adoption remains 2026-07-20; amended for the Flowbite standard.

Modified principles:
- III. User Experience Consistency — REDEFINED: the styling standard moved from
  django-crispy-forms + Bootstrap 5 to TailwindCSS + Flowbite, with shared template
  partials for structure and `@apply` component classes for repeated controls; HTMX
  replaced by Flowbite/Tagify as the progressive-enhancement layer. (MAJOR: a mandated
  technology inside a principle was removed/replaced.)

Unchanged principles:
- I. Code Quality, II. Testing Standards, IV. Performance Requirements

Added sections: none
Removed sections: none

Templates requiring updates:
- .specify/templates/plan-template.md ✅ aligned (Constitution Check gate is
  generic and references the constitution without outdated tokens)
- .specify/templates/spec-template.md ✅ aligned (no mandatory sections changed)
- .specify/templates/tasks-template.md ✅ aligned (testing + performance task
  types supported by existing phases; tests remain opt-in per spec)
- .specify/templates/checklist-template.md ✅ aligned (no changes required)

Follow-up TODOs: none
-->

# Labor Hub Constitution

## Core Principles

### I. Code Quality

All code MUST be readable, maintainable, and idiomatic for its language and framework.

- Python code MUST follow PEP 8; Django code MUST follow standard Django project and
  app conventions (fat models / thin views, reusable apps, `urls.py` namespacing).
- Django templates MUST pass `djlint` linting and formatting; Python style violations
  MUST be resolved before merge. Linting is a required gate, not advisory.
- Business logic MUST live in models, managers, forms, or dedicated service/util modules
  (e.g. `publications/utils.py`) — never duplicated across views or templates (DRY).
- Names MUST be descriptive; functions and views MUST have a single clear responsibility.
  Dead code, commented-out blocks, and unused imports MUST be removed before merge.
- Every schema change MUST ship with its Django migration, and migrations MUST be
  reviewed as first-class code.

**Rationale**: The project is a multi-app Django codebase (accounts, events, publications,
seminars) maintained over time. Consistent, convention-driven code keeps apps
independently understandable and lowers the cost of every future change.

### II. Testing Standards

Correctness MUST be demonstrable through automated tests, not assumed.

- Every Django app MUST maintain tests in its `tests.py` (or a `tests/` package) covering
  models, forms, and views for the behavior it owns.
- Any bug fix MUST add a regression test that fails before the fix and passes after.
- New or changed views MUST have tests asserting status codes, authorization/permission
  boundaries, and the key context or side effects they produce.
- Data migrations that transform existing rows MUST be verified (test or documented
  manual verification) before merge.
- The full test suite (`python manage.py test`) MUST pass before any change is merged.
  A failing or skipped-without-justification test blocks merge.

**Rationale**: Authentication, applications, publications approval, and event data are
user-facing and stateful. Tests are the only durable guarantee that refactors and new
features do not silently break existing flows.

### III. User Experience Consistency

The interface MUST feel like one coherent product across every app and page.

- All pages MUST extend the shared base templates and reuse partials in
  `templates/partials/` rather than re-implementing layout, navigation, or chrome.
- Styling MUST use the project's TailwindCSS pipeline with Flowbite components. Shared
  structure (list items, pagination, empty states) MUST come from reusable partials in
  `templates/partials/`, and repeated controls (buttons, inputs, selects, nav links) MUST
  be defined once as `@apply` component classes in `static/src/input.css` — never as
  duplicated utility strings or inline styles.
- Forms MUST render through the shared field partials and template tags
  (`{% render_field %}` / `{% render_select %}`) for consistent field, label, and error
  presentation; `django-crispy-forms` and the Bootstrap 5 pack MUST NOT be used.
- User feedback MUST be consistent: success, error, and validation messages use the
  standard messaging patterns; error and empty states MUST be handled explicitly, never
  left as raw tracebacks or blank pages.
- Interactions MUST be responsive across common viewport sizes and MUST remain usable
  without JavaScript where feasible; Flowbite and Tagify MUST be used as progressive
  enhancement, not as a hard requirement for core flows.
- Interactive elements MUST be accessible: meaningful labels, keyboard operability, and
  sufficient color contrast.

**Rationale**: A research/community hub spans many content types. Consistent layout,
forms, and feedback let users transfer knowledge from one section to the next and keep
the product trustworthy.

### IV. Performance Requirements

Features MUST be efficient by default and MUST NOT degrade as data grows.

- Database access MUST avoid N+1 query patterns; views rendering related data MUST use
  `select_related` / `prefetch_related`, and querysets MUST select only needed fields
  where it matters.
- List and search views over unbounded data MUST paginate rather than loading full tables.
- Interactive page responses SHOULD target under 500ms server processing time under
  expected load; any endpoint that cannot meet this MUST document why and its mitigation.
- Static assets MUST be served through the compression/collectstatic pipeline
  (`django-compressor`) in production; media MUST be served via the configured storage
  backend, not the app process.
- Repeated expensive computations SHOULD be cached, and caching decisions MUST be
  documented with their invalidation strategy.

**Rationale**: Publications, events, and seminar listings accumulate indefinitely.
Query discipline and pagination keep the site responsive as content scales, protecting
both users and hosting cost.

## Technology & Security Standards

- The canonical stack is Django 5.2 on Python 3, PostgreSQL, Docker Compose for local
  and deployment parity, gunicorn as the WSGI server, and TailwindCSS for styling.
  Deviations from this stack MUST be justified and recorded.
- Secrets, credentials, and environment-specific configuration MUST come from environment
  variables or secret stores — never hardcoded or committed.
- User-supplied input MUST be validated through Django forms/model validation; template
  auto-escaping MUST NOT be disabled without a documented, reviewed reason.
- Authentication and authorization MUST use Django's built-in mechanisms; permission
  checks MUST guard every non-public view and action.
- File uploads (avatars, resumes, papers, PDFs) MUST validate type and size and be stored
  through the configured storage backend.
- Dependencies MUST be pinned in `requirements.txt`; known-vulnerable versions MUST be
  upgraded promptly.

## Development Workflow & Quality Gates

- Changes MUST be delivered via reviewed pull requests; at least one reviewer MUST confirm
  compliance with these principles before merge.
- The following gates MUST pass before merge: linting/formatting (Python + `djlint`),
  the full test suite, and successful application of migrations.
- Each pull request description MUST state which principles are affected and how the
  change satisfies them (or why an exception is warranted).
- New apps MUST be created with `manage.py startapp` and follow the existing app layout
  (models, views, urls, admin, forms, tests, migrations).
- Reviewers MUST reject changes that introduce N+1 queries, unpaginated large listings,
  inconsistent UI, or untested behavior unless an explicit, documented exception is
  approved.

## Governance

This constitution supersedes ad hoc conventions and prior undocumented practices for the
Labor Hub project. When guidance conflicts, the constitution wins.

- **Amendments**: Proposed changes MUST be submitted as a pull request that edits this
  file, states the rationale and impact, and updates all dependent templates and docs.
  Amendments take effect once merged.
- **Versioning**: This document uses semantic versioning. MAJOR increments for backward
  incompatible governance or principle removals/redefinitions; MINOR for a newly added
  principle or section or materially expanded guidance; PATCH for clarifications and
  non-semantic refinements.
- **Compliance review**: Every pull request review MUST verify compliance with the
  applicable principles. Complexity or deviations MUST be justified in writing and are
  approved only when a simpler compliant alternative is demonstrably insufficient.
- **Runtime guidance**: Contributors SHOULD consult `README.md` for setup, migration, and
  build commands; that guidance MUST stay consistent with this constitution.

**Version**: 2.0.0 | **Ratified**: 2026-07-20 | **Last Amended**: 2026-07-20
