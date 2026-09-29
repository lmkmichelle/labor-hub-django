# Vendored third-party JS

Per CLAUDE.md, no runtime CDN loads — third-party scripts are vendored here and served via
`{% static %}`.

- `flowbite.min.js` — Flowbite (see `package.json` for the pinned version).
- `cropper.min.js` — [Cropper.js](https://fengyuanchen.github.io/cropperjs) v1.6.2, MIT licensed.
  Used by `avatar-editor.js` for the Edit Profile picture crop/rotate/zoom control. Its stylesheet
  is vendored alongside at `static/css/cropper.min.css`.
- `dragsort.js` — [DragSort](https://github.com/yaireo/dragsort) v1.3.2, MIT licensed, by Tagify's
  own author, purpose-built to pair with it for animated tag reordering (Tagify itself has no
  built-in drag-sort). Used by `tagify.js` for the paper-submission Authors field's drag-to-reorder
  pills, replacing an earlier hand-rolled native-HTML5-drag version that reordered instantly with
  no animation. Its stylesheet is vendored alongside at `static/css/dragsort.css`.
