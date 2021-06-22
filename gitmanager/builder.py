import logging
import os.path
from pathlib import Path
import shutil
import subprocess
import traceback
from typing import List, Tuple

from django.conf import settings
from django.db.models.functions import Now
from huey.contrib.djhuey import db_task, lock_task

from access.config import config, META
from .models import CourseRepo, CourseUpdate, UpdateStatus


logger = logging.getLogger("grader.gitmanager")


def read_static_dir(course_key: str) -> str:
    '''
    Reads static_dir from course configuration.
    '''
    course = config.course_entry(course_key)
    if course and 'static_dir' in course:
        return course['static_dir']
    return ''


def git_call(path: str, command: str, cmd: List[str], include_cmd_string: bool = True) -> Tuple[bool, str]:
    if include_cmd_string:
        cmd_str = " ".join(["git", *cmd]) + "\n"
    else:
        cmd_str = ""
    response = subprocess.run(["git", "-C", path] + cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', env={"GIT_SSH_COMMAND": f"ssh -i {settings.SSH_KEY_PATH}"})
    if response.returncode != 0:
        return False, f"{cmd_str}Git {command}: returncode: {response.returncode}\nstdout: {response.stdout}\n"
    return True, cmd_str + response.stdout


def clone(path: str, origin: str, branch: str) -> Tuple[bool, str]:
    Path(path).mkdir(parents=True, exist_ok=True)

    return git_call(".", "clone", ["clone", "-b", branch, "--recursive", origin, path])


def checkout(path: str, origin: str, branch: str) -> Tuple[bool, str]:
    log = ""
    success = True
    # set the path beforehand, and handle logging
    def git(command: str, cmd: List[str]):
        nonlocal success, log
        if not success: # dont run the other commands if one fails
            return
        success, output = git_call(path, command, cmd)
        log += output + "\n"

    git("fetch", ["fetch", "origin", branch])
    git("clean", ["clean", "-xfd"])
    git("reset", ["reset", "-q", "--hard", f"origin/{branch}"])
    git("submodule sync", ["submodule", "sync", "--recursive"])
    git("submodule clean", ["submodule", "foreach", "--recursive", "git", "clean", "-xfd"])
    git("submodule reset", ["submodule", "foreach", "--recursive", "git", "reset", "-q", "--hard"])
    git("submodule update", ["submodule", "update", "--init", "--recursive"])

    return success, log


def pull(path: str, origin: str, branch: str) -> Tuple[bool, str]:
    if (Path(path) / ".git").exists():
        success, log = checkout(path, origin, branch)
    else:
        success, log = clone(path, origin, branch)

    if (Path(path) / ".git").exists():
        success2, log2 = git_call(path, "log", ["--no-pager", "log", '--pretty=format:------------\nCommit metadata\n\nHash:\n%H\nSubject:\n%s\nBody:\n%b\nCommitter:\n%ai\n%ae\nAuthor:\n%ci\n%cn\n%ce\n------------\n', "-1"], include_cmd_string=False)
        return success and success2, log2 + "\n" + log
    else:
        return success, "------------\nFailed to clone repository\n------------\n\n" + log


def container_build(path: Path, host_path: Path, course_key: str) -> Tuple[bool, str]:
    log = ""

    meta = config.course_meta(course_key)

    build_image = settings.DEFAULT_IMAGE
    if meta and "build_image" in meta:
        build_image = meta["build_image"]
        log += "Using build image: " + build_image + "\n\n"
    elif meta:
        log += f"No build_image in {META}, using the default: {build_image}\n\n"
    else:
        log += f"No {META} file, using the default build image: {build_image}\n\n"

    process = subprocess.run([
                settings.CONTAINER_SCRIPT,
                build_image,
                str(path.resolve()),
                str(host_path.resolve()),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf8'
        )
    return process.returncode == 0, log + process.stdout


def local_build(path: str) -> Tuple[bool, str]:
    log = ""
    success = True
    def run(command, **kwargs):
        nonlocal log, success
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf8', **kwargs)
        log += process.stdout + "\n"
        success = success and process.returncode == 0

    if Path(path, "build.sh").exists():
        log += "### Detected 'build.sh' executing it with bash. ###\n"
        run(["/bin/bash", "build.sh"], cwd=path)
    elif Path(path, "Makefile").exists():
        log += "### Detected a Makefile. Running 'make html'. Add nop 'build.sh' to disable this! ###\n"
        run(["make", "html"], cwd=path)
    else:
        log += "### No build.sh or Makefile. Not building the course. ###\n"

    return success, log


def build(path: Path, host_path: Path, course_key: str) -> Tuple[bool, str]:
    if settings.BUILD_IN_CONTAINER:
        return container_build(path, host_path, course_key)
    else:
        return local_build(str(path))


# lock_task to make sure that two updates don't happen at the same
# time. Would be better to lock it for each repo separately but it isn't really
# needed
@db_task()
@lock_task("push_event")
def push_event(course_key: str):
    logger.debug(f"push_event: {course_key}")

    repo = CourseRepo.objects.get(key=course_key)

    # delete all but latest 10 updates
    updates = CourseUpdate.objects.filter(course_repo=repo).order_by("-request_time")[10:]
    for update in updates:
        update.delete()
    # get pending updates
    updates = CourseUpdate.objects.filter(course_repo=repo, status=UpdateStatus.PENDING).order_by("request_time").all()

    updates = list(updates)
    if len(updates) == 0:
        return

    # skip all but the most recent update
    for update in updates[:-1]:
        update.status = UpdateStatus.SKIPPED
        update.save()

    update = updates[-1]
    update.status = UpdateStatus.RUNNING
    update.save()

    path = os.path.join(settings.COURSES_PATH, course_key)
    try:
        pull_status, update.log = pull(path, repo.git_origin, repo.git_branch)
        if not pull_status:
            return

        tmp_path = Path(settings.TMP_DIR, course_key)
        host_tmp_path = Path(settings.HOST_TMP_DIR, course_key)

        # copy the course material to a tmp folder
        if tmp_path.is_dir():
            shutil.rmtree(tmp_path)
        elif tmp_path.exists():
            tmp_path.unlink()
        shutil.copytree(path, tmp_path, symlinks=True)

        # build in tmp folder
        build_status, build_log = build(tmp_path, host_tmp_path, course_key)
        update.log += "\n" + build_log
        if not build_status:
            return

        # copy the course material back
        shutil.rmtree(path)
        shutil.copytree(tmp_path, path, symlinks=True)

        # link static dir
        static_dir = read_static_dir(course_key)
        if static_dir:
            update.log += f"\nLinking static dir {static_dir}\n"
            src_path = Path("static", course_key)
            if src_path.exists() or src_path.is_symlink():
                src_path.unlink()
            src_path.symlink_to(Path(path, static_dir))

        # all went well
        update.status = UpdateStatus.SUCCESS
    except:
        update.log += "\n" + traceback.format_exc()
        raise
    finally:
        if update.status != UpdateStatus.SUCCESS:
            update.status = UpdateStatus.FAILED
        update.updated_time = Now()
        update.save()

    if update.status == UpdateStatus.SUCCESS:
        pass
        # TODO: ? reload uwsgi processes

        # TODO: let LMS know about the update
