"""Business logic for the accounts app, kept out of views per CLAUDE.md."""
from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps

# The stored avatar's pixel size: square, matching how it's displayed everywhere on
# the site (profile page, Scholars grid) and the crop UI's aspect ratio. 2x the 256px
# box those pages render it in, for crisp retina display.
AVATAR_OUTPUT_SIZE = (512, 512)


def process_avatar(image_file, crop=None, output_size=AVATAR_OUTPUT_SIZE):
    """Return a cropped/rotated, re-encoded JPEG avatar as an InMemoryUploadedFile.

    ``crop``, when given, is a dict with ``x``, ``y``, ``width``, ``height`` (in pixels,
    relative to the image *after* the rotation below) and ``rotate`` (degrees, one of
    0/90/180/270, clockwise -- matching Cropper.js's getData()). When it's None (no-JS
    fallback, or the user didn't touch the editor), a centred crop to output_size's
    aspect ratio is used instead, exactly as before.

    Always applies the image's EXIF orientation first -- without this, a portrait photo
    from a phone (stored as landscape pixels + an EXIF Orientation tag) comes out rotated
    90 degrees, since re-saving as JPEG below drops the EXIF tag that told browsers to
    rotate it.
    """
    with Image.open(image_file) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")

        if crop:
            img = _apply_crop(img, crop)
        else:
            img = _center_crop(img, output_size)

        img = img.resize(output_size, Image.LANCZOS)

        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=90)
        buffer.seek(0)

        return InMemoryUploadedFile(
            buffer,
            field_name='avatar',
            name='avatar.jpg',
            content_type='image/jpeg',
            size=buffer.tell(),
            charset=None,
        )


def _center_crop(img, output_size):
    target_ratio = output_size[0] / output_size[1]
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        new_height = img.height
        new_width = int(new_height * target_ratio)
    else:
        new_width = img.width
        new_height = int(new_width / target_ratio)

    left = (img.width - new_width) // 2
    top = (img.height - new_height) // 2
    return img.crop((left, top, left + new_width, top + new_height))


def _apply_crop(img, crop):
    rotate = crop.get('rotate', 0) % 360
    if rotate:
        # Cropper.js rotates clockwise and reports crop coordinates against the
        # rotated image; Pillow's rotate() is counter-clockwise, so negate.
        img = img.rotate(-rotate, expand=True)

    x, y = crop.get('x', 0), crop.get('y', 0)
    width, height = crop.get('width') or img.width, crop.get('height') or img.height

    # Clamp to the image bounds -- a stale crop box (e.g. from a differently-sized
    # re-upload) must not crash the request.
    left = max(0, min(int(x), img.width - 1))
    top = max(0, min(int(y), img.height - 1))
    right = max(left + 1, min(int(x + width), img.width))
    bottom = max(top + 1, min(int(y + height), img.height))

    return img.crop((left, top, right, bottom))
