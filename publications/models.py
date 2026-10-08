import re

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models import F, JSONField, Max
from django.utils.text import slugify

from accounts.models import CustomUser
from core.constants import PAPER_COUNTRY_CHOICES
from core.models import Approvable

User = get_user_model()

class Author(models.Model):
    user = models.ForeignKey(CustomUser, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.user.get_full_name() if self.user else self.name

    class Meta:
        unique_together = [('user', 'name')]


class PublicationAuthor(models.Model):
    """Through model for Publication.authors, adding author order.

    Reuses the M2M table Django's plain ManyToManyField already created
    (``db_table``), so switching to ``through=`` here is schema-compatible --
    see publications/migrations/0023_publicationauthor_alter_publication_authors.py,
    which only adds the ``position`` column and backfills it.
    """
    publication = models.ForeignKey(
        'Publication', on_delete=models.CASCADE, related_name='author_links')
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'publications_publication_authors'
        ordering = ['position']
        unique_together = [('publication', 'author')]


class Publication(Approvable):
    title = models.CharField(max_length=200)
    authors = models.ManyToManyField(
        Author, related_name='publications', through=PublicationAuthor,
    )
    abstract = models.TextField()
    country_code = models.CharField(
        max_length=16,
        choices=PAPER_COUNTRY_CHOICES,
        blank=True,
        null=True
    )
    # A flat list of research topics, each an exact RECOMMENDED_KEYWORDS value.
    # Written only through publications.utils.handle_keywords.
    topic = JSONField(default=list, blank=True)
    is_job_market = models.BooleanField(default=False)
    # The publicly downloaded file: pdf_original with a generated cover page
    # prepended once the paper has a discussion_paper_number. Never edited
    # directly -- see rebuild_covered_pdf().
    pdf = models.FileField(upload_to='publications/pdf', null=True, blank=True)
    # The author's upload, untouched. The only source rebuild_covered_pdf()
    # ever reads from, so regenerating the cover (after an approval or a
    # later title/author edit) can't stack a second cover onto the first.
    pdf_original = models.FileField(
        upload_to='publications/pdf/original', null=True, blank=True,
    )
    applied_at = models.DateTimeField(auto_now_add=True)

    # Assigned the first time the paper is approved; None until then. Example
    # papers never get one, and job-market papers get job_market_paper_number
    # instead -- see assign_discussion_paper_number().
    discussion_paper_number = models.PositiveIntegerField(
        null=True, blank=True, unique=True,
    )
    # A separate "J" series for job-market papers (displayed as J1, J2, ...),
    # assigned instead of discussion_paper_number -- a job-market paper never
    # holds both. Independent counter, so it starts at 1 regardless of how
    # many regular papers have already been numbered.
    job_market_paper_number = models.PositiveIntegerField(
        null=True, blank=True, unique=True,
    )

    # A revised version of an earlier paper. Always points at the ORIGINAL
    # (never at another revision), so versions are 323, 323.1, 323.2 -- not
    # 323.1.1. A revision takes no slot in either numbering series; its number
    # is the original's plus revision_number. PROTECT so deleting an original
    # can't leave a revision with a dangling base number.
    revision_of = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='revisions',
    )
    revision_number = models.PositiveSmallIntegerField(null=True, blank=True)

    submitted_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_publications',
    )
    jm_advisor = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advised_job_market_papers',
        limit_choices_to={'role': CustomUser.Role.RESEARCHER},
        verbose_name='Job market advisor',
    )
    # None = not answered, True = acknowledged, False = declined.
    jm_advisor_acknowledged = models.BooleanField(null=True, blank=True)
    jm_advisor_responded_at = models.DateTimeField(null=True, blank=True)

    # Incremented by record_download() (publications/utils.py) -- once per
    # session per paper, and only for an approved paper -- so it reflects
    # public interest rather than an author repeatedly previewing their own
    # pending upload. Not user-editable; see PublicationAdmin.readonly_fields.
    download_count = models.PositiveIntegerField(default=0, editable=False)

    def __str__(self):
        return self.title

    @property
    def ordered_authors(self):
        """Authors in the order set on submission/edit (drag-and-drop in the
        Authors field), instead of `authors.all()`'s undefined M2M order.
        Prefetch with 'author_links__author__user' to avoid N+1."""
        return [link.author for link in self.author_links.all()]

    def formatted_date(self):
        """The paper's public date is when it was submitted."""
        return f"{self.applied_at:%Y-%m-%d}"

    @property
    def has_advisor_response(self):
        return self.jm_advisor_acknowledged is not None

    @property
    def display_number(self):
        """The number shown on the card/cover: "J3" for a job-market paper's
        own series, or the plain integer for the regular series. None until
        the paper has been assigned one of the two. A revision reads
        "323.1" / "J3.1": the original's number plus its revision number."""
        if self.revision_of_id is not None:
            base = self.revision_of.display_number
            if base is None or self.revision_number is None:
                return None
            return f"{base}.{self.revision_number}"
        if self.job_market_paper_number is not None:
            return f"J{self.job_market_paper_number}"
        if self.discussion_paper_number is not None:
            return str(self.discussion_paper_number)
        return None

    def assign_discussion_paper_number(self):
        """Assign the next number in the paper's series, once.

        A job-market paper gets the next slot in its own independent "J"
        series (job_market_paper_number); every other paper gets the next
        slot in the regular series (discussion_paper_number) -- never both.
        No-op if already numbered, and for example/seed rows, which never
        consume a slot in either series. `unique=True` on each field is the
        backstop against a race; the transaction+lock is what actually
        prevents one.
        """
        if self.is_example:
            return
        if self.revision_of_id is not None:
            self._assign_revision_number()
            return
        field = 'job_market_paper_number' if self.is_job_market else 'discussion_paper_number'
        if getattr(self, field) is not None:
            return
        with transaction.atomic():
            current_max = (
                Publication.objects.select_for_update()
                .exclude(**{field: None})
                .aggregate(Max(field))[f'{field}__max']
            )
            setattr(self, field, (current_max or 0) + 1)
            self.save(update_fields=[field])

    def _assign_revision_number(self):
        """Next .N under the original, once. Locks the original's row so two
        revisions approved together can't both take the same N."""
        if self.revision_number is not None:
            return
        with transaction.atomic():
            Publication.objects.select_for_update().get(pk=self.revision_of_id)
            current_max = (
                Publication.objects.filter(revision_of_id=self.revision_of_id)
                .aggregate(Max('revision_number'))['revision_number__max']
            )
            self.revision_number = (current_max or 0) + 1
            self.save(update_fields=['revision_number'])

    @classmethod
    def find_original(cls, raw, job_market_only=False):
        """Resolve "323", "323.1", "No. 323" or "J3" to the published ORIGINAL
        paper (a revision's number resolves to the paper it revises), or None."""
        match = re.fullmatch(
            r'(?i)(?:no\.?\s*)?(j)?\s*(\d+)(?:\.\d+)?', (raw or '').strip())
        if not match:
            return None
        is_jm = bool(match.group(1))
        if job_market_only and not is_jm:
            return None
        field = 'job_market_paper_number' if is_jm else 'discussion_paper_number'
        return cls.objects.filter(
            status='approved', revision_of__isnull=True,
            **{field: int(match.group(2))},
        ).first()

    def is_authored_by(self, user):
        """Whether ``user`` is one of this paper's authors -- linked to their
        account, or typed in under their full name (the rule the edit page
        has always used)."""
        if not user.is_authenticated:
            return False
        return (
            self.authors.filter(user=user).exists()
            or self.authors.filter(name=user.get_full_name()).exists()
        )

    def other_versions(self):
        """The original and every approved revision, except this paper.
        Ordered original first, then by revision."""
        original_id = self.revision_of_id or self.pk
        versions = Publication.objects.filter(status='approved').filter(
            models.Q(pk=original_id) | models.Q(revision_of_id=original_id)
        ).exclude(pk=self.pk).select_related('revision_of')
        return sorted(versions, key=lambda p: p.revision_number or 0)

    def record_download(self):
        """Bump download_count by one, atomically, without a read-modify-write
        race between two concurrent downloads. Updates the DB row directly
        rather than ``self.download_count += 1; self.save()``, and refreshes
        ``self`` so a caller that renders the count right after (there isn't
        one today, but a redirect-back page might) sees the new value."""
        Publication.objects.filter(pk=self.pk).update(
            download_count=F('download_count') + 1)
        self.refresh_from_db(fields=['download_count'])

    def rebuild_covered_pdf(self, save=True):
        """(Re)build the public `pdf` as pdf_original with a fresh cover
        page prepended. Always reads from pdf_original, never from pdf --
        that's what makes calling this twice idempotent instead of stacking
        a second cover on top of the first.

        No-op if there's no upload yet, or no paper number yet (an
        unapproved paper's own author can still download the plain
        pdf_original via `pdf` in the meantime; see PublicationForm.save()).
        """
        if not self.pdf_original or self.display_number is None:
            return
        # Local import: registering the cover fonts (and finding the vendored
        # static assets) at every model-module import would be wasted work
        # for the vast majority of requests that never approve a paper.
        from reportlab.lib.colors import black

        from .covers import build_covered_pdf

        author_names = [str(author) for author in self.ordered_authors]
        with self.pdf_original.open('rb') as f:
            original_bytes = f.read()

        # A job-market paper reuses the exact same backdrop/layout -- only the
        # overlay differs: black instead of Carnelian text, the "Job Market
        # Paper Series" label with its own (un-prefixed) number, and an
        # "Advisor: <name>" line whenever one is named on the paper. See
        # Jason's clarification in the paper-fixes plan.
        if self.is_job_market:
            covered = build_covered_pdf(
                original_bytes, self.job_market_paper_number, self.title,
                author_names, series_label='Job Market Paper Series',
                advisor=self.jm_advisor.get_full_name() if self.jm_advisor else None,
                text_color=black,
            )
            filename = f"JMP{self.job_market_paper_number}-{slugify(self.title)[:60]}.pdf"
        else:
            covered = build_covered_pdf(
                original_bytes, self.display_number, self.title, author_names,
            )
            filename = f"DP{self.display_number}-{slugify(self.title)[:60]}.pdf"
        self.pdf.save(filename, ContentFile(covered), save=save)

    def approve(self, admin_user=None):
        super().approve(admin_user)
        self.assign_discussion_paper_number()
        self.rebuild_covered_pdf()

