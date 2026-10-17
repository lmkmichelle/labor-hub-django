/**
 * Show a form field only while a trigger checkbox is checked.
 *
 * Wiring is by data attributes on a wrapper element, so no template inlines any
 * JavaScript. Two trigger modes:
 *
 *   Single checkbox, addressed by id:
 *     <div data-conditional-field
 *          data-when-checked="{{ form.is_job_market.id_for_label }}"
 *          data-target="{{ form.jm_advisor.id_for_label }}">
 *       ...the field to reveal...
 *     </div>
 *
 *   One checkbox out of a group (same name, different value):
 *     <div data-conditional-field
 *          data-when-checked-name="other_networks"
 *          data-when-checked-value="NBER"
 *          data-target="{{ form.network_url_nber.id_for_label }}">
 *       ...the field to reveal...
 *     </div>
 *
 *   One option of a radio group (e.g. the paper-type cards):
 *     <div data-conditional-field
 *          data-when-radio-name="paper_type"
 *          data-when-radio-value="job_market"
 *          data-target="{{ form.jm_advisor.id_for_label }}">
 *       ...the field to reveal while that option is selected...
 *     </div>
 *
 *   One pill in a Tagify input (e.g. the "other networks" picker):
 *     <div data-conditional-field
 *          data-when-pill-input="networks-input"
 *          data-when-pill-value="NBER"
 *          data-target="{{ form.network_url_nber.id_for_label }}">
 *       ...revealed while an "NBER" pill is present...
 *     </div>
 *
 * The target's ".mb-5" wrapper (emitted by partials/_form_field.html and
 * _select_field.html) is toggled, so the label hides with the control. The
 * state is applied once on load too, so a form redisplayed after a validation
 * error keeps the field open.
 */
(function () {
  function resolveCheckbox(root) {
    var byId = root.dataset.whenChecked;
    if (byId) {
      return document.getElementById(byId);
    }
    var name = root.dataset.whenCheckedName;
    var value = root.dataset.whenCheckedValue;
    if (name && value != null) {
      var selector =
        'input[type="checkbox"][name="' + name + '"][value="' + value + '"]';
      return document.querySelector(selector);
    }
    return null;
  }

  function initRadioField(root) {
    var name = root.dataset.whenRadioName;
    var value = root.dataset.whenRadioValue;
    var target = document.getElementById(root.dataset.target);
    var radios = document.querySelectorAll(
      'input[type="radio"][name="' + name + '"]'
    );
    if (!target || !radios.length) {
      return;
    }

    var wrapper = target.closest(".mb-5") || root;

    function apply() {
      var checked = document.querySelector(
        'input[type="radio"][name="' + name + '"]:checked'
      );
      // A radio only fires "change" on the option that became checked, so every
      // option in the group listens and re-evaluates this panel.
      var show = !!checked && checked.value === value;
      wrapper.classList.toggle("hidden", !show);
      root.classList.toggle("hidden", !show);
    }

    radios.forEach(function (radio) {
      radio.addEventListener("change", apply);
    });
    apply();
  }

  function pillValues(input) {
    var raw = (input.value || "").trim();
    if (!raw) {
      return [];
    }
    try {
      var parsed = JSON.parse(raw);
      return parsed.map(function (item) {
        return typeof item === "object" ? item.value : item;
      });
    } catch (e) {
      return raw.split(",").map(function (part) {
        return part.trim();
      });
    }
  }

  function initPillField(root) {
    var input = document.getElementById(root.dataset.whenPillInput);
    var target = document.getElementById(root.dataset.target);
    if (!input || !target) {
      return;
    }
    var wrapper = target.closest(".mb-5") || root;

    function apply() {
      var show = pillValues(input).indexOf(root.dataset.whenPillValue) !== -1;
      wrapper.classList.toggle("hidden", !show);
    }

    // Tagify rewrites the original input's value as pills are added or removed
    // (tagify.js re-dispatches "pillchange" so this does not depend on its events).
    ["change", "input", "pillchange"].forEach(function (type) {
      input.addEventListener(type, apply);
    });
    apply();
  }

  function initField(root) {
    if (root.dataset.whenPillInput) {
      initPillField(root);
      return;
    }
    if (root.dataset.whenRadioName) {
      initRadioField(root);
      return;
    }
    var checkbox = resolveCheckbox(root);
    var target = document.getElementById(root.dataset.target);
    if (!checkbox || !target) {
      return;
    }

    var wrapper = target.closest(".mb-5") || root;

    function apply() {
      wrapper.classList.toggle("hidden", !checkbox.checked);
    }

    checkbox.addEventListener("change", apply);
    apply();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-conditional-field]").forEach(initField);
  });
})();
