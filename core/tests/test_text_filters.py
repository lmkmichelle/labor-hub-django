from django.test import SimpleTestCase

from core.templatetags.text_filters import soften_linebreaks


class SoftenLinebreaksTests(SimpleTestCase):
    def test_empty_value_is_unchanged(self):
        self.assertEqual(soften_linebreaks(""), "")
        self.assertIsNone(soften_linebreaks(None))

    def test_hard_wrapped_single_newlines_become_spaces(self):
        text = "This paper exploits\nestablishment mobility as a novel\nsource."
        self.assertEqual(
            soften_linebreaks(text),
            "This paper exploits establishment mobility as a novel source.",
        )

    def test_blank_line_paragraph_breaks_are_preserved(self):
        text = "First paragraph,\nhard-wrapped.\n\nSecond paragraph."
        self.assertEqual(
            soften_linebreaks(text),
            "First paragraph, hard-wrapped.\n\nSecond paragraph.",
        )

    def test_multiple_blank_lines_still_count_as_one_paragraph_break(self):
        text = "First.\n\n\nSecond."
        self.assertEqual(soften_linebreaks(text), "First.\n\nSecond.")

    def test_leading_and_trailing_whitespace_is_stripped(self):
        text = "\n  Padded text.  \n"
        self.assertEqual(soften_linebreaks(text), "Padded text.")

    def test_plain_prose_with_no_embedded_newlines_is_unchanged(self):
        text = "A single continuous paragraph with no hard wraps at all."
        self.assertEqual(soften_linebreaks(text), text)
