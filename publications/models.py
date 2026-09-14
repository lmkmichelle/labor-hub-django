from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models import JSONField, Max
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

class Publication(Approvable):
    title = models.CharField(max_length=200)
    authors = models.ManyToManyField(Author, related_name='publications')
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
    # papers never get one (see assign_discussion_paper_number).
    discussion_paper_number = models.PositiveIntegerField(
        null=True, blank=True, unique=True,
    )

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

    def __str__(self):
        return self.title

    def formatted_date(self):
        """The paper's public date is when it was submitted."""
        return f"{self.applied_at:%Y-%m-%d}"

    @property
    def has_advisor_response(self):
        return self.jm_advisor_acknowledged is not None

    def assign_discussion_paper_number(self):
        """Assign the next number in the discussion-paper series, once.

        No-op if already numbered, and for example/seed rows -- those never
        consume a slot in the real series. `unique=True` is the backstop
        against a race; the transaction+lock is what actually prevents one.
        """
        if self.discussion_paper_number is not None or self.is_example:
            return
        with transaction.atomic():
            current_max = (
                Publication.objects.select_for_update()
                .exclude(discussion_paper_number=None)
                .aggregate(Max('discussion_paper_number'))['discussion_paper_number__max']
            )
            self.discussion_paper_number = (current_max or 0) + 1
            self.save(update_fields=['discussion_paper_number'])

    def rebuild_covered_pdf(self, save=True):
        """(Re)build the public `pdf` as pdf_original with a fresh cover
        page prepended. Always reads from pdf_original, never from pdf --
        that's what makes calling this twice idempotent instead of stacking
        a second cover on top of the first.

        No-op if there's no upload yet, or no discussion paper number yet
        (an unapproved paper's own author can still download the plain
        pdf_original via `pdf` in the meantime; see PublicationForm.save()).
        """
        if not self.pdf_original or self.discussion_paper_number is None:
            return
        # Local import: registering the cover fonts (and finding the vendored
        # static assets) at every model-module import would be wasted work
        # for the vast majority of requests that never approve a paper.
        from .covers import build_covered_pdf

        author_names = [str(author) for author in self.authors.all()]
        with self.pdf_original.open('rb') as f:
            original_bytes = f.read()
        covered = build_covered_pdf(
            original_bytes, self.discussion_paper_number, self.title, author_names,
        )
        filename = f"DP{self.discussion_paper_number}-{slugify(self.title)[:60]}.pdf"
        self.pdf.save(filename, ContentFile(covered), save=save)

    def approve(self, admin_user=None):
        super().approve(admin_user)
        self.assign_discussion_paper_number()
        self.rebuild_covered_pdf()

