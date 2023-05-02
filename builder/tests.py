from inspect import FullArgSpec, getfullargspec
import os.path
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch
import urllib.parse

from django.conf import settings
from django.test import TestCase, override_settings

from .builder import build_course, build_module
from .models import Course, CourseUpdate
from access.config import CourseConfig, ConfigSource
from util.git import get_diff_names
from util.files import rm_path


test_course_commits = [
    "f8f13733b97cbf321c67566d2aaa9a7e27fd45e7",
    "b1a4eee5904dc5c3e4c695126a84aa4b336f83eb",
    "53dd20510ce986ac7adfc79784350392b5120878",
    "06a47655bfa6029af6b6484026381fc61872b0db",
]


def get_args(argspec: FullArgSpec, mock: Mock, index: int = -1):
    args = dict(zip(reversed(argspec.args), reversed(argspec.defaults or [])))
    args.update(dict(zip(argspec.args, mock.call_args_list[-1].args)))
    args.update(mock.call_args_list[index].kwargs)

    return args


@override_settings(
    BUILD_PATH=os.path.abspath(os.path.join(settings.TESTDATADIR, "build")),
    STORE_PATH=os.path.abspath(os.path.join(settings.TESTDATADIR, "store")),
    GIT_OPTIONS=["--git-dir", "dotgit"],
    STATIC_CONTENT_HOST="http://example.com",
)
class BuildTest(TestCase):
    def setUp(self):
        self.course_key = "test_course"
        self.course = Course(
            key=self.course_key,
            git_origin="dummyurl",
        )
        self.course.save()

        for path in (settings.BUILD_PATH, settings.STORE_PATH):
            if not os.path.exists(path):
                os.mkdir(path)

    def tearDown(self) -> None:
        self.course.delete()
        rm_path(CourseConfig.version_id_path(self.course_key, source=ConfigSource.BUILD))

    def test_changed_files(self) -> None:
        build_dir = CourseConfig.path_to(self.course_key, source=ConfigSource.BUILD)
        static_url_path = os.path.join(settings.STATIC_URL, self.course_key)

        build_argspec = getfullargspec(build_module.build)

        with patch("builder.builder.build_module.build") as build_mock, \
                patch("builder.builder.checkout") as checkout_mock, \
                patch("builder.builder.clean") as clean_mock, \
                patch("builder.builder.configure_graders") as configure_mock:

            build_mock.return_value = True
            checkout_mock.return_value = True
            clean_mock.return_value = True
            configure_mock.return_value = ({}, [])


            update = self.build_course()
            self.assertEqual(update.status, CourseUpdate.Status.SUCCESS)
            self.assertEqual(update.commit_hash, test_course_commits[-1])

            expected_build_args = {
                "course_key": self.course_key,
                "path": Path(build_dir),
                "image": "testimage",
                "cmd": ["testcommand"],
                "env": {
                    "COURSE_KEY": self.course_key,
                    "COURSE_ID": "None",
                    "STATIC_URL_PATH": static_url_path,
                    "STATIC_CONTENT_HOST": urllib.parse.urljoin(settings.STATIC_CONTENT_HOST, static_url_path),
                    "CHANGED_FILES": {"*"},
                },
                "settings": settings.BUILD_MODULE_SETTINGS,
            }
            self.assert_args(expected_build_args, get_args(build_argspec, build_mock))


            CourseUpdate(
                course=self.course,
                request_ip="0.0.0.0",
                status=CourseUpdate.Status.SUCCESS,
                commit_hash=test_course_commits[0],
            ).save()

            CourseUpdate(
                course=self.course,
                request_ip="0.0.0.0",
                status=CourseUpdate.Status.FAILED,
                commit_hash=test_course_commits[1],
            ).save()

            update = self.build_course()
            self.assertEqual(update.status, CourseUpdate.Status.SUCCESS)
            self.assertEqual(update.commit_hash, test_course_commits[-1])

            expected_build_args["env"]["CHANGED_FILES"] = {"index.yaml", "apps.meta"}
            self.assert_args(expected_build_args, get_args(build_argspec, build_mock))

    def build_course(self, *args, **kwargs) -> CourseUpdate:
        update = CourseUpdate(
            course=self.course,
            request_ip="0.0.0.0",
            status=CourseUpdate.Status.PENDING,
        )
        update.save()
        build_course(self.course_key, *args, **kwargs)

        update.refresh_from_db()
        return update

    def assert_args(self, expected: Dict[str, Any], args: Dict[str, Any]):
        """Check that args is a subdict of expected"""
        for k,v in expected.items():
            self.assertTrue(k in args)
            if isinstance(v, dict):
                self.assert_args(v, args[k])
            elif k == "CHANGED_FILES":
                self.assertEqual(v, {f for f in args[k].split("\n") if f}, f"k = {k}")
            else:
                self.assertEqual(v, args[k], f"k = {k}")
