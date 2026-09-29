/**
 * Lets a Tagify instance's tags be reordered by dragging, with an animated
 * slide as tags swap places. Tagify itself has no built-in drag-sort; this
 * uses its author's companion library, vendored at static/js/dragsort.js
 * (see static/js/README.md) -- the documented pairing
 * (https://github.com/yairEO/tagify#drag--sort), and a straight upgrade over
 * an earlier hand-rolled native-HTML5-drag version, which had no way to
 * animate a sibling sliding over (DOM reordering on `dragover` is instant)
 * short of a hand-built FLIP-animation layer.
 */
function makeTagifySortable(tagify) {
  new DragSort(tagify.DOM.scope, {
    selector: '.' + tagify.settings.classNames.tag,
    callbacks: {
      // Tagify's own value array doesn't track drag reorders on its own;
      // this rebuilds it (and so the hidden input's JSON) from the new DOM
      // order, which is what publications.utils.set_ordered_authors persists.
      dragEnd: function () {
        tagify.updateValueByDOMTags();
      },
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
