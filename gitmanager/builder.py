from io import StringIO
import logging
from pathlib import Path
import shutil
import subprocess
import traceback
from typing import List, Tuple

from django.conf import settings
from django.db.models.functions import Now
from huey.contrib.djhuey import db_task, lock_task

from access.config import CourseConfig as config, META
from .models import Course, CourseUpdate, UpdateStatus


logger = logging.getLogger("grader.gitmanager")

build_logger = logging.getLogger("gitmanager.build")
build_logger.setLevel(logging.DEBUG)


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


def clone(path: str, origin: str, branch: str) -> bool:
    Path(path).mkdir(parents=True, exist_ok=True)

    success, logstr = git_call(".", "clone", ["clone", "-b", branch, "--recursive", origin, path])
    build_logger.info(logstr)
    return success


def checkout(path: str, origin: str, branch: str) -> bool:
    success = True
    # set the path beforehand, and handle logging
    def git(command: str, cmd: List[str]):
        nonlocal success
        if not success: # dont run the other commands if one fails
            return
        success, output = git_call(path, command, cmd)
        build_logger.info(output + "\n")

    git("fetch", ["fetch", "origin", branch])
    git("clean", ["clean", "-xfd"])
    git("reset", ["reset", "-q", "--hard", f"origin/{branch}"])
    git("submodule sync", ["submodule", "sync", "--recursive"])
    git("submodule clean", ["submodule", "foreach", "--recursive", "git", "clean", "-xfd"])
    git("submodule reset", ["submodule", "foreach", "--recursive", "git", "reset", "-q", "--hard"])
    git("submodule update", ["submodule", "update", "--init", "--recursive"])

    return success


def pull(path: str, origin: str, branch: str) -> bool:
    if (Path(path) / ".git").exists():
        success = checkout(path, origin, branch)
    else:
        success = clone(path, origin, branch)

    if (Path(path) / ".git").exists():
        success2, logstr = git_call(path, "log", ["--no-pager", "log", '--pretty=format:------------\nCommit metadata\n\nHash:\n%H\nSubject:\n%s\nBody:\n%b\nCommitter:\n%ai\n%ae\nAuthor:\n%ci\n%cn\n%ce\n------------\n', "-1"], include_cmd_string=False)
        build_logger.info("\n" + logstr)
        return success and success2
    else:
        build_logger.info("------------\nFailed to clone repository\n------------\n\n")
        return success


def container_build(path: Path, host_path: Path, course_key: str) -> bool:
    meta = config.course_meta(course_key)

    build_image = settings.DEFAULT_IMAGE
    if meta and "build_image" in meta:
        build_image = meta["build_image"]
        build_logger.info("Using build image: " + build_image + "\n\n")
    elif meta:
        build_logger.info(f"No build_image in {META}, using the default: {build_image}\n\n")
    else:
        build_logger.info(f"No {META} file, using the default build image: {build_image}\n\n")

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
    build_logger.info(process.stdout)
    return process.returncode == 0


def local_build(path: str) -> bool:
    success = True
    def run(command, **kwargs):
        nonlocal success
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf8', **kwargs)
        build_logger.info(process.stdout + "\n")
        success = success and process.returncode == 0

    if Path(path, "build.sh").exists():
        build_logger.info("### Detected 'build.sh' executing it with bash. ###\n")
        run(["/bin/bash", "build.sh"], cwd=path)
    elif Path(path, "Makefile").exists():
        build_logger.info("### Detected a Makefile. Running 'make html'. Add nop 'build.sh' to disable this! ###\n")
        run(["make", "html"], cwd=path)
    else:
        build_logger.info("### No build.sh or Makefile. Not building the course. ###\n")

    return success


def build(path: Path, host_path: Path, course_key: str) -> bool:
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

    course: Course = Course.objects.get(key=course_key)

    # delete all but latest 10 updates
    updates = CourseUpdate.objects.filter(course=course).order_by("-request_time")[10:]
    for update in updates:
        update.delete()
    # get pending updates
    updates = CourseUpdate.objects.filter(course=course, status=UpdateStatus.PENDING).order_by("request_time").all()

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

    path = course.path

    log_stream = StringIO()
    log_handler = logging.StreamHandler(log_stream)
    build_logger.addHandler(log_handler)
    try:
        if course.git_origin:
            pull_status = pull(path, course.git_origin, course.git_branch)
            if not pull_status:
                return
        else:
            build_logger.warning(f"Course origin not set: skipping git update\n")

        tmp_path = Path(settings.TMP_DIR, course_key)
        host_tmp_path = Path(settings.HOST_TMP_DIR, course_key)

        # copy the course material to a tmp folder
        if tmp_path.is_dir():
            shutil.rmtree(tmp_path)
        elif tmp_path.exists():
            tmp_path.unlink()
        shutil.copytree(path, tmp_path, symlinks=True)

        # build in tmp folder
        build_status = build(tmp_path, host_tmp_path, course_key)
        if not build_status:
            return

        # copy the course material back
        shutil.rmtree(path)
        shutil.copytree(tmp_path, path, symlinks=True)

        # link static dir
        static_dir = read_static_dir(course_key)
        if static_dir:
            build_logger.info(f"\nLinking static dir {static_dir}\n")
            src_path = Path("static", course_key)
            if src_path.exists() or src_path.is_symlink():
                src_path.unlink()
            src_path.symlink_to(Path(path, static_dir))

        # all went well
        update.status = UpdateStatus.SUCCESS
    except:
        build_logger.error("Build failed.\n")
        build_logger.error(traceback.format_exc() + "\n")
        raise
    finally:
        update.log = log_stream.getvalue()
        build_logger.removeHandler(log_handler)

        if update.status != UpdateStatus.SUCCESS:
            update.status = UpdateStatus.FAILED
        update.updated_time = Now()
        update.save()

    if update.status == UpdateStatus.SUCCESS:
        pass
        # TODO: ? reload uwsgi processes

        # TODO: let LMS know about the update
