import json

from django import forms

from accounts.models import CustomUser

from .models import SpecialIssue


class SpecialIssueForm(forms.ModelForm):
    editors_input = forms.CharField(
        required=False,
        label='Other Editors (Optional)',
        widget=forms.TextInput(attrs={'id': 'editors-input'}),
        help_text=(
            "You are added as an editor automatically. Type a name to find a "
            "Labor Hub member, or enter any other editor's name."
        ),
    )

    class Meta:
        model = SpecialIssue
        fields = ['journal', 'title', 'description', 'call_url', 'submission_deadline']
        widgets = {
            'submission_deadline': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 6}),
        }
        labels = {
            'journal': 'Journal',
            'title': 'Title of Special Issue',
            'description': 'Description (include a link to the call for papers)',
            'call_url': 'Call for Papers Link (Optional)',
            'submission_deadline': 'Deadline for Submission',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_editors_input(self):
        raw = (self.cleaned_data.get('editors_input') or '').strip()
        if not raw:
            return []
        try:
            entries = json.loads(raw)
        except (TypeError, ValueError):
            raise forms.ValidationError("Could not read the editors list.")
        if not isinstance(entries, list):
            raise forms.ValidationError("Could not read the editors list.")

        editors, seen_ids, seen_names = [], set(), set()
        poster_id = self.user.id if self.user else None
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get('value', '')).strip()
            user_id = None
            member = None
            raw_id = entry.get('id')
            if raw_id:
                member = CustomUser.objects.filter(pk=str(raw_id)).first() if str(raw_id).isdigit() else None
            elif name:
                parts = name.split()
                if len(parts) >= 2:
                    member = CustomUser.objects.filter(
                        first_name__iexact=parts[0],
                        last_name__iexact=' '.join(parts[1:]),
                    ).first()
            if member:
                user_id = member.id
                name = member.get_full_name() or member.email
            if not name:
                continue
            # The poster is added by SpecialIssue.save(); skip repeats.
            if user_id is not None:
                if user_id == poster_id or user_id in seen_ids:
                    continue
                seen_ids.add(user_id)
            else:
                if name.lower() in seen_names:
                    continue
                seen_names.add(name.lower())
            editors.append({'name': name, 'user_id': user_id})
        return editors

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.editors = self.cleaned_data.get('editors_input', [])
        if commit:
            instance.save()
        return instance
