"""
If the app runs inside docker, TMP_DIR must be mounted to a directory on the host.
Set HOST_TMP_DIR inside BUILD_MODULE_SETTINGS to be that directory. This is so
that we can call docker and mount said directoty to the build container.
"""

import logging
import os.path
from typing import Any, Dict
import subprocess


def build(
        logger: logging.Logger,
        course_key: str,
        image: str,
        env: Dict[str, str],
        settings: Dict[str, Any],
        **kwargs,
        ) -> bool:
    env_args = [i for t in (("-e", f"{k}={v}") for k,v in env.items()) for i in t]
    host_path = os.path.join(settings["HOST_TMP_PATH"], course_key)
    command = [
        "docker", "run",
        *env_args,
        "-v", f"{host_path}:/content",
        "--workdir", "/content",
        image,
    ]

    logger.info(" ".join(command))

    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf8',
    )
    logger.info(process.stdout)
    return process.returncode == 0
