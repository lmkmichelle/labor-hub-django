/**
 * Country-driven city suggestion combobox.
 *
 * Fills a themed suggestion panel (matching base.html's nav account-menu
 * dropdown, the site's one already-correct Flowbite-styled pattern) with the
 * cities of the country chosen in a sibling country <select>, fetched from
 * the cities endpoint. Unlike university-picker.js (which narrows a <select>
 * to an exact match), the city field stays a free-text <input>, so a venue in
 * a town too small to be in the dataset is still a valid, typeable entry --
 * the suggestion panel is an assist, not a constraint.
 *
 * Wiring is by data attributes on a wrapper element, so no template needs to
 * inline any JavaScript:
 *
 *   <div data-city-picker
 *        data-endpoint="{% url 'cities-by-country' %}"
 *        data-country-field="{{ form.country_code.id_for_label }}"
 *        data-city-field="{{ form.city.id_for_label }}">
 *     <input ...>
 *     <div class="city-suggestions hidden ..."><ul></ul></div>
 *   </div>
 *
 * On a fetch failure the plain text input keeps working with no suggestions,
 * the same graceful-degradation posture as the university picker.
 */
(function () {
  var MAX_SUGGESTIONS = 50;

  function initPicker(root) {
    var endpoint = root.dataset.endpoint;
    var countrySelect = document.getElementById(root.dataset.countryField);
    var cityInput = document.getElementById(root.dataset.cityField);
    var panel = root.querySelector(".city-suggestions");
    var list = panel ? panel.querySelector("ul") : null;
    if (!endpoint || !countrySelect || !cityInput || !panel || !list) {
      return;
    }

    // A plain text input gives no visual hint that it opens a suggestion
    // list; add the same chevron a <select> shows, so the field reads as a
    // dropdown rather than looking like free text with nothing behind it.
    cityInput.classList.add("form-input-chevron");

    var cities = [];

    function hide() {
      panel.classList.add("hidden");
    }

    function show() {
      if (list.children.length) {
        panel.classList.remove("hidden");
      }
    }

    function renderMatches(matches) {
      list.innerHTML = "";
      matches.slice(0, MAX_SUGGESTIONS).forEach(function (name) {
        var item = document.createElement("li");
        var button = document.createElement("button");
        button.type = "button";
        button.className = "dropdown-panel-item";
        button.textContent = name;
        button.addEventListener("mousedown", function (event) {
          // mousedown (not click) so this fires before the input's blur hides the panel.
          event.preventDefault();
          cityInput.value = name;
          hide();
        });
        item.appendChild(button);
        list.appendChild(item);
      });
    }

    function filterAndShow() {
      var query = cityInput.value.trim().toLowerCase();
      var matches = query
        ? cities.filter(function (name) {
            return name.toLowerCase().indexOf(query) !== -1;
          })
        : cities;
      renderMatches(matches);
      show();
    }

    function load() {
      var country = (countrySelect.value || "").toUpperCase();
      cities = [];
      hide();
      if (!country) {
        return;
      }

      fetch(endpoint + "?country=" + encodeURIComponent(country), {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      })
        .then(function (response) {
          return response.ok ? response.json() : { cities: [] };
        })
        .then(function (payload) {
          cities = (payload && payload.cities) || [];
          // The user may have already focused/typed in the city field while
          // this fetch was in flight -- show the now-loaded matches instead
          // of leaving the panel closed until the next keystroke.
          if (document.activeElement === cityInput) {
            filterAndShow();
          }
        })
        .catch(function () {
          // Leave the free-text fallback field as the way through.
          cities = [];
        });
    }

    countrySelect.addEventListener("change", load);
    cityInput.addEventListener("focus", filterAndShow);
    cityInput.addEventListener("input", filterAndShow);
    cityInput.addEventListener("blur", hide);
    cityInput.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        hide();
      }
    });
    load();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-city-picker]").forEach(initPicker);
  });
})();
