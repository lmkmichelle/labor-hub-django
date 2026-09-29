/**
 * Adds "move up" / "move down" buttons to each of a Tagify instance's tags,
 * so the author order can be reordered deterministically -- see
 * publications/utils.py::set_ordered_authors and Publication.ordered_authors
 * for how that order is persisted and displayed.
 *
 * This replaces two rounds of drag-based reordering (DragSort, then
 * Sortable.js), both abandoned:
 *  - DragSort (Tagify's own documented drag-sort pairing) hit an unresolved
 *    upstream bug, "Glitchy sorting animation on macOS"
 *    (https://github.com/yaireo/dragsort/issues/5): native HTML5 drag's
 *    dragover firing is unreliable on macOS.
 *  - Sortable.js's forceFallback mode fixed that, but its FLIP-style
 *    animation fought the transition Tagify's own (unlayered, always-wins --
 *    see the .tagify.form-input comment in input.css) CSS sets on
 *    `.tagify__tag`, a documented class of conflict
 *    (https://github.com/SortableJS/Sortable/issues/1751): the reorder
 *    snapped instead of animating.
 *
 * Buttons sidestep the whole cross-library CSS fight (no drag library, no
 * animation to fight over) and are the standard accessible pattern for this
 * anyway -- WCAG 2.2 SC 2.5.7 (Dragging Movements) requires any drag
 * interaction to have a single-pointer, non-drag alternative like this one.
 */
function addAuthorReorderButtons(tagify) {
  function moveTag(tagElm, direction) {
    const sibling = direction === 'up'
      ? tagElm.previousElementSibling
      : tagElm.nextElementSibling;
    if (!sibling || !sibling.classList.contains(tagify.settings.classNames.tag)) {
      return;
    }
    if (direction === 'up') {
      tagElm.parentNode.insertBefore(tagElm, sibling);
    } else {
      tagElm.parentNode.insertBefore(sibling, tagElm);
    }
    tagify.updateValueByDOMTags();
    refreshButtonStates();
  }

  function refreshButtonStates() {
    const tags = tagify.DOM.scope.querySelectorAll('.' + tagify.settings.classNames.tag);
    tags.forEach(function (tagElm, index) {
      const upBtn = tagElm.querySelector('[data-reorder="up"]');
      const downBtn = tagElm.querySelector('[data-reorder="down"]');
      if (upBtn) {
        upBtn.disabled = index === 0;
      }
      if (downBtn) {
        downBtn.disabled = index === tags.length - 1;
      }
    });
  }

  function attachButtons() {
    tagify.DOM.scope
      .querySelectorAll('.' + tagify.settings.classNames.tag)
      .forEach(function (tagElm) {
        if (tagElm.querySelector('.tag-reorder-buttons')) {
          return; // already has buttons
        }
        const group = document.createElement('span');
        group.className = 'tag-reorder-buttons';

        ['up', 'down'].forEach(function (direction) {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'tag-reorder-btn';
          btn.dataset.reorder = direction;
          btn.setAttribute('aria-label',
            (direction === 'up' ? 'Move ' : 'Move ') +
            (tagElm.textContent || 'author').trim() +
            (direction === 'up' ? ' earlier' : ' later'));
          btn.textContent = direction === 'up' ? '↑' : '↓';
          // Both to stop Tagify's own click handling on the tag (which can
          // open its edit-in-place mode) and to keep the click from being
          // treated as a tag removal/selection.
          btn.addEventListener('mousedown', function (e) { e.stopPropagation(); });
          btn.addEventListener('click', function (e) {
            e.stopPropagation();
            e.preventDefault();
            moveTag(tagElm, direction);
          });
          group.appendChild(btn);
        });

        tagElm.appendChild(group);
      });
    refreshButtonStates();
  }

  attachButtons();
  tagify.on('add', attachButtons);
  tagify.on('remove', refreshButtonStates);
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

    addAuthorReorderButtons(authors_tag);
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
