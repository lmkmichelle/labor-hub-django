# Vendored third-party JS

Per CLAUDE.md, no runtime CDN loads — third-party scripts are vendored here and served via
`{% static %}`.

- `flowbite.min.js` — Flowbite (see `package.json` for the pinned version).
- `cropper.min.js` — [Cropper.js](https://fengyuanchen.github.io/cropperjs) v1.6.2, MIT licensed.
  Used by `avatar-editor.js` for the Edit Profile picture crop/rotate/zoom control. Its stylesheet
  is vendored alongside at `static/css/cropper.min.css`.
- `sortable.min.js` — [Sortable.js](https://github.com/SortableJS/Sortable) v1.15.7, MIT licensed.
  Used by `tagify.js` (`makeTagifySortable`) for the paper-submission Authors field's
  drag-to-reorder pills, with `forceFallback: true` so dragging is tracked with pointer events
  instead of native HTML5 drag-and-drop -- native DnD's `dragover` firing is unreliable on macOS,
  which is what an earlier attempt with `@yaireo/dragsort` (Tagify's own documented drag-sort
  pairing) ran into: https://github.com/yaireo/dragsort/issues/5.
