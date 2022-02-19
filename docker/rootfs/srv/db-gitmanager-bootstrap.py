import os
import sys

import django


def create_default_courses():
    from builder.models import Course, CourseUpdate

    course = Course.objects.create(
        key='default',
        remote_id=1,
        git_origin='/srv/courses/git_repo/default',
        git_branch='master',
        webhook_secret='',
    )
    return {
        'default': course,
    }


if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gitmanager.settings")
    sys.path.insert(0, '')
    django.setup()

    courses = create_default_courses()
