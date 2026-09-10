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

  function initField(root) {
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
