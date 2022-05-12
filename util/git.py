from logging import Logger, getLogger
from pathlib import Path
import os
import subprocess
from typing import List, Tuple

from django.conf import settings

from util.files import rm_path
from util.typing import PathLike


default_logger = getLogger("util.git")

# Copy the environment for use in git calls. In particular, the HOME variable is needed to find the .gitconfig file
# in case it contains something necessary (like safe.directories)
git_env = os.environ.copy()
git_env["GIT_SSH_COMMAND"] = f"ssh -i {settings.SSH_KEY_PATH}"


def git_call(path: str, command: str, cmd: List[str], include_cmd_string: bool = True) -> Tuple[bool, str]:
    global git_env
    
    if include_cmd_string:
        cmd_str = " ".join(["git", *cmd]) + "\n"
    else:
        cmd_str = ""

    response = subprocess.run(["git", "-C", path] + cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', env=git_env)
    if response.returncode != 0:
        return False, f"{cmd_str}Git {command}: returncode: {response.returncode}\nstdout: {response.stdout}\n"

    return True, cmd_str + response.stdout


def clone(path: str, origin: str, branch: str, *, logger: Logger = default_logger) -> bool:
    Path(path).mkdir(parents=True, exist_ok=True)

    success, logstr = git_call(".", "clone", ["clone", "-b", branch, "--recursive", origin, path])
    logger.info(logstr)
    return success


def checkout(path: str, origin: str, branch: str, *, logger: Logger = default_logger) -> bool:
    success = True
    # set the path beforehand, and handle logging
    def git(command: str, cmd: List[str]):
        nonlocal success
        if not success: # dont run the other commands if one fails
            return
        success, output = git_call(path, command, cmd)
        logger.info(output)

    git("fetch", ["fetch", "origin", branch])
    git("clean", ["clean", "-xfd"])
    git("reset", ["reset", "-q", "--hard", f"origin/{branch}"])
    git("submodule sync", ["submodule", "sync", "--recursive"])
    git("submodule clean", ["submodule", "foreach", "--recursive", "git", "clean", "-xfd"])
    git("submodule reset", ["submodule", "foreach", "--recursive", "git", "reset", "-q", "--hard"])
    git("submodule update", ["submodule", "update", "--init", "--recursive"])

    return success


def has_origin(path: str, origin: str) -> bool:
    success, origin_url = git_call(path, "remote", ["remote", "get-url", "origin"], include_cmd_string=False)
    return origin == origin_url.strip()


def pull(path: str, origin: str, branch: str, *, logger: Logger = default_logger) -> bool:
    success = False
    do_clone = True
    if Path(path, ".git").exists():
        if has_origin(path, origin):
            do_clone = False
            success = checkout(path, origin, branch, logger=logger)
        else:
            logger.info("Wrong origin in repo, recloning\n\n")

    if do_clone:
        rm_path(path)
        success = clone(path, origin, branch, logger=logger)

    if (Path(path) / ".git").exists():
        success2, logstr = git_call(path, "log", ["--no-pager", "log", '--pretty=format:------------\nCommit metadata\n\nHash:\n%H\nSubject:\n%s\nBody:\n%b\nCommitter:\n%ai\n%ae\nAuthor:\n%ci\n%cn\n%ce\n------------\n', "-1"], include_cmd_string=False)
        logger.info(logstr)
        return success and success2
    else:
        logger.info("------------\nFailed to clone repository\n------------\n\n")
        return success


def get_commit_hash(path: PathLike) -> str:
    success, hash_or_error = git_call(os.fspath(path), "rev-parse", ["HEAD"], include_cmd_string = False)
    if success:
        return hash_or_error
    else:
        raise RuntimeError(hash_or_error)
