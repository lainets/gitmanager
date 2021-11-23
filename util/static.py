import os
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings

from util.files import rm_path
from util.pydantic import Undefined
from util.typing import PathLike

if TYPE_CHECKING:
    from access.config import CourseConfig


def static_path(course_config: "CourseConfig") -> Path:
    """Path to a course's static directory in STATIC_ROOT"""
    return Path(settings.STATIC_ROOT) / course_config.key


def symbolic_link(course_config: "CourseConfig"):
    """
    Creates symbolic links to unprotected static files
    """
    dst = static_path(course_config)
    rm_path(dst)

    static_dir = course_config.static_path_to()
    if static_dir is not None:
        static_dir = course_config.path_to(course_config.key, static_dir)
        if course_config.data.unprotected_paths is not Undefined:
            for path in course_config.data.unprotected_paths:
                (dst / path).parent.mkdir(parents=True, exist_ok=True)
                (dst / path).symlink_to(static_dir / path)
        else:
            dst.symlink_to(static_dir)


def static_url_path(course_key: str, *paths: PathLike):
    ''' Returns absolute URL path (no host) for a static file of a course '''
    return os.path.join(
        settings.STATIC_URL,
        course_key,
        *[os.fspath(p) for p in paths]
    )
