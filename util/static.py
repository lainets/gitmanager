import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional
import urllib.parse

from django.conf import settings
from builder.models import Course

from util.files import rm_path
from util.pydantic import Undefined
from util.typing import PathLike

if TYPE_CHECKING:
    from access.config import CourseConfig


def static_path_from_key(course_key: str) -> Path:
    """Path to a course's static directory in STATIC_ROOT"""
    return Path(settings.STATIC_ROOT) / course_key


def static_path(course_config: "CourseConfig") -> Path:
    """Path to a course's static directory in STATIC_ROOT"""
    return static_path_from_key(course_config.key)


def symbolic_link(course_config: "CourseConfig"):
    """
    Creates symbolic links to unprotected static files
    """
    dst = static_path(course_config)
    rm_path(dst)

    try:
        remote_id = Course.objects.get(key=course_config.key).remote_id
    except Course.DoesNotExist:
        id_dst = None
    else:
        # dst as if the remote_id was the course key
        # allows static file access using the remote_id instead of the key
        id_dst = static_path_from_key(str(remote_id))
        rm_path(id_dst)

    static_dir = course_config.static_path_to()
    if static_dir is not None:
        static_dir = course_config.path_to(course_config.key, static_dir)
        if course_config.data.unprotected_paths is not Undefined:
            for path in course_config.data.unprotected_paths:
                (dst / path).parent.mkdir(parents=True, exist_ok=True)
                (dst / path).symlink_to(static_dir / path)
            if id_dst is not None and course_config.data.unprotected_paths:
                id_dst.symlink_to(dst)
        else:
            dst.symlink_to(static_dir)
            if id_dst is not None:
                id_dst.symlink_to(dst)


def static_url_path(course_key: str, *paths: PathLike):
    ''' Returns absolute URL path (no host) for a static file of a course '''
    return os.path.join(
        settings.STATIC_URL,
        course_key,
        *[os.fspath(p) for p in paths]
    )


def static_url(course_key: str, *paths: PathLike) -> Optional[str]:
    if settings.STATIC_CONTENT_HOST:
        return urllib.parse.urljoin(
            settings.STATIC_CONTENT_HOST,
            static_url_path(course_key, *paths)
        )
    else:
        return None
