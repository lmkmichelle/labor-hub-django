# Phase 1 Data Model: Reusable UI Components (Presentation Model)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This is a **presentation-only** feature: there are **no database entities, models, or migrations**.
The "data model" here is the vocabulary of **reusable UI building blocks** the cleanup standardizes —
their inputs, states, and the single source each becomes. Concrete interface signatures live in
[contracts/ui-components.md](./contracts/ui-components.md); this file defines *what* each component is
and the rules it must satisfy.

---

## Component entities

### 1. List / Card Item
The atomic unit of any listing (scholars, papers, events, seminars, home lists, profile papers).

| Field | Type | Req? | Notes |
|-------|------|------|-------|
| `title` | string | ✅ | Primary label |
| `url` | string | ⬜ | If present, the item (or its title) links here |
| `subtitle` | string | ⬜ | Secondary line (e.g., authors, venue) |
| `description` | string | ⬜ | Longer body/summary |
| `meta` | string | ⬜ | Date or supplementary text |
| `badge` | string | ⬜ | Status/category chip |
| `image` | string(url) | ⬜ | Optional avatar/thumbnail |

- **Consolidates**: `_list_display.html`, `_publications_list.html`, `seminars_list` inline,
  `users_list` inline card, `event_list` inline → **one** partial.
- **Validation rules**: unstyled Bootstrap classes MUST NOT appear; only Flowbite/token classes.
  Callers MUST NOT change view context to use it (dict-driven and model-driven callers both map into
  the fields above in-template).
- **States**: default; hover (Flowbite card hover); **empty state** — a listing with zero items MUST
  render a consistent styled "nothing to display" message, not a blank area.

### 2. Form Field Wrapper
Label + control + help text + error for one field, across all widget types.

| Field | Type | Req? | Notes |
|-------|------|------|-------|
| `field` | Django BoundField | ✅ | Passed to `render_field` / `render_select` |
| `label` | string | derived | From the form field; not re-specified in markup |
| `help_text` | string | ⬜ | Rendered in the token help-text style |
| `errors` | list | derived | Rendered in the token error style |

- **Consolidates**: hand-rolled fields in `login.html`, `publication_form.html`, advisor select in
  `apply.html` → the existing `render_field` / `render_select` path (sole field renderer).
- **Validation rules**: field names, labels, help text, and validation behavior MUST be unchanged
  (FR-014). Per-widget control classes MUST reference the shared `.form-input`/select atom, not
  inline duplicated strings (FR-005).
- **States**: normal; focus (`focus:ring-brand`); error (token error color + message); disabled.
- **Widget coverage**: text, email, password, textarea, select, multi-select, file, date, checkbox,
  and the Tagify tag input.

### 3. Button (Primary / Secondary)
Submit and cancel/secondary actions.

- **Primary**: `.btn-primary` (`@apply` atom). **Secondary/Cancel**: `.btn-secondary`.
- **Consolidates**: the copy-pasted button utility strings across login/apply/event/edit-profile/
  publication forms → one class each.
- **Validation rules**: exactly one canonical definition per variant; changing it updates 100% of
  usages (SC-003).
- **States**: default, hover, focus, disabled.

### 4. Pagination Control
Prev / numbered / next navigation for paginated lists.

| Field | Type | Req? | Notes |
|-------|------|------|-------|
| `page_obj` | Django Page | ✅ | Standard paginator page |
| `is_paginated` | bool | ✅ | Hides control when false |
| `querystring` | string | ⬜ | Preserves active filters/search across pages |

- **Consolidates**: per-page Bootstrap `pagination`/`page-item`/`page-link` markup → one
  `_pagination.html`.
- **Validation rules**: pagination **behavior** (page size, query params) unchanged; only
  presentation changes. Renders nothing when `is_paginated` is false.
- **States**: first page (no prev), last page (no next), current-page highlight.

### 5. Search / Filter Bar
Search box with optional filter dropdown.

- **Source**: existing `_search_form.html` — already shared; **remains the single source**.
- **Validation rules**: no duplicate/bespoke search markup elsewhere; behavior unchanged.

### 6. Page Shell
Global layout: `<head>`/asset loading, navigation, content wrapper, footer.

- **Source**: `base.html` — the single host for global chrome and asset loading.
- **Validation rules**: nav dropdown markup MUST be well-formed (fix FR-012 nesting bug); nav-link
  classes defined once (FR-006); Flowbite JS + Tagify each loaded at most once and build-consistent
  (FR-011 / SC-009).

### 7. Design Tokens
The semantic color/typography vocabulary every component uses.

- **Set**: `text-heading`, `text-body`, `bg-neutral-*`, `border-default*`, `focus:ring-brand`,
  Flowbite-typography `format` classes, brand red for primary actions.
- **Validation rules**: components MUST use tokens, not raw palette values, for shared roles (help
  text, error text, controls) — FR-007.

---

## Removal map (dead-stack teardown)

| Item | Location | Action | Requirement |
|------|----------|--------|-------------|
| `crispy_forms`, `crispy_bootstrap5` apps | `nole/settings.py` INSTALLED_APPS | remove | FR-008 |
| `CRISPY_ALLOWED_TEMPLATE_PACKS`, `CRISPY_TEMPLATE_PACK` | `nole/settings.py` | remove | FR-008 |
| `FormHelper`/`Layout`/`Submit`/`ButtonHolder`/`HTML` scaffolding | `accounts/forms.py`, `events/forms.py` | remove (fields/validation untouched) | FR-008 |
| `{% load crispy_forms_tags %}` (unused) | `application_submitted.html` | remove | FR-008 |
| `django-crispy-forms`, `crispy-bootstrap5` | `requirements.txt` | unpin/remove | FR-008 |
| `django-htmx` (unused) | `requirements.txt` | remove | FR-009 |
| Commented avatar block | `edit_profile.html` | remove | FR-010 |
| Commented resume-save block + `from email.mime import application` | `accounts/forms.py` | remove | FR-010 |
| Orphaned custom classes (`list-title`, `box-list`, `title`, `section`, …) | list templates | remove/replace | FR-002/FR-007 |
| CDN Flowbite `<script>` | `base.html` | replace with local version-locked static | FR-011 |
| Duplicate Tagify includes | `publication_form.html` (+ `js/tagify.js`) | reduce to one | FR-011 |

**Invariant**: every removal above is either unused or has an equivalent replacement, so **no
rendered output or form behavior changes** as a result (FR-014, SC-006, SC-007).

---

## Governance artifact

`.specify/memory/constitution.md` **Principle III** is amended (Tailwind/Flowbite standard) with a
**MAJOR** version bump to **2.0.0** and an updated Sync Impact Report (FR-015 / research D10).

---

## Traceability

| Component / item | Requirements | Success criteria |
|------------------|--------------|------------------|
| List/Card Item | FR-001, FR-002 | SC-001, SC-002, SC-003 |
| Form Field Wrapper | FR-004, FR-005, FR-014 | SC-004, SC-007 |
| Button | FR-006 | SC-003, SC-005 |
| Pagination | FR-001, FR-003 | SC-002, SC-003 |
| Search Bar | FR-002 | SC-003 |
| Page Shell | FR-011, FR-012 | SC-009 |
| Design Tokens | FR-006, FR-007 | SC-002, SC-005 |
| Removal map | FR-008, FR-009, FR-010 | SC-006 |
| Lint/build/tests | FR-013 | SC-008 |
| Constitution amendment | FR-015 | — |
