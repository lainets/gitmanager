from django import forms

from .models import Course


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            'key',
            'remote_id',
            'update_automatically',
            'email_on_error',
            'git_origin',
            'git_branch',
            'webhook_secret',
            'update_hook',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # makes webhook_secret uneditable
        self.fields['webhook_secret'].disabled = True

        for name in self.fields:
            if name not in ("email_on_error", "update_automatically"):
                self.fields[name].widget.attrs = {'class': 'form-control'}
