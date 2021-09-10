import os
from typing import TYPE_CHECKING

from django.conf import settings

from util.pydantic import Undefined

if TYPE_CHECKING:
    from access.config import CourseConfig

def symbolic_link(courses_dir: str, course_key: str, course_config: "CourseConfig"):
    dst = os.path.join(settings.STATIC_ROOT, course_key)
    if not os.path.lexists(dst) and course_config.data.static_dir is not Undefined:
        src = os.path.join(courses_dir, course_key, course_config.data.static_dir)
        os.symlink(src, dst)
