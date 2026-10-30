"""Reading the unsubscribe links in newsletter emails sent before the newsletter was
a Campaign Monitor campaign (those emails were the old per-user "digest" and are
still in people's inboxes). New issues unsubscribe through Campaign Monitor's own
link; nothing creates these tokens any more."""
from django.core import signing

# The salt the old tokens were signed with. It must not change or existing links die.
LEGACY_SALT = "accounts.digests.unsubscribe"


def read_newsletter_unsubscribe_token(token, max_age=None):
    """Return the user id encoded in ``token`` or ``None`` if invalid."""
    try:
        data = signing.loads(token, salt=LEGACY_SALT, max_age=max_age)
    except signing.BadSignature:
        return None
    return data.get("uid")
