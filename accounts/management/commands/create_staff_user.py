"""Create member accounts (optionally with admin access) and print temporary passwords.

Intended for onboarding the site's own faculty/administrators, who cannot use the
public application flow because nobody exists yet to approve them.

Each account is created directly (bypassing ``UserApplication``), gets its
``Profile`` via the ``post_save`` signal, and is assigned a freshly generated
random password that is printed **once** to stdout. Recipients should change it
at ``/accounts/password-change/`` on first sign-in.

Why generated passwords and not password-reset links?
    ``EMAIL_BACKEND`` defaults to Django's console backend, so on a deployment
    without SMTP configured a reset email is written to the log and never
    delivered. A printed temporary password works regardless of mail setup. If
    SMTP *is* configured, prefer ``--no-password`` and have each person use the
    "Forgot password" link instead, so no credential is ever displayed.

The command is idempotent: an address that already has an account is reported and
skipped, so a re-run never clobbers a password someone has already changed. Pass
``--reset-existing`` to deliberately issue a new temporary password instead.

Usage::

    python manage.py create_staff_user "Ada Lovelace <ada@example.edu>" --superuser
    python manage.py create_staff_user "Ada Lovelace <ada@example.edu>" \
        --superuser --country US --reset-existing
"""

import secrets
from email.utils import parseaddr

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import CustomUser, Profile
from core.constants import COUNTRY_CHOICES

# Ambiguous glyphs (0/O, 1/l/I) are excluded: these passwords get read aloud,
# retyped, and pasted out of chat clients before they are changed.
_PASSWORD_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_DEFAULT_PASSWORD_LENGTH = 20

_VALID_COUNTRY_CODES = {code for code, _ in COUNTRY_CHOICES}


def generate_password(length=_DEFAULT_PASSWORD_LENGTH, user=None):
    """Return a random password that satisfies AUTH_PASSWORD_VALIDATORS.

    Validation is re-run rather than assumed: the project's validator list is
    configuration and may gain rules this command knows nothing about.
    """
    for _ in range(10):
        candidate = "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))
        try:
            validate_password(candidate, user=user)
        except ValidationError:
            continue
        return candidate
    raise CommandError(
        "Could not generate a password passing AUTH_PASSWORD_VALIDATORS; "
        "try a longer --password-length."
    )


def parse_person(spec):
    """Split a ``"First Last <email@host>"`` spec into (first, last, email)."""
    display_name, address = parseaddr(spec)
    if not address or "@" not in address:
        raise CommandError(
            f'Could not read an email address from {spec!r}. '
            f'Expected the form "First Last <someone@example.edu>".'
        )

    name_parts = display_name.split()
    if len(name_parts) < 2:
        raise CommandError(
            f'Could not read a first and last name from {spec!r}. '
            f'Expected the form "First Last <someone@example.edu>".'
        )

    first_name = name_parts[0]
    last_name = " ".join(name_parts[1:])
    return first_name, last_name, address


class Command(BaseCommand):
    help = (
        "Create member accounts with generated temporary passwords, "
        'e.g. create_staff_user "Ada Lovelace <ada@example.edu>" --superuser'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "people",
            nargs="+",
            metavar="PERSON",
            help='One or more people as "First Last <email@example.edu>".',
        )
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Grant full Django admin access (is_staff + is_superuser).",
        )
        parser.add_argument(
            "--role",
            choices=[value for value, _ in CustomUser.Role.choices],
            default=CustomUser.Role.RESEARCHER,
            help=(
                "Directory role (default: researcher). Note that 'admin' hides the "
                "account from the public scholars directory."
            ),
        )
        parser.add_argument(
            "--country",
            default="",
            help="ISO country code for the profile, e.g. US. Places them on the world map.",
        )
        parser.add_argument(
            "--password-length",
            type=int,
            default=_DEFAULT_PASSWORD_LENGTH,
            help=f"Generated password length (default: {_DEFAULT_PASSWORD_LENGTH}).",
        )
        parser.add_argument(
            "--no-password",
            action="store_true",
            help=(
                "Create the account with an unusable password instead of a temporary "
                "one, so each person must use the 'Forgot password' link. Requires "
                "working SMTP."
            ),
        )
        parser.add_argument(
            "--reset-existing",
            action="store_true",
            help="Issue a new temporary password for accounts that already exist.",
        )

    def handle(self, *args, **options):
        country = (options["country"] or "").strip().upper()
        if country and country not in _VALID_COUNTRY_CODES:
            raise CommandError(f"Unknown country code {country!r}; expected an ISO code like US.")

        # Parse every spec up front so a typo in the third name does not leave the
        # first two accounts created.
        people = [parse_person(spec) for spec in options["people"]]

        results = []
        for first_name, last_name, email in people:
            with transaction.atomic():
                results.append(
                    self._upsert(
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        role=options["role"],
                        superuser=options["superuser"],
                        country=country,
                        password_length=options["password_length"],
                        no_password=options["no_password"],
                        reset_existing=options["reset_existing"],
                    )
                )

        self._report(results, no_password=options["no_password"])

    def _upsert(self, *, first_name, last_name, email, role, superuser, country,
                password_length, no_password, reset_existing):
        existing = CustomUser.objects.filter(email__iexact=email).first()

        if existing and not reset_existing:
            return {"email": email, "action": "skipped", "password": None}

        password = None if no_password else generate_password(password_length)

        if existing:
            user = existing
            if password is None:
                user.set_unusable_password()
            else:
                user.set_password(password)
            action = "password reset"
        else:
            manager = CustomUser.objects
            if superuser:
                # create_superuser sets is_staff/is_superuser/is_active itself.
                user = manager.create_superuser(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                )
            else:
                # create_user defaults to is_active=False (the application flow
                # activates accounts on approval); these are created by an admin
                # directly, so activate them here.
                user = manager.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                    is_active=True,
                )
            if password is None:
                user.set_unusable_password()
            action = "created"

        # Keep role/access in sync when refreshing an existing account, and let the
        # single save below persist the password set above.
        user.role = role
        if superuser:
            user.is_staff = True
            user.is_superuser = True
        user.is_active = True
        user.save()

        # The post_save signal creates the Profile; get_or_create is a guard for
        # accounts that predate it.
        profile, _ = Profile.objects.get_or_create(user=user)
        if country:
            profile.country_code = country
            profile.save(update_fields=["country_code"])

        return {"email": email, "action": action, "password": password}

    def _report(self, results, *, no_password):
        created = [r for r in results if r["action"] != "skipped"]
        skipped = [r for r in results if r["action"] == "skipped"]

        if created:
            self.stdout.write("")
            for result in created:
                secret = result["password"] or "(no password — use the reset link)"
                self.stdout.write(
                    "  {}  {}  [{}]".format(
                        result["email"].ljust(28), secret, result["action"]
                    )
                )
            self.stdout.write("")
            if not no_password:
                self.stdout.write(
                    self.style.WARNING(
                        "These passwords are shown once. Share them over a secure "
                        "channel and have each person change theirs at "
                        "/accounts/password-change/ after signing in."
                    )
                )

        for result in skipped:
            self.stdout.write(
                self.style.NOTICE(
                    "  {}  already exists — left unchanged "
                    "(use --reset-existing to issue a new password)".format(result["email"])
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "\n{} account(s) processed, {} skipped.".format(len(created), len(skipped))
            )
        )
