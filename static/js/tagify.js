/**
 * Lets a Tagify instance's tags be reordered by dragging, with an animated
 * slide as tags swap places. Tagify itself has no built-in drag-sort.
 *
 * Tagify's own documented pairing is its author's small companion library,
 * DragSort (https://github.com/yairEO/tagify#drag--sort) -- tried first, but
 * dropped after it turned out to hit a known, unresolved upstream bug
 * (https://github.com/yairEO/dragsort/issues/5, "Glitchy sorting animation
 * on macOS"): native HTML5 drag-and-drop's `dragover` firing is notoriously
 * unreliable on macOS, especially over gaps between elements, which is also
 * why it took dragging far outside the field to register at all.
 *
 * Sortable.js (vendored at static/js/sortable.min.js -- see
 * static/js/README.md) sidesteps that whole class of bug via its
 * `forceFallback` option, which makes it track the drag with pointer events
 * instead of relying on native HTML5 DnD -- the documented fix for exactly
 * this "feel more consistent between Desktop, Mobile and old Browsers" case.
 */
function makeTagifySortable(tagify) {
  // Marks the field so input.css can target its tags with user-select: none
  // (see the .tagify--sortable rule there) without affecting every other
  // Tagify field on the site.
  tagify.DOM.scope.classList.add('tagify--sortable');

  Sortable.create(tagify.DOM.scope, {
    // Only tag pills are draggable -- not Tagify's own growing text input,
    // which is also a direct child of the same scope element.
    draggable: '.' + tagify.settings.classNames.tag,
    forceFallback: true,
    animation: 150,
    // Tagify's own value array doesn't track drag reorders on its own;
    // this rebuilds it (and so the hidden input's JSON) from the new DOM
    // order, which is what publications.utils.set_ordered_authors persists.
    onEnd: function () {
      tagify.updateValueByDOMTags();
    },
  });
}

document.addEventListener("DOMContentLoaded", async function () {
  const authors_input = document.querySelector("#authors-input");
  const editors_input = document.querySelector("#editors-input");
  const research_interests_input = document.querySelector("#research-interests-input");
  const topics_input = document.querySelector("#topics-input");

  function getRecommendedKeywords() {
    const el = document.getElementById("recommended-keywords-data");
    if (el) {
      try {
        return JSON.parse(el.textContent);
      } catch (e) {
        return [];
      }
    }
    return [];
  }

  const additional_keywords = getRecommendedKeywords();

  if (authors_input) {
    const authors_tag = new Tagify(authors_input, {
      whitelist: [],
      enforceWhitelist: false,
      dropdown: {
        closeOnSelect: false,
        enabled: 0,
        maxItems: 10,
        classname: "dropdown-panel",
      }
    });

    authors_tag.on('input', function (e) {
      const value = e.detail.value;
      fetch(`/api/accounts/search/?q=${encodeURIComponent(value)}`)
        .then(res => res.json())
        .then(data => {
          authors_tag.settings.whitelist = data;
        });
    });

    makeTagifySortable(authors_tag);
  }

  if (editors_input) {
    // Same member search as authors; anyone not found is kept as a plain name.
    const editors_tag = new Tagify(editors_input, {
      whitelist: [],
      enforceWhitelist: false,
      dropdown: {
        closeOnSelect: false,
        enabled: 0,
        maxItems: 10,
        classname: "dropdown-panel",
      }
    });

    editors_tag.on('input', function (e) {
      fetch(`/api/accounts/search/?q=${encodeURIComponent(e.detail.value)}`)
        .then(res => res.json())
        .then(data => {
          editors_tag.settings.whitelist = data;
        });
    });
  }

  if (research_interests_input) {
    new Tagify(research_interests_input, {
      whitelist: additional_keywords,
      // Some recommended keywords contain commas (e.g. "Structural models of
      // health, retirement, and savings") -- the default "," delimiter would
      // split typing/pasting one of those into several tags. Enter and
      // picking a dropdown item still add a tag.
      delimiters: null,
      dropdown: {
        enabled: 0,
        closeOnSelect: false,
        maxItems: additional_keywords.length,
        classname: "dropdown-panel"
      }
    });
  }

  if (topics_input) {
    // Closed list: only the recommended vocabulary, no free entry. The server
    // (PublicationForm.clean_topics_input) re-checks this.
    new Tagify(topics_input, {
      whitelist: additional_keywords,
      enforceWhitelist: true,
      delimiters: null,
      dropdown: {
        enabled: 0,
        closeOnSelect: false,
        maxItems: additional_keywords.length,
        classname: "dropdown-panel"
      },
      originalInputValueFormat: values =>
        JSON.stringify(values.map(v => ({value: v.value}))),
    });
  }
});
