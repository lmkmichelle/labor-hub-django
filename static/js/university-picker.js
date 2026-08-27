/**
 * Country-driven university picker.
 *
 * Narrows a university <select> to the institutions in the country chosen in a
 * sibling country <select>, fetching them from the universities endpoint. Used
 * by the visit form and by the profile / application forms, so the behaviour is
 * defined once rather than copied per template.
 *
 * Wiring is by data attributes on a wrapper element, so no template needs to
 * inline any JavaScript:
 *
 *   <div data-university-picker
 *        data-endpoint="{% url 'seminar-universities' %}"
 *        data-country-field="{{ form.country_code.id_for_label }}"
 *        data-university-field="{{ form.university.id_for_label }}">
 *
 * The university field is hidden until a country is picked, because the
 * endpoint needs a country code and an unfiltered list would be thousands of
 * rows long.
 */
(function () {
  function initPicker(root) {
    var endpoint = root.dataset.endpoint;
    var countrySelect = document.getElementById(root.dataset.countryField);
    var universitySelect = document.getElementById(root.dataset.universityField);
    if (!endpoint || !countrySelect || !universitySelect) {
      return;
    }

    // .mb-5 is the wrapper emitted by partials/_form_field.html and
    // _select_field.html; hiding it hides the label along with the control.
    var wrapper = universitySelect.closest(".mb-5");
    var placeholderText =
      root.dataset.placeholder || "Choose your institution";
    // Preserve an already-saved selection across the first refill, so editing a
    // profile does not silently clear the affiliation.
    var initialValue = universitySelect.value;

    function setVisible(show) {
      if (wrapper) {
        wrapper.classList.toggle("hidden", !show);
      }
    }

    function refill(universities) {
      var previous = universitySelect.value || initialValue;

      universitySelect.innerHTML = "";
      var placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = placeholderText;
      universitySelect.appendChild(placeholder);

      universities.forEach(function (uni) {
        var option = document.createElement("option");
        option.value = String(uni.id);
        option.textContent = uni.name;
        if (String(uni.id) === String(previous)) {
          option.selected = true;
        }
        universitySelect.appendChild(option);
      });
    }

    function load() {
      var country = (countrySelect.value || "").toUpperCase();
      if (!country) {
        setVisible(false);
        refill([]);
        return;
      }

      setVisible(true);
      fetch(endpoint + "?country=" + encodeURIComponent(country), {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      })
        .then(function (response) {
          return response.ok ? response.json() : { universities: [] };
        })
        .then(function (payload) {
          refill((payload && payload.universities) || []);
        })
        .catch(function () {
          // Leave the free-text fallback field as the way through.
          refill([]);
        });
    }

    countrySelect.addEventListener("change", function () {
      // A different country invalidates the saved selection.
      initialValue = "";
      load();
    });
    load();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-university-picker]").forEach(initPicker);
  });
})();
