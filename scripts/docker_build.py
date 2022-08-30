"""
If the app runs inside docker, BUILD_PATH and COURSES_PATH must be mounted to a directory on the host.
Inside BUILD_MODULE_SETTINGS, set CONTAINER_BUILD_PATH to BUILD_PATH, CONTAINER_PUBLISH_PATH to COURSES_PATH,
HOST_BUILD_PATH to the directory where BUILD_PATH is on host and HOST_PUBLISH_PATH to the directory where
COURSES_PATH is on host. This is so that we can call docker and mount said directory to the build container.
"""

import logging
import os.path
from pathlib import Path
from typing import Any, Dict, List, Optional
import subprocess


def build(
        logger: logging.Logger,
        path: Path,
        image: str,
        cmd: Optional[List[str]],
        env: Dict[str, str],
        settings: Dict[str, Any],
        **kwargs,
        ) -> bool:
    env_args = [i for t in (("-e", f"{k}={v}") for k,v in env.items()) for i in t]
    if str(path).startswith(settings["CONTAINER_BUILD_PATH"]):
        host_path = str(path).replace(settings["CONTAINER_BUILD_PATH"], settings["HOST_BUILD_PATH"])
    elif str(path).startswith(settings["CONTAINER_PUBLISH_PATH"]):
        host_path = str(path).replace(settings["CONTAINER_PUBLISH_PATH"], settings["HOST_PUBLISH_PATH"])
    else:
        raise Exception("Couldn't determine path on host. Check the BUILD_MODULE_SETTINGS in (local_)settings.py")

    command = [
        "docker", "run",
        *env_args,
        "-v", f"{host_path}:/content",
        "--workdir", "/content",
        image,
    ]

    if cmd is not None:
        command.extend(cmd)

    logger.info(" ".join(command))

    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf8',
    )
    logger.info(process.stdout)
    return process.returncode == 0
