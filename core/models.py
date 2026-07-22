from django.db import models


class ContactMessage(models.Model):
    """A message submitted through the public contact form.

    Submissions are stored so they survive email outages and can be triaged in
    the Django admin; a notification email is also sent when one is created.
    """

    name = models.CharField(max_length=150)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(
        default=False,
        help_text="Mark once this inquiry has been followed up on.",
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} <{self.email}> ({self.created_at:%Y-%m-%d})"
