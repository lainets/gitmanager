# -*- coding: utf-8 -*-
'''
This module holds unit tests.
'''
import copy
import os
import time
import tempfile

from django.conf import settings
from django.test import TestCase, override_settings

from access.config import CourseConfig
from access.parser import ConfigParser
from builder.models import Course as CourseModel
from util.files import rm_path


@override_settings(
    COURSES_PATH=os.path.abspath(os.path.join(settings.TESTDATADIR, "build")),
    # Set static root to a tmp dir so it wont affect anything, and we can easily delete it afterwards
    STATIC_ROOT=tempfile.mkdtemp(prefix="static_root_test", dir=settings.TESTDATADIR),
)
class ConfigTestCase(TestCase):

    TEST_DATA = {
        'key': 'value',
        'title|i18n': {'en': 'A Title', 'fi': 'Eräs otsikko'},
        'text|rst': 'Some **fancy** text with ``links <http://google.com>`` and code like ``echo "moi"``.',
        'nested': {
            'number|i18n': {'en': 1, 'fi': 2},
            'another': 10
        }
    }

    def setUp(self):
        self.course = CourseModel.objects.create(
            key='test_course',
            email_on_error=False,
            update_automatically=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        # Remove the temporary static root
        rm_path(settings.STATIC_ROOT)
        return super().tearDownClass()

    def get_course_key(self):
        course_configs, errors = CourseConfig.all()
        self.assertGreater(len(course_configs), 0, "No courses configured")
        return course_configs[0].key

    def test_rst_parsing(self):
        from access.parser import get_rst_as_html
        self.assertEqual(get_rst_as_html('A **foobar**.'), '<p>A <strong>foobar</strong>.</p>\n')

    def test_parsing(self):
        data = copy.deepcopy(self.TEST_DATA)
        data = ConfigParser.process_tags(data, 'en')
        self.assertEqual(data["en"]["text"], data["fi"]["text"])
        self.assertEqual(data["en"]["title"], "A Title")
        self.assertEqual(data["en"]["nested"]["number"], 1)
        self.assertEqual(data["fi"]["title"], "Eräs otsikko")
        self.assertEqual(data["fi"]["nested"]["number"], 2)

    def test_cache(self):
        course_key = self.get_course_key()

        root = CourseConfig.get(course_key)
        mtime = root.mtime
        ptime = root.ptime
        self.assertGreater(ptime, mtime)

        # Ptime changes if cache is missed.
        root = CourseConfig.get(course_key)
        self.assertEqual(root.mtime, mtime)
        self.assertEqual(root.ptime, ptime)

    def test_cache_reload(self):
        course_key = self.get_course_key()

        root = CourseConfig.get(course_key)
        mtime = root.mtime
        ptime = root.ptime
        self.assertGreater(ptime, mtime)

        time.sleep(0.01)
        os.utime(root.file)
        root = CourseConfig.get(course_key)
        self.assertGreater(root.ptime, root.mtime)
        self.assertGreater(root.mtime, mtime)
        self.assertGreater(root.ptime, ptime)
