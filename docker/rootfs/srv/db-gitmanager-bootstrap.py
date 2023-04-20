import os
import sys

import django


def create_default_courses():
    from builder.models import Course, CourseUpdate

    course = Course.objects.create(
        key='default',
        remote_id=1,
        git_origin='',
        git_branch='master',
        webhook_secret='xyz',
    )
    manual_course = Course.objects.create(
        key='aplus-manual',
        remote_id=2,
        git_origin='',
        git_branch='master',
        webhook_secret='abc',
    )
    test_course = Course.objects.create(
        key='test-course-master',
        remote_id=3,
        git_origin='',
        git_branch='master',
        webhook_secret='qwerty',
    )
    return {
        'default': course,
        'aplus-manual': manual_course,
        'test-course-master': test_course,
    }


if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gitmanager.settings")
    sys.path.insert(0, '')
    django.setup()

    courses = create_default_courses()
