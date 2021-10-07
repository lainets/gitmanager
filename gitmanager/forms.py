from django import forms

from .models import Course


class CourseForm(forms.ModelForm):

    class Meta:
        model = Course
        fields = [
            'key',
            'remote_id',
            'email_on_error',
            'git_origin',
            'git_branch',
            'update_hook',
        ]
