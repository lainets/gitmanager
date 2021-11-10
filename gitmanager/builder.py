import importlib
from io import StringIO
import json
import logging
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import sys
import traceback
from types import ModuleType
from typing import List, Tuple
import urllib.parse

from django.conf import settings
from django.db.models.functions import Now
from huey.contrib.djhuey import db_task, lock_task
from pydantic.error_wrappers import ValidationError

from aplus_auth.payload import Permission, Permissions
from aplus_auth.requests import post

from access.config import CourseConfig, load_meta, META
from gitmanager.configure import configure_graders, publish_graders
from util.files import is_subpath, renames, rm_path, FileLock
from util.pydantic import validation_error_str, validation_warning_str
from util.static import static_url_path
from util.typing import PathLike
from .models import Course, CourseUpdate, UpdateStatus


logger = logging.getLogger("grader.gitmanager")

build_logger = logging.getLogger("gitmanager.build")
build_logger.setLevel(logging.DEBUG)


def _import_path(path: str) -> ModuleType:
    """Imports an attribute (e.g. class or function) from a module from a specified path"""
    spec = importlib.util.spec_from_file_location("builder_module", path)
    if spec is None:
        raise ImportError(f"Couldn't find {path}")

    module = importlib.util.module_from_spec(spec)
    if module is None:
        raise ImportError(f"Couldn't import {path}")
    sys.modules["builder_module"] = module
    spec.loader.exec_module(module)

    return module

build_module = _import_path(settings.BUILD_MODULE)
if not hasattr(build_module, "build"):
    raise AttributeError(f"{settings.BUILD_MODULE} does not have a build function")
if not callable(getattr(build_module, "build")):
    raise AttributeError(f"build attribute in {settings.BUILD_MODULE} is not callable")


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
        build_logger.info(output)

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


def pull(path: str, origin: str, branch: str) -> bool:
    success = False
    do_clone = True
    if Path(path, ".git"):
        if has_origin(path, origin):
            do_clone = False
            success = checkout(path, origin, branch)
        else:
            build_logger.info("Wrong origin in repo, recloning\n\n")

    if do_clone:
        rm_path(path)
        success = clone(path, origin, branch)

    if (Path(path) / ".git").exists():
        success2, logstr = git_call(path, "log", ["--no-pager", "log", '--pretty=format:------------\nCommit metadata\n\nHash:\n%H\nSubject:\n%s\nBody:\n%b\nCommitter:\n%ai\n%ae\nAuthor:\n%ci\n%cn\n%ce\n------------\n', "-1"], include_cmd_string=False)
        build_logger.info(logstr)
        return success and success2
    else:
        build_logger.info("------------\nFailed to clone repository\n------------\n\n")
        return success


def build(course: Course, path: Path) -> bool:
    meta = load_meta(path)

    build_image = settings.DEFAULT_IMAGE
    build_command = None
    if meta:
        if "build_image" in meta:
            build_image = meta["build_image"]
            build_logger.info(f"Using build image: {build_image}\n\n")
        else:
            build_logger.info(f"No build_image in {META}, using the default: {build_image}\n\n")

        if "build_command" in meta:
            build_command = meta["build_command"]
            build_logger.info(f"Using build command: {build_command}\n\n")
        elif not "build_image" in meta:
            build_command = settings.DEFAULT_CMD
            build_logger.info(f"No build_command in {META}, using the default: {build_command}\n\n")
        else:
            build_logger.info(f"No build_command in {META}, using the image default\n\n")
    else:
        build_logger.info(f"No {META} file, using the default build image: {build_image}\n\n")

    env = {
        "COURSE_KEY": course.key,
        "COURSE_ID": str(course.remote_id),
        "STATIC_URL_PATH": static_url_path(course.key),
    }

    if build_command is not None:
        build_command = shlex.split(build_command)

    return build_module.build(
        logger=build_logger,
        course_key=course.key,
        path=path,
        image=build_image,
        cmd=build_command,
        env=env,
        settings=settings.BUILD_MODULE_SETTINGS,
    )


def send_error_mail(course: Course, subject: str, message: str) -> bool:
    if course.remote_id is None:
        build_logger.error(f"Remote id not set: cannot send error email")
        return False

    email_url = urllib.parse.urljoin(settings.FRONTEND_URL, f"api/v2/courses/{course.remote_id}/send_mail/")
    permissions = Permissions()
    permissions.instances.add(Permission.WRITE, id=course.remote_id)
    data = {
        "subject": subject,
        "message": message,
    }
    try:
        response = post(email_url, permissions=permissions, data=data, headers={"Application": "application/json, application/*"})
    except:
        logger.exception(f"Failed to send email for {course.key}")
        build_logger.exception(f"Failed to send error email")
        return False

    if response.status_code != 200 or response.text:
        logger.error(f"Sending email for {course.key} failed: {response.status_code} {response.text}")
        build_logger.error(f"API failed to send the error email: {response.status_code} {response.text}")
        return False

    return True


def is_self_contained(path: PathLike) -> bool:
    spath = os.fspath(path)
    for root, _, files in os.walk(spath):
        rpath = Path(root)
        for file in files:
            if not is_subpath(str((rpath / file).resolve()), spath):
                return False

    return True


def copytree(src: PathLike, dst: PathLike) -> None:
    """
    Uses cp command to copy a directory tree in order to preserve hard- and symlinks.
    """
    process = subprocess.run(
        ["cp", "-a", os.fspath(src), os.fspath(dst)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8"
    )
    if process.returncode != 0:
        raise RuntimeError(f"Failed to copy built course files: {process.stdout}")


def store(config: CourseConfig) -> bool:
    """
    Stores the built course files and sends the configs to the graders.

    Returns False on failure and True on success.

    May raise an exception (due to FileLock timing out).
    """
    course_key = config.key

    build_logger.info("Configuring graders...")
    # send configs to graders' stores
    exercise_defaults, errors = configure_graders(config)
    if errors:
        for e in errors:
            build_logger.error(e)
        return False

    store_path = CourseConfig.store_path_to(course_key)
    store_defaults_path = CourseConfig.store_path_to(course_key + ".defaults.json")

    build_logger.info("Acquiring file lock...")
    with FileLock(store_path, timeout=settings.BUILD_FILELOCK_TIMEOUT):
        build_logger.info("File lock acquired.")

        build_logger.info("Copying the built materials")
        rm_path(store_path)
        copytree(config.dir, store_path)

        with open(store_defaults_path, "w") as f:
            json.dump(exercise_defaults, f)

    return True


def publish(course_key: str) -> List[str]:
    """
    Publishes the stored course files and tells graders to publish too.

    Returns a list of errors if something was published.

    Raises an exception if an error occurs before anything could be published.
    """
    prod_path = CourseConfig.path_to(course_key)
    prod_defaults_path = CourseConfig.path_to(course_key + ".defaults.json")
    store_path = CourseConfig.store_path_to(course_key)
    store_defaults_path = CourseConfig.store_path_to(course_key + ".defaults.json")

    config = None
    if Path(store_path).exists():
        with FileLock(store_path):
            config = CourseConfig.load(store_path, course_key)
            if config is not None:
                renames([
                    (store_path, prod_path),
                    (store_defaults_path, prod_defaults_path),
                ])

    if config is None:
        if Path(prod_path).exists():
            with FileLock(prod_path):
                config = CourseConfig.load(prod_path, course_key)

    if config is None:
        raise Exception(f"Config not found for {course_key} - the course probably has not been built")

    return publish_graders(config)


# lock_task to make sure that two updates don't happen at the same
# time. Would be better to lock it for each repo separately but it isn't really
# needed
@db_task()
@lock_task("push_event")
def push_event(
        course_key: str,
        skip_git: bool = False,
        skip_build: bool = False,
        skip_notify: bool = False,
        ) -> None:
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

    path = CourseConfig.path_to(course_key)

    log_stream = StringIO()
    log_handler = logging.StreamHandler(log_stream)
    build_logger.addHandler(log_handler)
    try:
        update.status = UpdateStatus.RUNNING
        update.save()

        build_path = CourseConfig.build_path_to(course_key)

        if not skip_git:
            if course.git_origin:
                pull_status = pull(str(build_path), course.git_origin, course.git_branch)
                if not pull_status:
                    return
            else:
                build_logger.warning(f"Course origin not set: skipping git update\n")

                # we assume that a missing git origin means local development
                # inside the course directory, thus:
                # copy the course material to the tmp folder
                rm_path(build_path)
                shutil.copytree(path, build_path, symlinks=True)
        else:
            build_logger.info("Skipping git update.")

        if not skip_build:
            # build in tmp folder
            build_status = build(course, Path(build_path))
            if not build_status:
                return
        else:
            build_logger.info("Skipping build.")

        if not is_self_contained(build_path):
            build_logger.error(f"Course {course_key} is not self contained (contains links to files outside course directory)")
            return

        # try loading the configs to validate them
        try:
            config = CourseConfig.load(str(build_path), course_key)
            if config is None:
                return
            config.get_exercise_list()
        except ValidationError as e:
            build_logger.error(validation_error_str(e))
            return

        warning_str = validation_warning_str(config)
        if warning_str:
            build_logger.warning(warning_str)

        # copy the course material to store
        if not store(config):
            build_logger.error("Failed to store built course")
            return

        # all went well
        update.status = UpdateStatus.SUCCESS
    except:
        build_logger.error("Build failed.\n")
        build_logger.error(traceback.format_exc() + "\n")
    else:
        if course.remote_id is None:
            build_logger.warning("Remote id not set. Not doing an automatic update.")
        elif skip_notify:
            build_logger.info("Skipping automatic update.")
        elif settings.FRONTEND_URL is None:
            build_logger.warning("FRONTEND_URL not set. Not doing an automatic update.")
        else:
            build_logger.info("Doing an automatic update...")
            failtext = ""
            try:
                notification_url = urllib.parse.urljoin(settings.FRONTEND_URL, f"api/v2/courses/{course.remote_id}/notify_update/")
                permissions = Permissions()
                permissions.instances.add(Permission.WRITE, id=course.remote_id)
                response = post(notification_url, permissions=permissions, data={"email_on_error": course.email_on_error}, headers={"Application": "application/json, application/*"})
                if response.status_code != 200:
                    failtext = response.reason
                elif response.text != "[]":
                    failtext = response.text
            except Exception as e:
                failtext = str(e)
                if course.email_on_error:
                    send_error_mail(
                        course,
                        f"Failed to notify update of {course_key}",
                        "Build succeeded but notifying the frontend of the update failed:\n" + failtext
                    )
            finally:
                if failtext:
                    build_logger.error("Failed:")
                    build_logger.error(failtext)
                else:
                    build_logger.info("Success.")
    finally:
        if update.status != UpdateStatus.SUCCESS:
            update.status = UpdateStatus.FAILED

            if course.email_on_error:
                send_error_mail(course, f"Course {course_key} build failed", log_stream.getvalue())

        update.log = log_stream.getvalue()
        build_logger.removeHandler(log_handler)

        update.updated_time = Now()
        update.save()
