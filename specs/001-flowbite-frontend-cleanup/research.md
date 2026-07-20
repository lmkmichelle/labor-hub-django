# Phase 0 Research: Flowbite Frontend Cleanup & Consolidation

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-07-20

All NEEDS CLARIFICATION items from the spec were resolved with the user during specification
(minimal-churn scope; blended abstraction). This document records the resulting technical decisions
and the smaller implementation-path choices the plan depends on.

---

## D1. Style-abstraction mechanism (blended)

**Decision**: Use a **blend** of two mechanisms, split by component granularity:

- **Structural components** (list/card item, pagination, buttons, page chrome, search bar) →
  reusable **Django template partials / inclusion tags** under `templates/partials/` and
  `core/templatetags/`.
- **Atomic form-control styling** (text input, select, textarea, file input, and the repeated
  "primary/secondary button" utility strings) → **Tailwind `@apply` component classes** declared
  once in `static/src/input.css`, compiled into the single committed `static/src/output.css`.

**Tailwind v4 mechanics** (project is CSS-first — confirmed no `tailwind.config.js`; `input.css`
uses `@import "tailwindcss"`, `@plugin`, `@source`): custom component classes are added with a
components layer, e.g.

```css
@layer components {
  .form-input   { @apply bg-neutral-secondary-medium border border-default-medium text-heading text-sm rounded-base focus:ring-brand focus:border-brand block w-full p-2.5; }
  .btn-primary  { @apply text-white bg-red-700 hover:bg-red-800 font-medium rounded-base text-sm px-5 py-2.5; }
  .btn-secondary{ @apply text-body bg-neutral-secondary-medium hover:bg-neutral-secondary-strong font-medium rounded-base text-sm px-5 py-2.5; }
}
```

**Rationale**: Honors the user's "abstracted into a single file" intent (the classes live in one
Tailwind source and compile into one CSS file) while reusing the project's existing
partial/inclusion-tag infrastructure (`render_field`, `_publications_list.html`) for structure,
where partials are more expressive than a CSS class. Keeps utility-first ergonomics for one-off
layout and reserves named classes for the genuinely repeated atoms.

**Alternatives considered**:
- *Pure `@apply` for everything*: rejected — structural layout (cards, pagination) is clearer as a
  partial with slots than as one mega-class; over-using `@apply` recreates a bespoke CSS framework.
- *Hand-authored rules in a single `base.css`*: rejected (and explicitly excluded by the user) —
  diverges from the Tailwind build, risks specificity fights with utilities, and duplicates tokens.
- *Pure template partials, no shared CSS*: rejected — still leaves ~15 identical ~90-char input
  strings copy-pasted inside partials; an `@apply` atom removes that duplication at its root.

---

## D2. Visual scope (minimal-churn) & page inventory

**Decision**: Strict, low-churn, presentation-only refactor. **Preserve** already-correct Flowbite
pages pixel-for-pixel; **fix** only pages broken by orphaned Bootstrap markup, bringing them to the
existing Flowbite design system. No redesign of correct pages.

**Page inventory** (drives which templates are touched):

| Page / template | Current state | Action |
|-----------------|---------------|--------|
| `templates/partials/_publications_list.html` (publications list, profile) | ✅ Correct Flowbite card | Preserve; promote to the unified list component |
| `templates/accounts/users_list.html` (scholars directory) | ✅ Flowbite grid (inline dup) | Preserve look; source card from unified component |
| `templates/partials/_list_display.html` (home ×4 lists) | ❌ Bootstrap `list-group`, unstyled | Fix → unified list component |
| `templates/seminars/seminars_list.html` | ❌ inline Bootstrap `list-group` | Fix → unified list component |
| `templates/events/event_list.html` | ⚠️ bespoke inline layout | Normalize to unified component (preserve intent) |
| All paginated lists (seminars, scholars, …) | ❌ Bootstrap `pagination` markup, unstyled | Fix → shared `_pagination.html` |
| `templates/registration/login.html` | ⚠️ hand-rolled Flowbite fields | Migrate fields to `render_field` |
| `templates/publications/publication_form.html` | ⚠️ hand-rolled fields (~10×), Tagify dup | Migrate to `render_field`; single Tagify load |
| `apply.html`, `event_form.html`, `edit_profile.html` | ✅ use `render_field` | Preserve; remove commented block in edit_profile |
| Detail pages (`publication_detail`, `event_detail`, `profile`) | ✅ mostly Flowbite + inline styles | Preserve; lift inline `style=""` to tokens/classes |
| `templates/base.html` | ⚠️ nav markup bug, CDN Flowbite JS, nav-link dup | Fix bug, local JS, dedupe nav-link |

**Rationale**: Matches the user's chosen scope (Q1 → A). Limits diff size and review risk; makes
"no visual regression on correct pages" a checkable acceptance criterion (SC-002 / quickstart).

**Alternatives considered**: broader restyling / open redesign — rejected by the user; would inflate
risk and turn a cleanup into a redesign.

---

## D3. List/card consolidation without changing views

**Decision**: Introduce one unified list-item partial (e.g. `templates/partials/_list_item.html`,
evolved from the Flowbite `_publications_list.html` card) with an explicit, documented input
contract (title, subtitle/description, meta/date, badge, url, image?). Callers pass those inputs via
`{% include ... with ... %}`. The home page keeps building its `item.*` dictionaries **unchanged**;
model-driven callers map their fields to the same inputs in-template.

**Rationale**: FR-002 asks for one shared component; Out-of-Scope forbids view-behavior changes. A
presentation-layer contract satisfies both — the home view's context stays as-is, and consolidation
happens entirely in templates. Avoids touching Python view logic or querysets.

**Alternatives considered**:
- *Change views to pass normalized objects*: rejected — that is a view-behavior change (out of
  scope) and risks regressions in context building.
- *Keep separate partials but share CSS only*: rejected — leaves five structural implementations,
  failing SC-003 ("exactly one canonical definition").

---

## D4. Form-field consolidation

**Decision**: Route **all** form fields through the existing `{% render_field %}` /
`{% render_select %}` inclusion tags (`core/templatetags/form_tags.py` → `_form_field.html` /
`_select_field.html`). Migrate the hand-rolled fields in `login.html`, `publication_form.html`, and
the advisor `<select>` in `apply.html`. De-duplicate per-widget class strings inside the two field
partials by referencing the `.form-input` / select `@apply` atoms from D1.

**Rationale**: FR-004/FR-005/SC-004 require a single field path with no duplicated markup. The
abstraction already exists and already renders correctly on three pages — this extends it, not
invents it.

**Alternatives considered**: reinstating crispy-forms as the field renderer — rejected: crispy is
Bootstrap-based (the stack being removed) and its layout code is already dead.

---

## D5. Flowbite JavaScript delivery

**Decision**: Serve Flowbite's JS from a **version-locked local static file** matching the installed
npm package (Flowbite **4.0.1**): copy `node_modules/flowbite/dist/flowbite.min.js` into
`static/js/` and reference it via `{% static %}`, so it is handled by `collectstatic`/compressor and
always matches the compiled CSS. Remove the `cdn.jsdelivr.net/npm/flowbite@4.0.1` `<script>` in
`base.html`.

**Rationale**: FR-011 + SC-009 require build-consistent, single-source asset loading; Principle IV
requires static assets through the collectstatic pipeline. The npm build only emits CSS, so the JS
must be delivered explicitly; a committed local file keeps runtime Node-free (Media3-friendly) and
version-aligned. A copy step can be added to the build later, but committing the file is sufficient
now.

**Alternatives considered**:
- *Keep the pinned CDN (`@4.0.1`)*: works and is low-effort, but adds an external runtime dependency
  and can drift from the local package; weaker fit with the collectstatic principle.
- *Bundle Flowbite JS via a JS bundler*: rejected — the project has no JS build step; adding one is
  scope creep for this cleanup.

---

## D6. Tagify single-load

**Decision**: Load Tagify **exactly once** on the pages that need it (publication form). Choose one
delivery consistent with D5 — a single committed local `static/js/` asset (preferred) or one pinned
CDN reference — and remove the duplicate `<script>`/CSS includes currently in
`publication_form.html` (loaded twice) plus reconcile the separate local `js/tagify.js`.

**Rationale**: FR-011 / SC-009 (each asset at most once per page, sourced consistently). Duplicate
loads risk double-initialization of the tag input.

**Alternatives considered**: leaving both includes with defensive guards — rejected as unnecessary
complexity; one include is simpler and correct.

---

## D7. Shared pagination component

**Decision**: Create one `templates/partials/_pagination.html` rendering Flowbite-styled pagination
from a standard Django `Page`/`Paginator` context (`page_obj`, `is_paginated`, querystring
preservation for filters). Replace every per-page Bootstrap `pagination`/`page-item`/`page-link`
block with an `{% include %}` of it.

**Rationale**: FR-003 / SC-003. The Bootstrap pagination currently renders unstyled (no Bootstrap
CSS). One Flowbite partial fixes all paginated lists identically and preserves existing pagination
*behavior* (page size, query params) — presentation-only.

**Alternatives considered**: a custom template tag that emits pagination — heavier than a partial for
no added benefit here; a partial with `{% include %}` is the idiomatic, reviewable choice.

---

## D8. Color/typography token standardization

**Decision**: Standardize on the project's **semantic design tokens** (`text-heading`, `text-body`,
`bg-neutral-*`, `border-default*`, `focus:ring-brand`, Flowbite-typography `format` classes).
Replace ad-hoc raw palette values (`text-gray-500`, `dark:text-gray-300`, `text-red-600`,
`bg-gray-100`, `border-gray-300`) used for the same roles (help text, error text, controls) with the
corresponding token. Undefined custom classes (`list-title`, `box-list`, `title`, `section`, …) are
removed or replaced with real Flowbite/token equivalents.

**Rationale**: FR-007 / SC-002. Consistent tokens are the vocabulary the shared components (D1) rely
on and keep dark-mode/theming coherent.

**Alternatives considered**: keep raw palette values where they "look the same" — rejected: perpetuates
the inconsistency this feature exists to remove.

---

## D9. Testing & validation approach

**Decision**: Treat validation as **lint + build + render checks**, with **optional lightweight view
smoke tests** as the regression guard:

1. `npm run build` must succeed and regenerate `output.css`.
2. `djlint` must pass with zero errors on all templates (FR-013 / SC-008).
3. `python manage.py test` must pass (SC-008). Apps currently ship empty `tests.py` stubs, so this
   is trivially green today; recommend adding minimal smoke tests asserting **HTTP 200 + expected
   template used** for each touched page (home, publications list/detail, scholars, events
   list/detail, seminars, profile, each form). These catch template-syntax errors, the malformed
   dropdown, missing includes, and missing context introduced by the refactor.
4. Manual page-by-page visual pass per [quickstart.md](./quickstart.md) confirms no unstyled elements
   and no regression on already-correct pages.

**Rationale**: The defects being fixed are template/rendering issues, best caught by render/lint
checks than by unit assertions. Smoke tests give a cheap, durable guard aligned with Principle II
("new/changed views MUST have tests asserting status codes") without expanding scope into
feature-level testing. Form *behavior* is unchanged by construction (FR-014), so no new form-logic
tests are required.

**Alternatives considered**: full form-submission/integration test suite — valuable but beyond this
cleanup's scope; can be a follow-up. Zero tests — leaves the rendering fixes unguarded against
future regressions.

---

## D10. Constitution amendment (governance)

**Decision**: Amend `.specify/memory/constitution.md` **Principle III (User Experience Consistency)**
to replace the `django-crispy-forms` + Bootstrap 5 pack + HTMX mandate with the **Tailwind/Flowbite
component standard** (shared partials/inclusion-tags for structure; `@apply` component classes for
atoms; Flowbite JS/Tagify as progressive enhancement). Because this **redefines a principle**, bump
the version **MAJOR → 2.0.0** per the constitution's own versioning rule, update the Sync Impact
Report, and set Last Amended to the change date.

**Rationale**: FR-015 / Dependencies. Without it, the finished cleanup is permanently non-compliant
with governance. The amendment is delivered as a reviewed change (Amendments rule).

**Alternatives considered**: MINOR bump — rejected: removing/redefining a mandated toolchain is
backward-incompatible governance, which the rules classify as MAJOR. Deferring the amendment —
rejected: leaves a standing conflict between the codebase and its constitution.

---

## Open questions

None. All spec clarifications are resolved; the decisions above fully specify the design inputs for
Phase 1.
