import importlib
from io import StringIO
import logging
from pathlib import Path
import shutil
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
from util.files import rm_path
from util.pydantic import validation_error_str, validation_warning_str
from util.static import static_url_path
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


def read_static_dir(course_key: str) -> str:
    '''
    Reads static_dir from course configuration.
    '''
    config = CourseConfig.get(course_key)
    if config and config.static_dir:
        return config.static_dir
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
    if meta and "build_image" in meta:
        build_image = meta["build_image"]
        build_logger.info("Using build image: " + build_image + "\n\n")
    elif meta:
        build_logger.info(f"No build_image in {META}, using the default: {build_image}\n\n")
    else:
        build_logger.info(f"No {META} file, using the default build image: {build_image}\n\n")

    env = {
        "COURSE_KEY": course.key,
        "COURSE_ID": str(course.remote_id),
        "STATIC_URL_PATH": static_url_path(course.key),
    }

    return build_module.build(
        logger=build_logger,
        course_key=course.key,
        path=path,
        image=build_image,
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

        tmp_path = Path(settings.TMP_DIR, course_key)

        if not skip_git:
            if course.git_origin:
                pull_status = pull(str(tmp_path), course.git_origin, course.git_branch)
                if not pull_status:
                    return
            else:
                build_logger.warning(f"Course origin not set: skipping git update\n")

                # we assume that a missing git origin means local development
                # inside the course directory, thus:
                # copy the course material to the tmp folder
                rm_path(tmp_path)
                shutil.copytree(path, tmp_path, symlinks=True)
        else:
            build_logger.info("Skipping git update.")

        if not skip_build:
            # build in tmp folder
            build_status = build(course, tmp_path)
            if not build_status:
                return
        else:
            build_logger.info("Skipping build.")

        # try loading the configs to validate them
        try:
            config = CourseConfig.load(str(tmp_path))
            if config is None:
                return
            config.get_exercise_list()
        except ValidationError as e:
            build_logger.error(validation_error_str(e))
            return

        warning_str = validation_warning_str(config)
        if warning_str:
            build_logger.warning(warning_str)

        # copy the course material back
        build_logger.info("Copying the built materials")
        rm_path(path)
        shutil.copytree(tmp_path, path, symlinks=True)

        # link static dir
        static_dir = read_static_dir(course_key)
        if static_dir:
            build_logger.info(f"\nLinking static dir {static_dir}\n")
            src_path = Path("static", course_key)
            if src_path.exists() or src_path.is_symlink():
                src_path.unlink()
            src_path.symlink_to(static_dir)

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
