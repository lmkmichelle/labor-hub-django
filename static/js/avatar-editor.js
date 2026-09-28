/**
 * Avatar picker + crop/rotate/zoom modal for Edit Profile, backed by vendored Cropper.js.
 *
 * Wiring is by data attributes on a wrapper element, so no template needs to inline
 * any JavaScript:
 *
 *   <div data-avatar-editor>
 *     <div data-avatar-trigger role="button" tabindex="0"><img data-avatar-image></div>
 *     <input type="file" data-avatar-input>
 *     <div data-avatar-modal>
 *       <img data-avatar-modal-image>
 *       <button data-avatar-action="zoom-in">... (also zoom-out, rotate-left,
 *                                                   rotate-right, reset, cancel, save)
 *
 * Clicking the preview (or its camera badge) opens the native file picker; picking a
 * file opens the modal with Cropper.js on a copy of it. Nothing is written back to
 * the page, and nothing is uploaded differently, until Save: at that point the crop
 * box (in image pixels, post-rotation) is written into the form's hidden avatar_crop
 * field as JSON for the server to re-apply with Pillow, AND the actual cropped result
 * is rendered onto the page's own preview image, so what's shown is exactly what will
 * be saved. Cancelling (the X, the Cancel button, a backdrop click, or Escape)
 * discards the pick entirely and clears the file input, so nothing half-edited can
 * end up submitted.
 */
(function () {
  function initEditor(root) {
    var stageButton = root.querySelector('[data-avatar-trigger]');
    var fileInput = root.querySelector('[data-avatar-input]');
    var cropField = root.querySelector('input[name="avatar_crop"]');
    var pageImage = root.querySelector('[data-avatar-image]');
    var modal = root.querySelector('[data-avatar-modal]');
    var modalImage = root.querySelector('[data-avatar-modal-image]');
    if (!stageButton || !fileInput || !cropField || !pageImage || !modal || !modalImage
        || typeof Cropper === 'undefined') {
      return;
    }

    var cropper = null;
    var objectUrl = null;

    function onKeydown(e) {
      if (e.key === 'Escape') {
        discardAndClose();
      }
    }

    function openModal() {
      modal.classList.remove('hidden');
      document.addEventListener('keydown', onKeydown);
    }

    function closeModal() {
      modal.classList.add('hidden');
      document.removeEventListener('keydown', onKeydown);
    }

    function destroyCropper() {
      if (cropper) {
        cropper.destroy();
        cropper = null;
      }
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
    }

    function discardAndClose() {
      destroyCropper();
      fileInput.value = '';
      closeModal();
    }

    function save() {
      if (cropper) {
        cropField.value = JSON.stringify(cropper.getData(true));
        var canvas = cropper.getCroppedCanvas({ width: 512, height: 512 });
        if (canvas) {
          pageImage.src = canvas.toDataURL('image/jpeg', 0.92);
        }
      }
      destroyCropper();
      closeModal();
    }

    stageButton.addEventListener('click', function () {
      fileInput.click();
    });

    // The stage is a plain div (role="button"), not a real <button> -- see the
    // template comment for why -- so Enter/Space activation isn't free.
    stageButton.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInput.click();
      }
    });

    fileInput.addEventListener('change', function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file || !file.type.startsWith('image/')) {
        return;
      }

      destroyCropper();
      objectUrl = URL.createObjectURL(file);
      modalImage.src = objectUrl;
      openModal();

      modalImage.onload = function () {
        cropper = new Cropper(modalImage, {
          aspectRatio: 1,
          viewMode: 1,
          autoCropArea: 1,
          checkOrientation: true,
          background: false,
        });
      };
    });

    modal.addEventListener('click', function (e) {
      var action = e.target.closest('[data-avatar-action]');
      if (action) {
        switch (action.dataset.avatarAction) {
          case 'zoom-in':
            cropper && cropper.zoom(0.1);
            break;
          case 'zoom-out':
            cropper && cropper.zoom(-0.1);
            break;
          case 'rotate-left':
            cropper && cropper.rotate(-90);
            break;
          case 'rotate-right':
            cropper && cropper.rotate(90);
            break;
          case 'reset':
            cropper && cropper.reset();
            break;
          case 'cancel':
            discardAndClose();
            break;
          case 'save':
            save();
            break;
        }
        return;
      }
      // A click that landed on the backdrop itself (not the panel or a control
      // inside it) cancels, same as the X button.
      if (e.target === modal) {
        discardAndClose();
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-avatar-editor]').forEach(initEditor);
  });
})();
