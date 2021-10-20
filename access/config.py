'''
The exercises and classes are configured in json/yaml.
Courses are listed in the database.
'''
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from util.pydantic import Undefined, validation_error_str, validation_warning_str
from django.conf import settings
import os, time
import logging
from typing import Any, ClassVar, Dict, Optional, List, Tuple, Union
import copy

from pydantic.error_wrappers import ValidationError

from util.files import read_meta
from util.localize import DEFAULT_LANG
from util.static import symbolic_link
from gitmanager.models import Course as CourseModel
from .course import Course, Exercise, Parent, ExerciseConfig
from .parser import ConfigParser, ConfigError

META = "apps.meta"
INDEX = "index"

LOGGER = logging.getLogger('main')


def _type_dict(dict_item: Dict[str, Any], dict_types: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    '''
    Extends dictionary with a type reference.
    @type dict_item: C{dict}
    @param dict_item: a dictionary
    @type dict_types: C{dict}
    @param dict_types: a dictionary of type dictionaries
    @rtype: C{dict}
    @return: an extended dictionary
    '''
    # TODO: should probably throw an error if type isn't in dict_types
    if "type" not in dict_item or dict_item["type"] not in dict_types:
        return dict_item
    base = copy.deepcopy(dict_types[dict_item["type"]])
    base.update(dict_item)
    del base["type"]
    return base


def load_meta(course_dir: Union[str, Path]) -> Dict[str,str]:
    return read_meta(os.path.join(course_dir, META))


@dataclass
class CourseConfig:
    # class variables
    # variables marked ClassVar do not get a field in the dataclass
    _courses: ClassVar[Dict[str, CourseConfig]] = {}
    _dir_mtime: ClassVar[float] = 0
    # instance variables
    key: str
    dir: str
    meta: dict
    file: str
    mtime: float
    ptime: float
    data: Course
    lang: str
    exercises: Dict[str, Exercise]

    @property
    def static_dir(self) -> str:
        return os.path.join(self.dir, self.data.static_dir or "")

    def get_exercise_list(self) -> Optional[List[dict]]:
        '''
        Gets course exercises as a list.

        @rtype: C{tuple}
        @return: listed exercise configurations or None
        '''
        # Pick exercise data into list.
        exercise_list = []
        for exercise in self.exercises.values():
            data = self.exercise_data(exercise.key)
            if data is not None:
                exercise_list.append(data)
        return exercise_list


    def exercise_data(self, exercise_key: str, lang: Optional[str] = None) -> Optional[dict]:
        '''
        Gets exercise config for its key.

        @type exercise_key: C{str}
        @param exercise_key: an exercise key
        @rtype: C{tuple}
        @return: exercise configuration or None
        '''
        exercise = self.exercise_config(exercise_key)
        if exercise is None:
            return None

        return exercise.data_for_language(lang)


    def exercise_config(self, exercise_key) -> Optional[ExerciseConfig]:
        '''
        Gets exercise dictionary root (meta and data).

        @type course_root: C{dict}
        @param course_root: a course root dictionary
        @type exercise_key: C{str}
        @param exercise_key: an exercise key
        @rtype: C{dict}
        @return: exercise root or None
        '''
        if not self.exercises[exercise_key].config:
            return None

        # Try cached version.
        if exercise_key in self.exercises:
            exercise_root = self.exercises[exercise_key]._config_obj
            try:
                if exercise_root.mtime >= os.path.getmtime(exercise_root.file):
                    return exercise_root
            except OSError:
                pass

        LOGGER.debug('Loading exercise "%s/%s"', self.key, exercise_key)

        exercise = self.exercises[exercise_key]

        if exercise.config.is_absolute():
            self._config_obj = ExerciseConfig.load(
                exercise_key,
                str(exercise.config)[1:],
                CourseConfig._conf_dir(self.dir, {}),
                self.lang,
            )
        else:
            exercise._config_obj = ExerciseConfig.load(
                exercise_key,
                str(exercise.config),
                CourseConfig._conf_dir(self.dir, self.meta),
                self.lang,
            )

        return exercise._config_obj

    @staticmethod
    def path_to(key: str, *paths: str) -> str:
        return os.path.join(settings.COURSES_PATH, key, *paths)

    def static_path_to(self, *paths: str) -> Optional[str]:
        if self.data.static_dir is Undefined:
            return None
        return os.path.join(self.data.static_dir, *paths)

    @staticmethod
    def all():
        '''
        Gets all course configs.

        @rtype: C{list}
        @return: course configurations
        '''

        # Find all courses if exercises directory is modified.
        t = os.path.getmtime(settings.COURSES_PATH)
        if CourseConfig._dir_mtime < t:
            CourseConfig._courses.clear()
            CourseConfig._dir_mtime = t

            LOGGER.debug('Recreating course list.')
            for course in CourseModel.objects.all():
                try:
                    config = CourseConfig.get(course.key)
                except ConfigError:
                    LOGGER.exception("Failed to load course: %s", course.key)
                except ValidationError as e:
                    LOGGER.exception("Failed to load course: %s", course.key)
                    LOGGER.exception(validation_error_str(e))
                else:
                    warnings = validation_warning_str(config)
                    if warnings:
                        LOGGER.warning("Warnings in course config: %s", course.key)
                        LOGGER.warning(warnings)

        return CourseConfig._courses.values()


    @staticmethod
    def get(course_key: str) -> Optional[CourseConfig]:
        '''
        Gets course config.

        @type course_key: C{str}
        @param course_key: a course key
        @rtype: C{dict}
        @return: course config or None
        '''

        # Try cached version.
        if course_key in CourseConfig._courses:
            config = CourseConfig._courses[course_key]
            try:
                if config.mtime >= os.path.getmtime(config.file):
                    return config
            except OSError:
                pass

        LOGGER.debug('Loading course "%s"' % (course_key))
        course_dir = CourseConfig.path_to(course_key)

        config = CourseConfig.load(course_dir, course_key)
        if config is not None:
            CourseConfig._courses[course_key] = config
            symbolic_link(settings.COURSES_PATH, course_key, config)
        return config


    @staticmethod
    def load(course_dir: str, course_key: str = "") -> Optional["CourseConfig"]:
        """Loads course config from the given directory"""
        meta = load_meta(course_dir)
        try:
            f = ConfigParser.get_config(os.path.join(CourseConfig._conf_dir(course_dir, meta), INDEX))
        except ConfigError:
            return None

        t = os.path.getmtime(f)
        data = ConfigParser.parse(f)
        if data is None:
            raise ConfigError('Failed to parse configuration file "%s"' % (f))

        default_lang = CourseConfig._default_lang(data)

        # apply exercise_types and module_types
        # TODO: this might cause hard to debug type errors due *_types not being validated separately
        # maybe try loading the types into partial pydantic objects first?
        if "modules" in data:
            if "module_types" in data:
                for i, module in enumerate(data["modules"]):
                    data["modules"][i] = _type_dict(module, data["module_types"])

                del data["module_types"]

            if "exercise_types" in data:
                def apply_exercise_types(parent: Dict[str, Any]) -> None:
                    if "children" not in parent:
                        return
                    for i, exercise_vars in enumerate(parent["children"]):
                        if "key" in exercise_vars:
                            parent["children"][i] = _type_dict(exercise_vars, data["exercise_types"])
                        apply_exercise_types(exercise_vars)
                for module in data["modules"]:
                    apply_exercise_types(module)

                del data["exercise_types"]

        course = Course.parse_obj(data)
        course.postprocess(
            course_key = course_key,
            course_dir = CourseConfig._conf_dir(course_dir, {}),
            grader_config_dir = CourseConfig._conf_dir(course_dir, meta),
            default_lang = default_lang,
        )

        exercises: Dict[str, Exercise] = {}
        if course.modules:
            def gather_exercises(parent: Parent):
                for obj in parent.children:
                    if isinstance(obj, Exercise):
                        exercises[obj.key] = obj

                    if isinstance(obj, Parent):
                        gather_exercises(obj)
            for module in course.modules:
                gather_exercises(module)

        return CourseConfig(
            key = course_key,
            dir = course_dir,
            meta = meta,
            file = f,
            mtime = t,
            ptime = time.time(),
            data = course,
            lang = default_lang,
            exercises = exercises,
        )


    @staticmethod
    def course_and_exercise_configs(course_key: str, exercise_key: str) -> Tuple[Optional[CourseConfig], Optional[ExerciseConfig]]:
        course = CourseConfig.get(course_key)
        if course is None:
            return course, None
        exercise = course.exercise_config(exercise_key)
        return course, exercise


    @staticmethod
    def course_meta(course_key):
        # Try cached version.
        if course_key in CourseConfig._courses:
            course_root = CourseConfig._courses[course_key]
            try:
                if course_root.mtime >= os.path.getmtime(course_root.file):
                    return course_root.meta
            except OSError:
                pass

        return load_meta(CourseConfig.path_to(course_key))


    @staticmethod
    def _conf_dir(course_dir, meta):
        '''
        Gets configuration directory for the course.

        @type course_dir: C{str}
        @param course_dir: course directory
        @type meta: C{dict}
        @param meta: course meta data
        @rtype: C{str}
        @return: path to the course config directory
        '''
        if 'grader_config' in meta:
            return os.path.join(course_dir, meta['grader_config'])
        return course_dir


    @staticmethod
    def _default_lang(data):
        l = data.get('lang')
        if isinstance(l, list) and len(l) > 0:
            return l[0]
        elif isinstance(l, str):
            return l
        return DEFAULT_LANG

