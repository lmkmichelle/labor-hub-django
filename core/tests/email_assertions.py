"""Shared assertion for outgoing-email tests across apps.

Every transactional email is now multipart (plain text + HTML) with the site
logo attached inline via core.email.attach_logo -- this checks both in one
place instead of duplicating the same two assertions in every app's tests.
"""


def assert_has_html_alternative_with_logo(testcase, message):
    """Assert ``message`` has an HTML alternative and the inline CID logo."""
    html_alternatives = [
        content for content, mimetype in message.alternatives
        if mimetype == "text/html"
    ]
    testcase.assertEqual(
        len(html_alternatives), 1,
        "expected exactly one text/html alternative on the message")
    testcase.assertTrue(
        any(part.get("Content-ID") == "<labor_hub_logo>" for part in message.attachments),
        "expected the inline logo (core.email.attach_logo) to be attached")
    return html_alternatives[0]
