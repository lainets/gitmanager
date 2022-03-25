from django import forms
from django.forms import widgets

from util.log import SecurityLog
from .models import Course


class A(widgets.TextInput):
    template_name="builder/widgets/read_only_with_reset_button.html"

class CourseForm(forms.ModelForm):
    # disabled makes webhook_secret uneditable
    webhook_secret = forms.CharField(disabled=True, required=False, widget=A())

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

        for name in self.fields:
            if name not in ("email_on_error", "update_automatically"):
                self.fields[name].widget.attrs = {'class': 'form-control'}

    def save(self, request):
        if self.initial:
            SecurityLog.info(request, "EDIT-COURSE", f"{self.initial} {self.cleaned_data}")
        else:
            SecurityLog.info(request, "NEW-COURSE", f"... {self.cleaned_data}")
        return super().save()
