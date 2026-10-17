/**
 * PDF upload slots (templates/partials/_upload_slot.html) and the CV link/upload switch.
 *
 * Everything is optional enhancement: without this script a slot is a plain file input
 * and both CV panels stay visible.
 *
 *   [data-upload-slot]   shows the chosen filename, a Remove button, drag and drop, and
 *                        rejects non-PDFs inline.
 *   [data-upload-group]  keeps its "N of M added" counter ([data-upload-counter]) in step.
 *   [data-cv-card]       a Link | Upload PDF switch; shows only the chosen panel
 *                        ([data-cv-panel="link"|"upload"]) and clears the hidden one.
 */
(function () {
  function isPdf(file) {
    return file.type === "application/pdf" || /\.pdf$/i.test(file.name);
  }

  function initSlot(slot, onChange) {
    var input = slot.querySelector('input[type="file"]');
    var hint = slot.querySelector("[data-upload-hint]");
    var nameEl = slot.querySelector("[data-upload-name]");
    var remove = slot.querySelector("[data-upload-remove]");
    var error = slot.querySelector("[data-upload-error]");

    function setError(message) {
      error.textContent = message;
      error.classList.toggle("hidden", !message);
    }

    function render() {
      var file = input.files && input.files[0];
      slot.classList.toggle("upload-slot-done", !!file);
      hint.classList.toggle("hidden", !!file);
      nameEl.classList.toggle("hidden", !file);
      nameEl.textContent = file ? file.name : "";
      remove.classList.toggle("hidden", !file);
      onChange();
    }

    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (file && !isPdf(file)) {
        input.value = "";
        setError("Please choose a PDF file.");
      } else {
        setError("");
      }
      render();
    });

    remove.addEventListener("click", function () {
      input.value = "";
      setError("");
      render();
    });

    ["dragenter", "dragover"].forEach(function (type) {
      slot.addEventListener(type, function (event) {
        event.preventDefault();
        slot.classList.add("upload-slot-over");
      });
    });
    ["dragleave", "drop"].forEach(function (type) {
      slot.addEventListener(type, function () {
        slot.classList.remove("upload-slot-over");
      });
    });
    slot.addEventListener("drop", function (event) {
      event.preventDefault();
      var files = event.dataTransfer && event.dataTransfer.files;
      if (!files || !files.length) {
        return;
      }
      var transfer = new DataTransfer();
      transfer.items.add(files[0]);
      input.files = transfer.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });

    render();
  }

  function initGroup(group) {
    var slots = group.querySelectorAll("[data-upload-slot]");
    var counter = group.querySelector("[data-upload-counter]");
    function update() {
      if (!counter) {
        return;
      }
      var added = group.querySelectorAll(".upload-slot-done").length;
      counter.textContent = added + " of " + slots.length + " added";
    }
    slots.forEach(function (slot) {
      initSlot(slot, update);
    });
    update();
  }

  function initCvCard(card) {
    var switcher = card.querySelector("[data-js-only]");
    var panels = card.querySelectorAll("[data-cv-panel]");
    var radios = card.querySelectorAll('input[name="cv_mode"]');

    function apply() {
      var checked = card.querySelector('input[name="cv_mode"]:checked');
      var mode = checked ? checked.value : "link";
      panels.forEach(function (panel) {
        var active = panel.dataset.cvPanel === mode;
        panel.classList.toggle("hidden", !active);
        if (!active) {
          // The hidden alternative must not be submitted.
          panel.querySelectorAll("input").forEach(function (field) {
            if (field.type === "file") {
              field.value = "";
              field.dispatchEvent(new Event("change", { bubbles: true }));
            } else {
              field.value = "";
            }
          });
        }
      });
    }

    if (switcher) {
      switcher.classList.remove("hidden");
    }
    radios.forEach(function (radio) {
      radio.addEventListener("change", apply);
    });
    // On load only hide the inactive panel; never clear what a failed submit re-showed.
    var checked = card.querySelector('input[name="cv_mode"]:checked');
    var mode = checked ? checked.value : "link";
    panels.forEach(function (panel) {
      panel.classList.toggle("hidden", panel.dataset.cvPanel !== mode);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-upload-group]").forEach(initGroup);
    document.querySelectorAll("[data-upload-slot]").forEach(function (slot) {
      if (!slot.closest("[data-upload-group]")) {
        initSlot(slot, function () {});
      }
    });
    document.querySelectorAll("[data-cv-card]").forEach(initCvCard);
  });
})();
