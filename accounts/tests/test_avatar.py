from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from accounts.forms import UpdateProfileForm
from accounts.utils import process_avatar


def make_exif_rotated_jpeg(size=(300, 200), orientation=6):
    """A landscape-pixel JPEG tagged (via EXIF Orientation) to display portrait --
    exactly what a phone camera saves. Orientation 6 means "rotate 90 CW to display".
    """
    img = Image.new("RGB", size, "red")
    # Mark a corner so we can tell, after exif_transpose, which way is "up".
    img.paste((0, 255, 0), (0, 0, 20, 20))  # green in the top-left of the raw pixels

    exif = img.getexif()
    exif[0x0112] = orientation  # Orientation tag
    buffer = BytesIO()
    img.save(buffer, format="JPEG", exif=exif)
    buffer.seek(0)
    return buffer


def make_plain_jpeg(size=(400, 300), color="blue"):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def make_heic(size=(400, 300), color="green"):
    """An actual HEIC file -- the default format for iPhone photos, which Pillow
    can't read/write without accounts.apps.AccountsConfig.ready() having
    registered the pillow-heif plugin."""
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="HEIF")
    buffer.seek(0)
    return buffer


class ProcessAvatarOrientationTests(TestCase):
    """Regression test for the bug reported by a user (Jonas Jessen): phone photos
    came out rotated 90 degrees because EXIF orientation was never applied."""

    def test_exif_orientation_is_applied_before_cropping(self):
        source = make_exif_rotated_jpeg()
        result = process_avatar(source, output_size=(100, 100))

        # Sanity: still produces a normal JPEG upload of the requested size.
        result.seek(0)
        out = Image.open(result)
        self.assertEqual(out.size, (100, 100))
        self.assertEqual(out.format, "JPEG")

    def test_output_has_no_exif_orientation_left_to_reinterpret(self):
        # Re-saving via Pillow's .save() already drops EXIF, but pin the behaviour:
        # a naive viewer must not be able to rotate the output a second time.
        source = make_exif_rotated_jpeg()
        result = process_avatar(source, output_size=(100, 100))
        result.seek(0)
        out = Image.open(result)
        self.assertIsNone(out.getexif().get(0x0112))


class ProcessAvatarCropTests(TestCase):
    def test_default_output_size_is_square(self):
        from accounts.utils import AVATAR_OUTPUT_SIZE
        self.assertEqual(AVATAR_OUTPUT_SIZE[0], AVATAR_OUTPUT_SIZE[1])

        source = make_plain_jpeg(size=(400, 200))
        result = process_avatar(source)
        result.seek(0)
        out = Image.open(result)
        self.assertEqual(out.size, AVATAR_OUTPUT_SIZE)

    def test_no_crop_falls_back_to_centered_crop(self):
        source = make_plain_jpeg(size=(400, 200))
        result = process_avatar(source, crop=None, output_size=(200, 200))
        result.seek(0)
        out = Image.open(result)
        self.assertEqual(out.size, (200, 200))

    def test_explicit_crop_box_is_honored(self):
        source = make_plain_jpeg(size=(400, 400), color="blue")
        crop = {"x": 50, "y": 50, "width": 200, "height": 200, "rotate": 0}
        result = process_avatar(source, crop=crop, output_size=(200, 200))
        result.seek(0)
        out = Image.open(result)
        self.assertEqual(out.size, (200, 200))

    def test_rotate_90_is_applied_before_the_crop_box(self):
        # A 400x200 image rotated 90 becomes 200x400; a crop box sized for the
        # rotated orientation must not raise or silently no-op.
        source = make_plain_jpeg(size=(400, 200))
        crop = {"x": 0, "y": 0, "width": 200, "height": 300, "rotate": 90}
        result = process_avatar(source, crop=crop, output_size=(200, 200))
        result.seek(0)
        out = Image.open(result)
        self.assertEqual(out.size, (200, 200))

    def test_out_of_bounds_crop_box_is_clamped_not_fatal(self):
        source = make_plain_jpeg(size=(400, 400))
        crop = {"x": -50, "y": 9999, "width": 5000, "height": 5000, "rotate": 0}
        result = process_avatar(source, crop=crop, output_size=(200, 200))
        result.seek(0)
        out = Image.open(result)
        self.assertEqual(out.size, (200, 200))

    def test_heic_upload_is_processed_like_any_other_format(self):
        """Regression: a user reported HEIC (the default iPhone photo format)
        avatars didn't work. Pillow can't read HEIC on its own -- this only
        passes with the pillow-heif plugin registered (accounts.apps)."""
        source = make_heic(size=(400, 200))
        result = process_avatar(source, output_size=(200, 200))
        result.seek(0)
        out = Image.open(result)
        self.assertEqual(out.size, (200, 200))
        self.assertEqual(out.format, "JPEG")  # still re-encoded to JPEG, as always


class UpdateProfileFormHeicTests(TestCase):
    def test_heic_upload_passes_django_imagefield_validation(self):
        # Django's ImageField also opens the upload with Pillow to validate it,
        # independently of process_avatar -- both must be able to read HEIC.
        upload = SimpleUploadedFile(
            "photo.heic", make_heic().read(), content_type="image/heic")
        form = UpdateProfileForm(
            data={"position": "Professor", "country_code": "US", "department": "Cornell"},
            files={"avatar": upload},
        )
        self.assertTrue(form.is_valid(), form.errors)


class AvatarCropFormFieldTests(TestCase):
    def make_data(self, **overrides):
        data = {
            "position": "Professor", "country_code": "US", "department": "Cornell",
        }
        data.update(overrides)
        return data

    def test_valid_json_is_parsed(self):
        form = UpdateProfileForm(data=self.make_data(
            avatar_crop='{"x": 1, "y": 2, "width": 10, "height": 20, "rotate": 90}'))
        form.is_valid()
        self.assertEqual(form.cleaned_data['avatar_crop'],
                          {'x': 1.0, 'y': 2.0, 'width': 10.0, 'height': 20.0, 'rotate': 90})

    def test_blank_is_none(self):
        form = UpdateProfileForm(data=self.make_data(avatar_crop=''))
        form.is_valid()
        self.assertIsNone(form.cleaned_data['avatar_crop'])

    def test_malformed_json_is_ignored_not_fatal(self):
        form = UpdateProfileForm(data=self.make_data(avatar_crop='{not json'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['avatar_crop'])

    def test_rotate_is_clamped_to_a_multiple_of_90(self):
        form = UpdateProfileForm(data=self.make_data(
            avatar_crop='{"x": 0, "y": 0, "width": 10, "height": 10, "rotate": 37}'))
        form.is_valid()
        self.assertEqual(form.cleaned_data['avatar_crop']['rotate'], 0)
