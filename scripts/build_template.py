import logging
from pathlib import Path
from typing import Any, Dict, List, Optional


def build(
        logger: logging.Logger,
        course_key: str,
        path: Path,
        image: str,
        cmd: Optional[List[str]],
        env: Dict[str, str],
        settings: Any,
        **kwargs,
        ) -> bool:
    """
    Build the course rooted at <path> synchronously. Use <logger> to log build
    output and return whether the build succeeded. <settings> is the value
    specified in django settings for BUILD_MODULE_SETTINGS. <image> and <cmd> are
    the image and command specified in the course apps.meta file (or a default
    from git manager settings). <env> contains the build environment variables
    as specified in courses/README.md.
    """