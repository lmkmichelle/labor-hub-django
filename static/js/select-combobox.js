/**
 * Progressive-enhancement combobox for every single-value <select>.
 *
 * A native <select>'s CLOSED box can be themed with CSS (.form-select already
 * does: border, background, radius, a background-image chevron). Its OPENED
 * option-list popup cannot -- it's rendered by the OS/browser outside the
 * page's box tree, in every browser, and no CSS selector reaches it. The only
 * way to get a fully themed dropdown panel is to replace the popup with one
 * of our own, which is what this file does for every `<select class="…
 * form-select …">` on the page (skipping `multiple` selects, which this
 * pattern doesn't support).
 *
 * The real <select> stays in the DOM -- same name, same value, same
 * `required`/`disabled` state, same id (so its <label for="..."> still
 * works) -- just visually collapsed to a 1x1px box (not display:none, so a
 * required field's native validation still has something to anchor to) and
 * taken out of the tab order. A new <button> becomes the real interactive
 * control, showing the selected option's text and driving a themed
 * .dropdown-panel of the same options. Choosing one sets the real select's
 * value and dispatches a real `change` event on it, so every existing
 * listener attached to the select itself -- university-picker.js's
 * `countrySelect.addEventListener('change', ...)`, a sort select's inline
 * `onchange="this.form.submit()"` -- keeps working completely unmodified.
 *
 * university-picker.js also rewrites a university select's <option>s
 * wholesale when its country changes. A MutationObserver on each enhanced
 * select's childList keeps this combobox's panel and trigger label in sync
 * with that, regardless of which script's DOMContentLoaded handler runs
 * first.
 *
 * Known scope boundary: this implements enough keyboard support (arrow keys,
 * Home/End, Enter, Escape) and ARIA (aria-haspopup/expanded, role=listbox/
 * option, aria-selected) to be genuinely usable without a mouse, but it is
 * not a full WAI-ARIA APG combobox implementation.
 */
(function () {
  var SEARCH_THRESHOLD = 8; // more options than this gets a filter box
  var MAX_VISIBLE_OPTIONS = 50;

  function optionsOf(select) {
    return Array.prototype.slice.call(select.options);
  }

  function selectedLabel(select) {
    var opt = select.options[select.selectedIndex];
    return opt ? opt.textContent : "";
  }

  function enhance(select) {
    if (select.multiple || select.dataset.comboboxEnhanced) {
      return;
    }
    select.dataset.comboboxEnhanced = "true";

    var originalClassName = select.className;
    var isFullWidth = originalClassName.split(/\s+/).indexOf("w-full") !== -1;
    // A native <select> without an explicit width sizes itself to fit its
    // widest option (e.g. a sort control). A <button> instead sizes to fit
    // only its own current text, which would visibly jitter width as the
    // selection changes. Lock it to the select's own natural width, measured
    // while it's still a normal in-flow element -- full-width fields don't
    // need this since w-full already stretches the trigger to match.
    var naturalWidth = isFullWidth ? null : select.getBoundingClientRect().width;

    var wrapper = document.createElement("div");
    wrapper.className = "relative";
    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);

    var trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = originalClassName + " text-left";
    if (naturalWidth) {
      trigger.style.minWidth = naturalWidth + "px";
    }
    trigger.disabled = select.disabled;
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    wrapper.insertBefore(trigger, select);

    // Visually hidden but still rendered (not display:none) -- a form
    // control that's never rendered can silently lose its native "please
    // select an item" validation bubble in some browsers. tabIndex -1 takes
    // it out of the tab order; the trigger button above is the real control
    // a keyboard/mouse user interacts with. Its <label for> still works:
    // clicking a label calls .focus() on its target directly, which isn't
    // blocked by tabindex="-1".
    select.className =
      "absolute h-px w-px overflow-hidden opacity-0 pointer-events-none";
    select.tabIndex = -1;

    var panel = document.createElement("div");
    panel.className =
      "dropdown-panel not-format hidden absolute top-full z-10 mt-1 max-h-72 w-full overflow-auto";
    wrapper.appendChild(panel);

    // Always created, but only shown once the select actually has enough
    // options to need filtering (checked in updateSearchVisibility, not just
    // once here) -- university-picker.js starts a university select with
    // just a placeholder option and grows it to thousands once a country is
    // chosen, well after this runs, so the decision can't be made only once.
    var searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.className = "form-input mb-1 hidden";
    searchInput.setAttribute("aria-label", "Filter options");
    searchInput.addEventListener("input", function () {
      renderOptions(searchInput.value);
    });
    searchInput.addEventListener("keydown", handleKeydown);
    panel.appendChild(searchInput);

    function updateSearchVisibility() {
      searchInput.classList.toggle("hidden", select.options.length <= SEARCH_THRESHOLD);
    }

    var list = document.createElement("ul");
    list.setAttribute("role", "listbox");
    list.className = "py-1 text-sm text-heading";
    panel.appendChild(list);

    var activeIndex = -1;

    function rows() {
      return Array.prototype.slice.call(list.querySelectorAll("button"));
    }

    function setActive(index) {
      var items = rows();
      items.forEach(function (b) {
        b.classList.remove("bg-neutral-secondary-medium");
      });
      if (items[index]) {
        items[index].classList.add("bg-neutral-secondary-medium");
        items[index].scrollIntoView({ block: "nearest" });
      }
      activeIndex = index;
    }

    function choose(opt) {
      select.value = opt.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      updateTrigger();
      closePanel();
      trigger.focus();
    }

    function renderOptions(filterText) {
      var query = (filterText || "").trim().toLowerCase();
      var opts = optionsOf(select);
      var matches = query
        ? opts.filter(function (o) {
            return o.textContent.toLowerCase().indexOf(query) !== -1;
          })
        : opts;

      list.innerHTML = "";
      var selectedRow = -1;
      matches.slice(0, MAX_VISIBLE_OPTIONS).forEach(function (opt, i) {
        var li = document.createElement("li");
        var button = document.createElement("button");
        button.type = "button";
        button.className = "dropdown-panel-item";
        button.textContent = opt.textContent;
        button.setAttribute("role", "option");
        if (opt.value === select.value) {
          button.setAttribute("aria-selected", "true");
          selectedRow = i;
        }
        button.addEventListener("mousedown", function (event) {
          // mousedown (not click) so this fires before the input's blur hides the panel.
          event.preventDefault();
          choose(opt);
        });
        li.appendChild(button);
        list.appendChild(li);
      });
      setActive(selectedRow);
    }

    function updateTrigger() {
      trigger.textContent = selectedLabel(select) || " ";
    }

    function openPanel() {
      updateSearchVisibility();
      searchInput.value = "";
      renderOptions("");
      panel.classList.remove("hidden");
      trigger.setAttribute("aria-expanded", "true");
      if (!searchInput.classList.contains("hidden")) {
        searchInput.focus();
      }
    }

    function closePanel() {
      panel.classList.add("hidden");
      trigger.setAttribute("aria-expanded", "false");
    }

    function togglePanel() {
      if (panel.classList.contains("hidden")) {
        openPanel();
      } else {
        closePanel();
      }
    }

    function handleKeydown(event) {
      var items = rows();
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (panel.classList.contains("hidden")) {
          openPanel();
        } else {
          setActive(Math.min(activeIndex + 1, items.length - 1));
        }
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setActive(Math.max(activeIndex - 1, 0));
      } else if (event.key === "Home") {
        event.preventDefault();
        setActive(0);
      } else if (event.key === "End") {
        event.preventDefault();
        setActive(items.length - 1);
      } else if (event.key === "Enter" || event.key === " ") {
        if (panel.classList.contains("hidden")) {
          if (event.key === "Enter") return; // let Enter submit an enclosing form as usual
          event.preventDefault();
          openPanel();
        } else if (items[activeIndex]) {
          event.preventDefault();
          items[activeIndex].dispatchEvent(new Event("mousedown", { bubbles: true }));
        }
      } else if (event.key === "Escape") {
        if (!panel.classList.contains("hidden")) {
          event.preventDefault();
          closePanel();
          trigger.focus();
        }
      }
    }

    trigger.addEventListener("click", togglePanel);
    trigger.addEventListener("keydown", handleKeydown);
    // Reaching the real select via Shift+Tab or a label click should behave
    // like reaching the trigger.
    select.addEventListener("focus", function () {
      trigger.focus();
    });

    // choose() (this file) and the MutationObserver below (university-picker.js
    // rebuilding <option>s) already keep the trigger's label in sync with
    // those two ways the select's value can change. A third way exists:
    // something else setting `select.value` directly and dispatching `change`
    // itself -- location-picker.js does exactly this to fill Country after a
    // city is chosen. Neither of the above catches that (no options are
    // added/removed, and choose() isn't what set the value), so the trigger
    // would keep showing the old selection while the real select silently
    // held the new one. Listening for `change` here covers every case.
    select.addEventListener("change", updateTrigger);

    document.addEventListener("mousedown", function (event) {
      if (!panel.classList.contains("hidden") && !wrapper.contains(event.target)) {
        closePanel();
      }
    });

    new MutationObserver(function () {
      updateTrigger();
      updateSearchVisibility();
      if (!panel.classList.contains("hidden")) {
        renderOptions(searchInput.value);
      }
    }).observe(select, { childList: true });

    updateSearchVisibility();
    updateTrigger();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("select.form-select").forEach(enhance);
  });
})();
