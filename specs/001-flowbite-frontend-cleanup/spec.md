# Feature Specification: Flowbite Frontend Cleanup & Consolidation

**Feature Branch**: `001-flowbite-frontend-cleanup`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "Major codebase cleanup — complete the mid-development transition from Bootstrap + crispy-forms + HTMX to Tailwind + Flowbite. Scattered/messy list-item partials for different list-card styles, inline CSS instead of a single abstracted file, lots of repeated code, mixed/inconsistent Bootstrap + crispy form components remaining, and inconsistent abstraction overall. Find additional issues and write a specification plan for the cleanup."

## Overview

The Labor Hub UI was migrated part-way from a **Bootstrap 5 + django-crispy-forms + HTMX**
stack to a **TailwindCSS v4 + Flowbite** stack. The migration was never finished, so the
codebase now carries **two overlapping visual systems at once**. Only the Tailwind/Flowbite
stylesheet is actually loaded, so every page that still uses leftover Bootstrap markup renders
**unstyled or misaligned**, while the same UI concepts (list cards, form fields, buttons,
pagination) are re-implemented several different ways across templates.

This feature finishes the transition: it converges the interface onto a single Tailwind/Flowbite
component vocabulary, removes the dead legacy stack, eliminates duplicated markup and scattered
inline styles, and makes each shared UI element come from one reusable source.

This is a **refactor / cleanup** feature. It changes presentation and internal structure only —
it does **not** add end-user features or change data, form fields, validation rules, or business
logic.

## Current-State Findings *(evidence gathered from the codebase)*

**A. Two competing style systems on every listing/detail page.** Bootstrap utility and component
classes (`list-group`, `list-group-item`, `d-flex`, `w-100`, `justify-content-between`,
`align-items-*`, `text-muted`, `row`, `col-*`, `container`, `section`, `pagination`, `page-item`,
`page-link`, `badge`, `bg-secondary`) remain in templates, but **no Bootstrap stylesheet is
loaded** (only `static/src/output.css` + `static/css/base.css`). These elements therefore render
**without their intended styling** — a real visual defect, not merely stylistic drift. Affected
areas include the home-page lists, the seminars list, and the pagination controls on multiple
list pages.

**B. List / card rendering is done at least five different ways:**

1. `templates/partials/_list_display.html` — a generic **Bootstrap** `list-group` partial, used
   **four times** on the home page (new scholars, recent papers, upcoming events, upcoming
   seminars) and driven by view-built `item.*` dictionaries.
2. `templates/partials/_publications_list.html` — a **Flowbite** card list (used by the
   publications list and the profile page).
3. `templates/seminars/seminars_list.html` — **inline Bootstrap** `list-group` markup
   (a hand-rolled near-duplicate of `_list_display`).
4. `templates/accounts/users_list.html` — **inline Flowbite** card grid.
5. `templates/events/event_list.html` — its own bespoke inline layout.

Additionally, references to custom classes (`list-title`, `box-list`, `box-list-headline`,
`list-description`, `title`, `section`) appear across these partials but are **not defined** in
the loaded CSS (`base.css` contains only world-map styles), so they contribute nothing.

**C. Form rendering uses three coexisting patterns:**

1. The custom `core/templatetags/form_tags.py` tags **`{% render_field %}` / `{% render_select %}`**
   (Flowbite field partials) — used by `apply.html`, `event_form.html`, `edit_profile.html`.
   This is the intended Flowbite abstraction.
2. **Hand-rolled Flowbite inputs** with fully duplicated class strings — `login.html` and
   `publication_form.html` (which re-types the same ~90-character input class on ~10 fields),
   plus the advisor `<select>` in `apply.html`.
3. **Dead crispy-forms scaffolding** — `accounts/forms.py` and `events/forms.py` build
   `FormHelper` / `Layout` / `Submit` / `ButtonHolder` / `HTML(...)` objects with Bootstrap
   button classes (`btn btn-primary`, `btn btn-secondary`), but **no template renders `{% crispy %}`**.
   The only crispy reference left in templates is a stray `{% load crispy_forms_tags %}` in
   `application_submitted.html` (a static confirmation page that never uses it). The crispy layout
   code is therefore **entirely dead**.

**D. HTMX is entirely unused.** `django-htmx` is pinned in `requirements.txt`, but it is not in
`INSTALLED_APPS`, has no middleware, and there are **zero `hx-*` attributes** anywhere in the
templates or Python. It is dead weight.

**E. Legacy dependencies and configuration remain wired up.** `INSTALLED_APPS` still registers
`crispy_forms` and `crispy_bootstrap5`; `settings.py` still sets `CRISPY_ALLOWED_TEMPLATE_PACKS`
and `CRISPY_TEMPLATE_PACK = "bootstrap5"`; `requirements.txt` still pins `django-crispy-forms`,
`crispy-bootstrap5`, and `django-htmx`.

**F. Repeated Tailwind class strings** (the same long utility string copy-pasted many times):

- **Primary button** (`text-white bg-red-700 hover:bg-red-800 … rounded-base …`) — duplicated on
  every form (login, apply, event, edit-profile, publication).
- **Secondary / Cancel button** (`text-body bg-neutral-secondary-medium …`) — same set of pages.
- **Card surface** (`bg-neutral-primary-soft block max-w-full p-6 border border-default rounded-base
  shadow-xs hover:bg-neutral-secondary-medium`) — publications list and users list.
- **Text input** (`bg-neutral-secondary-medium border border-default-medium text-heading text-sm
  rounded-base focus:ring-brand focus:border-brand block w-full …`) — repeated ~15 times across
  login, publication form, both form-field partials, and the event-list date pickers.
- **Navbar link** — the same block/hover/active class string repeated for all six nav items in
  `base.html`.

**G. Scattered inline CSS** that belongs in the shared stylesheet or a reusable class:
`style="margin-bottom: … ; padding: …"`, `style="font-weight:100"`, `style="object-fit: cover"`,
`style="text-decoration: underline"`, `style="font-size:2rem"`, and `style="color: var(--primary)"`
appear across `_list_display.html`, `users_list.html`, `event_form.html`, `publication_detail.html`,
`event_detail.html`, and `profile.html`.

**H. Inconsistent color tokens.** Semantic design tokens (`text-heading`, `text-body`,
`bg-neutral-*`, `border-default*`, `focus:ring-brand`) are mixed with raw palette values
(`text-gray-500`, `dark:text-gray-300`, `text-red-600`, `bg-gray-100`, `border-gray-300`,
`text-gray-900`) for the same roles (help text, error text, form controls).

**I. Inconsistent / duplicated third-party asset loading.** Flowbite's JavaScript is pulled from a
**CDN** in `base.html` even though Flowbite is an installed npm dependency compiled into
`output.css`. The Tagify library is loaded via CDN **and** duplicated (loaded twice in
`publication_form.html`, plus a separate local `js/tagify.js`), with inconsistent placement.

**J. Dead / commented-out code** contrary to the project's code-quality principle: a large
`{% comment %}` avatar block in `edit_profile.html`, a commented resume-save block and an unused
`from email.mime import application` import in `accounts/forms.py`.

**K. Structural markup defect.** The authenticated user dropdown in `base.html` has malformed
`<li>` / `<div>` nesting (an unclosed list item), which can cause inconsistent menu rendering.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every page renders with one consistent, correct visual style (Priority: P1)

A visitor browses the site — home, publications, scholars directory, events, seminars, profiles —
and every list, card, button, form, and pagination control looks like it belongs to the same
product and is correctly styled. No page shows unstyled, plain-HTML, or visibly misaligned
components caused by leftover Bootstrap markup.

**Why this priority**: This is the user-visible payoff and it fixes actual current breakage
(Bootstrap-classed lists and pagination render without styling because no Bootstrap CSS is
loaded). Delivering only this story already produces a coherent, correct-looking site.

**Independent Test**: Visit each primary page (home, publications list + detail, scholars
directory, events list + detail, seminars list, profile, and each form page) and confirm every
list card, button, form field, empty state, and pagination control renders in the Tailwind/Flowbite
style with correct spacing and alignment, with no plain/unstyled elements.

**Acceptance Scenarios**:

1. **Given** the home page with scholars, papers, events, and seminars data, **When** it is
   viewed, **Then** all four lists render as styled Flowbite components with consistent card
   layout, spacing, and empty-state messaging.
2. **Given** the seminars list and the scholars directory (both paginated), **When** they are
   viewed across more than one page of results, **Then** the pagination control renders as a
   single consistent styled component on both pages.
3. **Given** any page previously containing Bootstrap classes, **When** it is inspected, **Then**
   no element relies on a class from a stylesheet the project does not load.

### User Story 2 - Shared UI elements come from a single reusable source (Priority: P2)

A developer needs to change a shared UI element — e.g., the primary button style, the list-card
layout, the form-field wrapper, or the pagination control. They make the change in **one** place
and it applies everywhere that element appears, without hunting through many templates or editing
copy-pasted class strings.

**Why this priority**: This is the maintainability payoff that prevents the inconsistency from
returning. It depends on the visual convergence from Story 1 but is separately valuable and
testable.

**Independent Test**: For each shared element type (list/card item, form field, primary button,
secondary button, pagination, search bar, page shell), confirm there is exactly one canonical
definition, and that changing it once visibly updates every usage.

**Acceptance Scenarios**:

1. **Given** the primary-button definition, **When** its style is changed once, **Then** every
   form's submit button reflects the change with no other edits.
2. **Given** a single list-item / card component, **When** it is used to render scholars, papers,
   events, and seminars, **Then** those lists share one implementation rather than five.
3. **Given** every form in the app, **When** its fields are rendered, **Then** they all flow
   through the one shared field-rendering mechanism (no hand-rolled duplicated field markup
   remains).
4. **Given** repeated utility-class strings or inline `style="…"` attributes, **When** the
   templates are searched, **Then** each shared style exists once in the agreed abstraction rather
   than being copy-pasted. **Resolved (blended approach)**: structural components (cards, list
   items, pagination, buttons) are consolidated into reusable **template partials/tags**, while a
   small set of atomic control styles (text input, select, textarea, file input) are defined once
   as **Tailwind `@apply` component classes in the Tailwind source** and compiled into the single
   `output.css`. Hand-authored ad-hoc rules in `base.css` are not the mechanism.

### User Story 3 - The legacy stack is fully removed and the project matches its intended stack (Priority: P3)

A maintainer reviews the project's dependencies and configuration and finds no trace of the
abandoned Bootstrap/crispy/HTMX stack — no unused packages, no dead form-helper code, no
orphaned settings, no dead template loads or commented-out blocks.

**Why this priority**: Reduces dependency surface, security/upgrade burden, and confusion, and
makes the codebase honestly reflect the Tailwind/Flowbite stack. It is lower priority than the
visible fixes but completes the "full transition" the user asked for.

**Independent Test**: Confirm the abandoned packages are gone from dependencies and configuration,
the app still starts, all forms still submit and validate identically, and the template lint gate
still passes.

**Acceptance Scenarios**:

1. **Given** the dependency and settings files, **When** they are inspected, **Then** the
   Bootstrap-based crispy-forms packages, the crispy template-pack settings, and the unused HTMX
   package are all removed.
2. **Given** the form modules, **When** they are inspected, **Then** no dead `FormHelper` /
   `Layout` crispy scaffolding, commented-out blocks, or unused imports remain, and each form still
   exposes the same fields and validation behavior as before.
3. **Given** the full application after cleanup, **When** every form is submitted (valid and
   invalid input), **Then** it behaves identically to before the cleanup (same fields, same
   validation messages, same success/error outcomes).

### Edge Cases

- **Empty states**: every list (scholars, papers, events, seminars, profile papers) must show a
  consistent, styled "nothing to display" message rather than a blank area or an unstyled one.
- **Validation & error display**: field errors and non-field/form-level errors must render in one
  consistent style across all forms.
- **Special field types**: date pickers, file uploads, multi-select, checkboxes, and the
  tag-input (Tagify) fields must keep working and render consistently through the shared field
  mechanism.
- **No-JavaScript**: core flows (navigation, forms, search) must remain usable when JavaScript is
  unavailable, since Flowbite/Tagify/datepicker behaviors are progressive enhancements.
- **Accessibility**: labels remain associated with inputs, menus and dropdowns stay keyboard
  operable, and color contrast remains sufficient after restyling.
- **Visual scope boundary**: some pages are currently *broken* (unstyled Bootstrap markup), so
  "preserve exact appearance" cannot apply uniformly. **Resolved (minimal-churn)**: this is a
  strict, low-churn refactor. Pages that are **already correctly styled** with Flowbite MUST be
  preserved as-is (no restyling); only the **broken Bootstrap pages** are brought up to the
  existing Flowbite design system. Broader redesign of already-correct pages is **out of scope**.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The interface MUST use a single visual/component system (Tailwind + Flowbite) across
  every template; leftover Bootstrap component and utility classes MUST be replaced with the
  Tailwind/Flowbite equivalent so that no element depends on a stylesheet the project does not load.
- **FR-002**: List and card rendering MUST be consolidated so that equivalent listings (scholars,
  papers, events, seminars, profile papers, home-page lists) are produced by a single shared,
  reusable component rather than multiple divergent partials and inline copies.
- **FR-003**: Pagination controls MUST be provided by one shared, styled component reused by every
  paginated list, replacing the per-page hand-rolled Bootstrap pagination markup.
- **FR-004**: All forms MUST render their fields through one shared field-rendering mechanism
  (the existing `render_field` / `render_select` Flowbite tags or an agreed equivalent); hand-rolled
  duplicated field markup (login, publication form, the advisor select) MUST be migrated to it.
- **FR-005**: The shared field-rendering partials MUST themselves avoid per-widget duplication of
  identical control styling, so a change to input/select/textarea/file/date styling is made once.
- **FR-006**: Repeated utility-class strings and shared inline `style="…"` rules (primary button,
  secondary/cancel button, card surface, text input, navbar link, and the scattered inline styles
  listed in Findings F–G) MUST be abstracted to a single canonical definition per element and
  reused, using the blended approach: **reusable template partials/tags** for structural components
  (buttons, cards, list items, pagination) and **Tailwind `@apply` component classes** (in the
  Tailwind source, compiled into `output.css`) for atomic form-control styling. Shared inline
  `style="…"` rules MUST be eliminated in favor of these definitions.
- **FR-007**: Color and typography usage MUST be standardized on the project's semantic design
  tokens; ad-hoc raw palette values used for the same roles (help text, error text, form controls)
  MUST be replaced with the corresponding tokens.
- **FR-008**: The abandoned Bootstrap-based crispy-forms integration MUST be removed entirely —
  the `crispy_forms` and `crispy_bootstrap5` apps, the `CRISPY_*` settings, the dead `FormHelper` /
  `Layout` scaffolding in the form modules, the stray `{% load crispy_forms_tags %}`, and the
  `django-crispy-forms` / `crispy-bootstrap5` dependencies — without changing any form's fields or
  validation behavior.
- **FR-009**: The unused HTMX integration (`django-htmx` dependency) MUST be removed, since it is
  not installed, configured, or referenced anywhere.
- **FR-010**: Dead and commented-out code revealed by the cleanup (e.g., the commented avatar block,
  commented save logic, unused imports) MUST be removed.
- **FR-011**: Third-party front-end assets MUST be loaded consistently: Flowbite's JavaScript MUST
  be sourced consistently with the rest of the build (aligned with the compiled Flowbite bundle
  rather than an unrelated CDN version), and the Tagify library MUST be loaded exactly once per
  page that needs it, without duplication.
- **FR-012**: The structural markup defect in the navigation dropdown (malformed list nesting) MUST
  be corrected.
- **FR-013**: After cleanup, all templates MUST pass the project's template lint gate (`djlint`),
  and the application MUST start and serve all pages without missing-class, missing-asset, or
  missing-dependency errors.
- **FR-014**: Form fields, field names, labels, help text, validation rules, and success/error
  behavior MUST remain functionally unchanged; this feature MUST NOT alter data models, business
  logic, or view behavior beyond presentation and the removal of dead code.
- **FR-015**: Because the current project constitution mandates the very stack being removed
  (it requires `django-crispy-forms` with the Bootstrap 5 pack and treats HTMX as the progressive
  enhancement mechanism), this effort MUST reconcile that conflict by updating the constitution's
  User Experience Consistency principle to codify the Tailwind/Flowbite component approach as the
  standard.

### Key Entities *(the reusable UI building blocks this feature standardizes)*

- **List / card item**: one styled unit in a listing (title, optional meta/date/badge, optional
  subtitle/description, optional link) — currently expressed five different ways; to become one
  reusable component with documented inputs.
- **Form field wrapper**: the label + control + help-text + error presentation for a single form
  field across all input types — the `render_field` / `render_select` abstraction, to be the sole
  field-rendering path.
- **Button**: primary (submit) and secondary (cancel) actions — one canonical definition each.
- **Pagination control**: the previous/numbered/next navigation for paginated lists — one shared
  component.
- **Search / filter bar**: the search-with-filter-dropdown element (`_search_form.html`) — already
  shared; to remain the single source.
- **Page shell**: the base layout, navigation, and content wrapper (`base.html`) — the single host
  for global chrome and asset loading.
- **Design tokens**: the semantic color/typography vocabulary (`text-heading`, `text-body`,
  `bg-neutral-*`, `border-default*`, `focus:ring-brand`, etc.) that all components must use.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **Zero** templates reference component/utility classes from a styling system the
  project does not load (no Bootstrap-only classes remain).
- **SC-002**: **Zero** pages render a list, card, form control, empty state, or pagination control
  in an unstyled or visibly misaligned state; every such element appears in the unified
  Tailwind/Flowbite style.
- **SC-003**: Each shared UI element type (list/card item, form field, primary button, secondary
  button, pagination, search bar) has **exactly one** canonical definition, and changing that
  definition once updates **100%** of its usages.
- **SC-004**: **100%** of forms render their fields through the single shared field-rendering
  mechanism; **zero** hand-rolled duplicated field markup remains.
- **SC-005**: The count of duplicated shared style strings and shared inline `style="…"` attributes
  identified in Findings F–G is reduced to **one canonical source each** (net large reduction in
  repeated markup).
- **SC-006**: The abandoned dependencies (`django-crispy-forms`, `crispy-bootstrap5`, `django-htmx`)
  and their configuration (crispy apps + `CRISPY_*` settings) are **fully removed**, and the
  application still starts and serves every page successfully.
- **SC-007**: **100%** of forms submit and validate with identical field sets, validation messages,
  and success/error outcomes before and after the cleanup (no behavioral regression).
- **SC-008**: The template lint gate (`djlint`) passes with **zero** errors across all templates,
  and the automated test suite passes.
- **SC-009**: Each third-party front-end asset (Flowbite JS, Tagify) is loaded **at most once** per
  page and sourced consistently with the project's build.

## Assumptions

- **HTMX removal is intended**: the user listed HTMX in the "from" stack and asked for a full
  transition; because HTMX is entirely unused, removing the dependency carries no functional risk.
- **crispy removal is safe**: no template renders `{% crispy %}`, so removing crispy and its
  form-helper scaffolding changes no rendered output; forms already render via `render_field` tags
  or plain field markup.
- **Presentation-only scope**: no changes to models, migrations, URLs, view logic, or form field
  definitions/validation are intended; only templates, shared partials/tags, styling assets,
  settings entries for removed apps, dependency pins, and dead code are touched.
- **Design system is the target**: where legacy Bootstrap markup currently renders unstyled, it
  will be brought up to the existing Flowbite design system (its semantic tokens and component
  patterns), which is treated as a fix rather than a visual regression.
- **Resolved — visual scope (minimal-churn)**: pages already correctly styled with Flowbite are
  preserved as-is; only broken Bootstrap pages are fixed. Redesign of correct pages is out of scope.
- **Resolved — style abstraction (blended)**: structural components use reusable template
  partials/tags; atomic form-control styles use Tailwind `@apply` component classes compiled into
  `output.css`. A hand-authored `base.css` is not the abstraction mechanism.
- **Build pipeline unchanged**: the Tailwind/Flowbite CSS is rebuilt with the existing
  `npm run build` step and the compiled `output.css` remains committed; Node is required only in
  the development/build environment, not on the Media3 host (consistent with prior deployment work).
- **Lint gate**: `djlint` remains the template quality gate per the project constitution.
- **Constitution amendment is a dependency**: the current constitution (v1.0.0) explicitly mandates
  crispy-forms + Bootstrap 5 and HTMX; this effort assumes that principle will be amended as part
  of the work so the cleanup does not violate governance.
- **No SSO/auth change**: this cleanup is unrelated to the deferred CUWebLogin/SSO consideration and
  does not touch authentication.

## Dependencies

- **Governance**: an amendment to `.specify/memory/constitution.md` (User Experience Consistency
  principle) to replace the crispy-forms/Bootstrap-5 + HTMX mandate with the Tailwind/Flowbite
  component standard. Until amended, this feature is in tension with the constitution as written.
- **Existing abstraction**: the `core/templatetags/form_tags.py` `render_field` / `render_select`
  inclusion tags and the `templates/partials/` directory are the foundation the consolidated
  components build on.
- **Build tooling**: the existing Tailwind v4 + Flowbite CLI build (`npm run build`) must be run to
  regenerate `output.css` after any change to shared component classes.

## Out of Scope

- New end-user features or content types.
- Data model, migration, URL, or view-behavior changes (beyond removing dead code).
- Backend performance work, caching, or query optimization.
- Deployment/hosting changes (covered by the separate Media3 deployment work).
- Authentication / CUWebLogin SSO.
