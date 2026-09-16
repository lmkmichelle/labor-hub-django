/**
 * Country-driven city suggestion picker.
 *
 * Fills a <datalist> with the cities of the country chosen in a sibling
 * country <select>, fetched from the cities endpoint. Unlike
 * university-picker.js (which narrows a <select> to an exact match), this
 * fills a <datalist> paired with a free-text <input list="...">, so a venue
 * in a town too small to be in the dataset is still a valid, typeable entry.
 *
 * Wiring is by data attributes on a wrapper element, so no template needs to
 * inline any JavaScript:
 *
 *   <div data-city-picker
 *        data-endpoint="{% url 'cities-by-country' %}"
 *        data-country-field="{{ form.country_code.id_for_label }}"
 *        data-city-field="{{ form.city.id_for_label }}">
 *
 * On a fetch failure the plain text input keeps working with no suggestions,
 * the same graceful-degradation posture as the university picker.
 */
(function () {
  function initPicker(root) {
    var endpoint = root.dataset.endpoint;
    var countrySelect = document.getElementById(root.dataset.countryField);
    var cityInput = document.getElementById(root.dataset.cityField);
    if (!endpoint || !countrySelect || !cityInput) {
      return;
    }

    var datalist = document.getElementById(cityInput.getAttribute("list"));
    if (!datalist) {
      return;
    }

    function fill(cities) {
      datalist.innerHTML = "";
      cities.forEach(function (name) {
        var option = document.createElement("option");
        option.value = name;
        datalist.appendChild(option);
      });
    }

    function load() {
      var country = (countrySelect.value || "").toUpperCase();
      if (!country) {
        fill([]);
        return;
      }

      fetch(endpoint + "?country=" + encodeURIComponent(country), {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      })
        .then(function (response) {
          return response.ok ? response.json() : { cities: [] };
        })
        .then(function (payload) {
          fill((payload && payload.cities) || []);
        })
        .catch(function () {
          // Leave the free-text fallback field as the way through.
          fill([]);
        });
    }

    countrySelect.addEventListener("change", load);
    load();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-city-picker]").forEach(initPicker);
  });
})();
