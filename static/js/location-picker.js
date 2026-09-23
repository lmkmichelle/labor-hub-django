/**
 * City-first location picker: type a city, get a themed suggestion panel of
 * real (city, state/province, country) matches, select one to auto-fill
 * Country and State/Province (plus hidden lat/lon for a future "sort by
 * distance" feature). The city field stays plain free text -- a venue in a
 * town too small for the dataset is still a valid, typeable entry; only
 * Country then needs to be set by hand.
 *
 * Backed by core.views.city_search (GET /api/cities/search/?q=...), which
 * queries the self-hosted GeoNames import (core.models.City) -- no
 * third-party geocoding API, no key, no per-request cost.
 *
 * Wiring is by data attributes on a wrapper element, so no template needs to
 * inline any JavaScript:
 *
 *   <div data-location-picker
 *        data-endpoint="{% url 'city-search' %}"
 *        data-city-field="{{ form.city.id_for_label }}"
 *        data-country-field="{{ form.country_code.id_for_label }}"
 *        data-admin1-field="{{ form.admin1_name.id_for_label }}"
 *        data-admin1-code-field="{{ form.admin1_code.id_for_label }}"
 *        data-lat-field="{{ form.latitude.id_for_label }}"
 *        data-lon-field="{{ form.longitude.id_for_label }}"
 *        data-admin1-labels-id="admin1-labels-data"
 *        data-default-admin1-label="Region">
 *     {{ admin1_labels|json_script:"admin1-labels-data" }}
 *     <input ...> (the city field)
 *     <div class="location-suggestions hidden ..."><ul></ul></div>
 *   </div>
 *
 * A sibling `[data-admin1-field-wrapper]` (holding the State/Province field)
 * is shown only once a selection has a non-empty admin1_name, and hidden
 * again on a fresh free-text city -- most countries have one, some don't,
 * and there is no reason to show an always-empty field for those that don't.
 *
 * On a fetch failure the plain text input keeps working with no suggestions,
 * the same graceful-degradation posture used throughout the site's other
 * pickers (city-picker.js's predecessor, university-picker.js).
 */
(function () {
  var MIN_QUERY_LENGTH = 2;
  var DEBOUNCE_MS = 200;

  function initPicker(root) {
    var endpoint = root.dataset.endpoint;
    var cityInput = document.getElementById(root.dataset.cityField);
    var countrySelect = document.getElementById(root.dataset.countryField);
    var admin1Input = document.getElementById(root.dataset.admin1Field);
    var admin1CodeInput = document.getElementById(root.dataset.admin1CodeField);
    var latInput = document.getElementById(root.dataset.latField);
    var lonInput = document.getElementById(root.dataset.lonField);
    var panel = root.querySelector(".location-suggestions");
    var list = panel ? panel.querySelector("ul") : null;
    if (!endpoint || !cityInput || !countrySelect || !panel || !list) {
      return;
    }

    var admin1Wrapper = document.querySelector("[data-admin1-field-wrapper]");
    var admin1Labels = {};
    var labelsScript = root.dataset.admin1LabelsId
      ? document.getElementById(root.dataset.admin1LabelsId)
      : null;
    if (labelsScript) {
      try {
        admin1Labels = JSON.parse(labelsScript.textContent) || {};
      } catch (e) {
        admin1Labels = {};
      }
    }
    var defaultAdmin1Label = root.dataset.defaultAdmin1Label || "Region";

    // A plain text input gives no visual hint that it opens a suggestion
    // list; add the same chevron a <select> shows, so the field reads as a
    // dropdown rather than looking like free text with nothing behind it.
    cityInput.classList.add("form-input-chevron");

    function updateAdmin1Visibility() {
      if (!admin1Wrapper) {
        return;
      }
      admin1Wrapper.classList.toggle("hidden", !admin1Input || !admin1Input.value);
    }

    function relabelAdmin1(countryCode) {
      if (!admin1Input) {
        return;
      }
      var label = admin1Labels[countryCode] || defaultAdmin1Label;
      var fieldLabel = admin1Wrapper
        ? admin1Wrapper.querySelector("label")
        : null;
      if (fieldLabel) {
        // Preserve the required-marker span (if any) while swapping the text.
        var marker = fieldLabel.querySelector("span");
        fieldLabel.textContent = label;
        if (marker) {
          fieldLabel.appendChild(marker);
        }
      }
    }

    function setField(input, value) {
      if (!input) {
        return;
      }
      input.value = value == null ? "" : value;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function hide() {
      panel.classList.add("hidden");
    }

    function show() {
      if (list.children.length) {
        panel.classList.remove("hidden");
      }
    }

    function choose(city) {
      cityInput.value = city.name;
      setField(countrySelect, city.country_code);
      setField(admin1Input, city.admin1_name || "");
      setField(admin1CodeInput, city.admin1_code || "");
      setField(latInput, city.latitude);
      setField(lonInput, city.longitude);
      relabelAdmin1(city.country_code);
      updateAdmin1Visibility();
      hide();
    }

    function renderMatches(cities) {
      list.innerHTML = "";
      cities.forEach(function (city) {
        var li = document.createElement("li");
        var button = document.createElement("button");
        button.type = "button";
        button.className = "dropdown-panel-item";
        button.textContent = city.label;
        button.addEventListener("mousedown", function (event) {
          // mousedown (not click) so this fires before the input's blur hides the panel.
          event.preventDefault();
          choose(city);
        });
        li.appendChild(button);
        list.appendChild(li);
      });
    }

    var debounceTimer = null;
    var inFlightController = null;

    function search() {
      var query = cityInput.value.trim();
      if (query.length < MIN_QUERY_LENGTH) {
        hide();
        return;
      }

      if (inFlightController) {
        inFlightController.abort();
      }
      inFlightController = window.AbortController ? new AbortController() : null;

      fetch(
        endpoint + "?q=" + encodeURIComponent(query),
        {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          signal: inFlightController ? inFlightController.signal : undefined,
        }
      )
        .then(function (response) {
          return response.ok ? response.json() : { cities: [] };
        })
        .then(function (payload) {
          renderMatches((payload && payload.cities) || []);
          show();
        })
        .catch(function (err) {
          // AbortError just means a newer keystroke superseded this request;
          // any other failure leaves the free-text fallback field working.
          if (err && err.name !== "AbortError") {
            list.innerHTML = "";
          }
        });
    }

    function scheduleSearch() {
      if (debounceTimer) {
        clearTimeout(debounceTimer);
      }
      debounceTimer = setTimeout(search, DEBOUNCE_MS);
    }

    cityInput.addEventListener("input", scheduleSearch);
    cityInput.addEventListener("focus", function () {
      if (list.children.length) {
        show();
      }
    });
    cityInput.addEventListener("blur", hide);
    cityInput.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        hide();
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        var items = Array.prototype.slice.call(list.querySelectorAll("button"));
        if (!items.length) {
          return;
        }
        event.preventDefault();
        var current = items.indexOf(document.activeElement);
        var next = event.key === "ArrowDown"
          ? Math.min(current + 1, items.length - 1)
          : Math.max(current - 1, 0);
        items[Math.max(next, 0)].focus();
      } else if (event.key === "Enter") {
        // Free text is a valid submission on its own; don't hijack Enter
        // unless the panel is actually open with matches to pick from.
        if (!panel.classList.contains("hidden")) {
          event.preventDefault();
        }
      }
    });

    updateAdmin1Visibility();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-location-picker]").forEach(initPicker);
  });
})();
