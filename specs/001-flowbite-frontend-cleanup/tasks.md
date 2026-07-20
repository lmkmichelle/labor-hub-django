---
description: "Task list for Flowbite Frontend Cleanup & Consolidation"
---

# Tasks: Flowbite Frontend Cleanup & Consolidation

**Input**: Design documents from `/specs/001-flowbite-frontend-cleanup/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/ui-components.md](./contracts/ui-components.md)

**Tests**: This is a presentation-only refactor; the spec did not request TDD. A **lightweight,
OPTIONAL** view-smoke-test track is included per research D9 (asserts HTTP 200 + template used) as a
regression guard for the rendering fixes. Optional tasks are labeled `(OPTIONAL)` and may be skipped.

**Organization**: Tasks are grouped by user story. Story independence: US1 makes the site render
correctly, US2 makes every element come from one source, US3 deletes the dead stack + reconciles
governance. Foundational phase creates the shared building blocks all stories consume.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 (Setup/Foundational/Polish have no story label)
- All paths are repository-root-relative.

## Path Conventions

Single Django project (multi-app), server-rendered templates. Work lands in `templates/`,
`static/src/input.css`, `core/templatetags/`, and three apps' `forms.py` + `nole/settings.py` +
`requirements.txt`. No new app or split-repo structure.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the single home for shared style classes and confirm the build/lint gates run.

- [X] T001 Add an empty `@layer components { }` block to `static/src/input.css` (the single home for `@apply` component classes), then run `npm run build` and confirm `static/src/output.css` regenerates with no errors.
- [X] T002 [P] Capture the template-lint baseline: run `djlint templates --lint` and record current issues so the Phase 6 "zero errors" gate is measurable.
- [X] T003 [P] (OPTIONAL) Confirm the Django test runner executes (`python manage.py test`) and add an empty smoke-test module skeleton in `core/tests.py` for the per-story smoke tests below.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create the canonical reusable building blocks (CSS atoms + shared partials) that **every**
user story consumes. Per [contracts/ui-components.md](./contracts/ui-components.md).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Define the `@apply` component classes in the `@layer components` block of `static/src/input.css` — `.form-input`, `.form-select`, `.btn-primary`, `.btn-secondary`, `.card-surface`, `.nav-link` (bodies = the current utility strings from spec Findings F, using semantic tokens per FR-007); then `npm run build`. (FR-006)
- [X] T005 [P] Create the unified list/card item partial `templates/partials/_list_item.html` per the contract (inputs: `title`, `url?`, `subtitle?`, `description?`, `meta?`, `badge?`, `image?`; Flowbite `.card-surface` markup only; optional params render nothing). (FR-002)
- [X] T006 [P] Create the shared pagination partial `templates/partials/_pagination.html` (inputs: `page_obj`, `is_paginated`, `querystring?`; Flowbite styling; renders nothing when not paginated; preserves querystring). (FR-003)
- [X] T007 [P] Create the shared empty-state partial `templates/partials/_empty_state.html` (input: `text`; consistent styled "nothing to display" message). (FR-002 / Edge Cases)
- [X] T008 Dedupe the field partials `templates/partials/_form_field.html` and `templates/partials/_select_field.html` so their control markup references `.form-input` / `.form-select` instead of per-widget duplicated class strings. (FR-005) — depends on T004.

**Checkpoint**: Canonical components exist and build cleanly — user stories can begin.

---

## Phase 3: User Story 1 - Every page renders with one consistent, correct visual style (Priority: P1) 🎯 MVP

**Goal**: Fix pages broken by orphaned Bootstrap markup so the whole site renders correctly and
consistently in Flowbite — lists, pagination, empty states, and the nav dropdown.

**Independent Test**: Browse home, seminars list, and the scholars directory across multiple pages;
every list card, pagination control, and empty state renders styled in Flowbite with correct spacing;
no plain/unstyled elements; the nav dropdown is well-formed and keyboard-operable.

### Tests for User Story 1 (OPTIONAL)

- [X] T009 [P] [US1] (OPTIONAL) Smoke tests in `core/tests.py` asserting HTTP 200 + expected template for the home page (`templates/core/home.html`) and seminars list (`templates/seminars/seminars_list.html`), including a paginated request.

### Implementation for User Story 1

- [X] T010 [US1] Convert the four home-page lists: replace the Bootstrap `list-group` markup in `templates/partials/_list_display.html` with `{% include "partials/_list_item.html" %}` (+ `_empty_state.html`), mapping the view-built `item.*` dicts to the partial inputs **without changing the view context**; remove orphaned custom classes (`list-title`, `box-list`, `box-list-headline`, `list-description`, `title`, `section`). (FR-001, FR-002) — depends on T005, T007.
- [X] T011 [US1] Convert `templates/seminars/seminars_list.html` inline Bootstrap `list-group` to `_list_item.html` + `_empty_state.html`. (FR-001, FR-002) — depends on T005, T007.
- [X] T012 [US1] Replace every hand-rolled Bootstrap pagination block (`pagination`/`page-item`/`page-link`) with `{% include "partials/_pagination.html" %}`, preserving active search/filter querystring — in `templates/seminars/seminars_list.html` and `templates/accounts/users_list.html` (and any other paginated list). (FR-001, FR-003) — depends on T006; sequence after T011 for `seminars_list.html`.
- [X] T013 [US1] Fix the malformed authenticated-user dropdown `<li>`/`<div>` nesting in `templates/base.html`. (FR-012)
- [X] T014 [US1] Verify all four home lists and the seminars list render the shared styled empty state when data is absent; adopt `_empty_state.html` anywhere still missing it. (Edge Cases / SC-002)

**Checkpoint**: MVP — the site renders correctly and consistently on every previously-broken page.

---

## Phase 4: User Story 2 - Shared UI elements come from a single reusable source (Priority: P2)

**Goal**: Every equivalent element (list card, form field, button, input, nav link, assets) comes
from exactly one canonical source; duplicated strings and scattered inline styles are eliminated.

**Independent Test**: For each shared element, confirm exactly one definition and that changing it
once (e.g., `.btn-primary`) visibly updates every usage after `npm run build`; a grep shows no
duplicated input/button strings, no Bootstrap-only classes, and each third-party asset loaded once.

### Tests for User Story 2 (OPTIONAL)

- [ ] T015 [P] [US2] (OPTIONAL) Tests in `core/tests.py` asserting the publications list, scholars directory, and events list pages return 200 and use the shared `_list_item.html` (assert via rendered marker/template).

### Implementation for User Story 2

- [X] T016 [P] [US2] Migrate `templates/partials/_publications_list.html` (publications list + profile) to render items via `_list_item.html` / `.card-surface`, preserving the current look. (FR-002, SC-003) — depends on T005.
- [X] T017 [US2] Migrate the scholar cards in `templates/accounts/users_list.html` to `_list_item.html` / `.card-surface`, preserving the grid look. (FR-002) — depends on T005; sequence after T012 (same file).
- [X] T018 [P] [US2] Migrate the bespoke layout in `templates/events/event_list.html` to `_list_item.html`, preserving intent. (FR-002) — depends on T005.
- [X] T019 [US2] Migrate all hand-rolled form fields to the single field path (`{% render_field %}` / `{% render_select %}`): `templates/registration/login.html`, `templates/publications/publication_form.html`, and the advisor `<select>` in `templates/accounts/apply.html`. (FR-004, SC-004) — depends on T008.
- [X] T020 [US2] Replace duplicated button/input utility strings with `.btn-primary` / `.btn-secondary` / `.form-input` across `templates/registration/login.html`, `templates/accounts/apply.html`, `templates/events/event_form.html`, `templates/accounts/edit_profile.html`, `templates/publications/publication_form.html`. (FR-006, SC-005) — depends on T004; sequence after T019 (same files).
- [X] T021 [US2] Dedupe the six repeated nav-link strings in `templates/base.html` to `.nav-link`. (FR-006) — depends on T004; sequence after T013 (same file).
- [X] T022 [US2] Lift scattered inline `style="…"` rules and standardize raw palette values to semantic tokens (FR-007) in `templates/accounts/users_list.html`, `templates/events/event_form.html`, `templates/publications/publication_detail.html`, `templates/events/event_detail.html`, `templates/accounts/profile.html`, and the converted `templates/partials/_list_display.html`. (FR-006, FR-007, SC-005) — sequence after T017 (users_list.html).
- [X] T023 [US2] Consolidate third-party assets: copy the version-locked Flowbite 4.0.1 JS to `static/js/flowbite.min.js` and reference it once via `{% static %}` in `templates/base.html` (remove the `cdn.jsdelivr.net/npm/flowbite` `<script>`); load Tagify exactly once in `templates/publications/publication_form.html` (remove the duplicate include, reconcile `static/js/tagify.js`). (FR-011, SC-009) — sequence after T021 (base.html).
- [X] T024 [US2] Run `npm run build`; verify the "change once" property by temporarily tweaking `.btn-primary` and confirming every button updates, then revert the tweak. (SC-003)

**Checkpoint**: Every shared element has one canonical source; no duplicated strings or stray assets.

---

## Phase 5: User Story 3 - The legacy stack is fully removed and governance is reconciled (Priority: P3)

**Goal**: No trace of the abandoned Bootstrap/crispy/HTMX stack remains, and the constitution is
amended to codify the Tailwind/Flowbite standard.

**Independent Test**: The crispy/HTMX packages and config are gone, the app still starts and serves
every page, all forms submit/validate identically, and the constitution reflects the new stack.

### Tests for User Story 3 (OPTIONAL)

- [ ] T025 [P] [US3] (OPTIONAL) Test in `core/tests.py` that the app boots and a representative form (e.g., login or application) submits with valid and invalid input producing the same field set and validation outcomes as before removal. (SC-007)

### Implementation for User Story 3

- [X] T026 [US3] Remove the dead crispy scaffolding (`FormHelper` / `Layout` / `Submit` / `ButtonHolder` / `HTML`) from `accounts/forms.py` and `events/forms.py` **without changing any field or validation**; also remove the unused `from email.mime import application` import and the commented resume-save block in `accounts/forms.py`. (FR-008, FR-010, FR-014)
- [X] T027 [P] [US3] Remove the stray `{% load crispy_forms_tags %}` from `templates/accounts/application_submitted.html` and the commented `{% comment %}` avatar block from `templates/accounts/edit_profile.html`. (FR-008, FR-010)
- [X] T028 [US3] Remove `crispy_forms` and `crispy_bootstrap5` from `INSTALLED_APPS` and delete `CRISPY_ALLOWED_TEMPLATE_PACKS` / `CRISPY_TEMPLATE_PACK` in `nole/settings.py`. (FR-008)
- [X] T029 [P] [US3] Remove `django-crispy-forms`, `crispy-bootstrap5`, and `django-htmx` from `requirements.txt` and refresh the environment (`pip install -r requirements.txt`). (FR-008, FR-009)
- [X] T030 [US3] Amend `.specify/memory/constitution.md` Principle III (User Experience Consistency) to codify the Tailwind/Flowbite component standard (shared partials/tags for structure; `@apply` atoms for controls; Flowbite/Tagify as progressive enhancement); bump the version MAJOR → **2.0.0**, update the Sync Impact Report and the Last Amended date. (FR-015)

**Checkpoint**: Dead stack removed; app healthy; governance consistent with the codebase.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Enforce the quality gates and validate the whole feature end-to-end.

- [X] T031 [P] Run `djlint templates --lint` and resolve all template lint errors to **zero**. (FR-013, SC-008)
- [X] T032 Run `python manage.py test` (including any optional smoke tests) and confirm the suite passes. (SC-008)
- [X] T033 Execute the [quickstart.md](./quickstart.md) page-by-page visual + non-regression checklist and the grep checks (no Bootstrap-only classes → SC-001; no Flowbite CDN → SC-009; no `crispy`/`django-htmx` in `requirements.txt` → SC-006); confirm SC-001–SC-009. 
- [X] T034 [P] Update `README.md` setup/build guidance to match the amended stack (Flowbite JS static asset; no crispy/HTMX), keeping runtime guidance consistent with the amended constitution.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; **blocks all user stories**. T008 depends on T004.
- **User Stories (Phase 3–5)**: depend on Foundational. US3 is largely file-disjoint from US1/US2 and
  can proceed in parallel with them; US1 is the MVP and is recommended first.
- **Polish (Phase 6)**: depends on all targeted stories being complete.

### Story-level notes

- **US1 (P1)**: after Foundational — no dependency on US2/US3. Delivers the MVP (correct site).
- **US2 (P2)**: after Foundational — extends the same components everywhere. Shares files with US1
  (`base.html`, `users_list.html`, `seminars_list.html`), so sequence those tasks after their US1
  counterparts (noted per task); otherwise independently testable.
- **US3 (P3)**: after Foundational — touches `forms.py`, `settings.py`, `requirements.txt`, and the
  constitution (disjoint from US1/US2 templates), so it can run anytime after Phase 2.

### Same-file sequencing (do NOT parallelize these)

- `templates/base.html`: T013 → T021 → T023.
- `templates/accounts/users_list.html`: T012 → T017 → T022.
- `templates/seminars/seminars_list.html`: T011 → T012.
- Form templates (login/apply/event_form/edit_profile/publication_form): T019 → T020.

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational: T005, T006, T007 in parallel (three new files); T004 before T008.
- US2 list migrations: T016 and T018 in parallel (different files); T017 gated by T012.
- US3: T027 and T029 in parallel with T026/T028 (different files).
- Polish: T031 and T034 in parallel.

---

## Parallel Example: Foundational building blocks

```bash
# After T004, create the three shared partials together (different files):
Task: "Create templates/partials/_list_item.html"        # T005
Task: "Create templates/partials/_pagination.html"       # T006
Task: "Create templates/partials/_empty_state.html"      # T007
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (blocking) → 3. Phase 3 US1.
4. **STOP and VALIDATE**: browse every page; confirm no unstyled elements, styled pagination, styled
   empty states, well-formed nav. This alone yields a coherent, correct site.

### Incremental Delivery

1. Setup + Foundational → building blocks ready.
2. US1 → correct, consistent rendering (MVP).
3. US2 → single reusable source everywhere; duplication and stray assets gone.
4. US3 → dead stack removed; constitution amended.
5. Polish → lint/test/quickstart gates green (SC-008) and full validation (SC-001–SC-009).

### Notes

- `[P]` = different files, no dependencies. Respect the same-file sequencing list above.
- Presentation-only: never change form fields, validation, view context, models, or URLs (FR-014).
- Minimal-churn: preserve the appearance of already-correct Flowbite pages; only fix broken ones.
- Rebuild CSS (`npm run build`) after any change to `static/src/input.css` or component classes.
- Commit after each task or logical group; keep the constitution amendment (T030) in its own commit.
