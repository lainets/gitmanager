import logging
from pathlib import Path
from typing import Dict
import subprocess


def build(
        logger: logging.Logger,
        path: Path,
        env: Dict[str, str],
        **kwargs,
        ) -> bool:
    success = True
    def run(command, **kwargs):
        nonlocal success, env
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf8', env=env, **kwargs)
        logger.info(process.stdout + "\n")
        success = success and process.returncode == 0

    if Path(path, "build.sh").exists():
        logger.info("### Detected 'build.sh' executing it with bash. ###\n")
        run(["/bin/bash", "build.sh"], cwd=path)
    elif Path(path, "Makefile").exists():
        logger.info("### Detected a Makefile. Running 'make html'. Add nop 'build.sh' to disable this! ###\n")
        run(["make", "html"], cwd=path)
    else:
        logger.info("### No build.sh or Makefile. Not building the course. ###\n")

    return success
