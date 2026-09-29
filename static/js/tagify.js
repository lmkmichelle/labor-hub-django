/**
 * Lets a Tagify instance's tags be reordered by dragging, using plain HTML5
 * drag-and-drop (no Tagify DragSort plugin/extra dependency -- see the
 * paper-fixes plan). After each drop, Tagify's own updateValueByDOMTags()
 * re-derives tagify.value (and so the hidden input's JSON) from the DOM
 * order, which is what publications.utils.set_ordered_authors then persists.
 */
function makeTagifyDraggable(tagify) {
  let draggedTag = null;

  function applyDraggable() {
    tagify.DOM.scope.querySelectorAll(".tagify__tag").forEach(function (tag) {
      tag.setAttribute("draggable", "true");
    });
  }

  tagify.DOM.scope.addEventListener("dragstart", function (e) {
    const tag = e.target.closest(".tagify__tag");
    if (!tag) {
      return;
    }
    draggedTag = tag;
    e.dataTransfer.effectAllowed = "move";
  });

  tagify.DOM.scope.addEventListener("dragover", function (e) {
    const target = e.target.closest(".tagify__tag");
    if (!draggedTag || !target || target === draggedTag) {
      return;
    }
    e.preventDefault();
    const rect = target.getBoundingClientRect();
    const before = e.clientX < rect.left + rect.width / 2;
    target.parentNode.insertBefore(draggedTag, before ? target : target.nextSibling);
  });

  tagify.DOM.scope.addEventListener("drop", function (e) {
    e.preventDefault();
  });

  tagify.DOM.scope.addEventListener("dragend", function () {
    if (draggedTag) {
      tagify.updateValueByDOMTags();
      draggedTag = null;
    }
  });

  applyDraggable();
  tagify.on("add", applyDraggable);
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

    makeTagifyDraggable(authors_tag);
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
