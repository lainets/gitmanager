'''
The exercises and classes are configured in json/yaml.
Courses are listed in the database.
'''
from __future__ import annotations
import copy
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import logging
import os
import time
from typing import Any, ClassVar, Dict, Iterable, Optional, List, Tuple, Union

from django.conf import settings
from django.utils import translation
from pydantic.error_wrappers import ValidationError

from util.files import read_meta
from util.localize import DEFAULT_LANG
from util.pydantic import Undefined, validation_error_str, validation_warning_str
from util.static import static_path, symbolic_link
from builder.models import Course as CourseModel
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


class ConfigSource(Enum):
    BUILD = 0
    STORE = 1
    PUBLISH = 2


@dataclass
class CourseConfig:
    # class variables
    # variables marked ClassVar do not get a field in the dataclass
    _courses: ClassVar[Dict[str, CourseConfig]] = {}
    _dir_mtime: ClassVar[float] = 0
    # instance variables
    key: str
    dir: str
    grader_config_dir: str
    meta: dict
    file: str
    mtime: float
    ptime: float
    version_id: Optional[str]
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


    def exercise_config(self, exercise_key: str) -> Optional[ExerciseConfig]:
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
            include_ok = self._check_include_file_timestamps(exercise_root)
            try:
                if (exercise_root.mtime >= os.path.getmtime(exercise_root.file)
                        and include_ok):
                    return exercise_root
            except OSError:
                pass

        LOGGER.debug('Loading exercise "%s/%s"', self.key, exercise_key)

        exercise = self.exercises[exercise_key]

        config_file_info = exercise.config_file_info(self.dir, self.grader_config_dir)
        if config_file_info:
            self._config_obj = ExerciseConfig.load(
                exercise_key,
                *config_file_info,
                self.lang,
            )

        return exercise._config_obj

    def get_course_name(self, lang: Optional[str] = None) -> str:
        lang = lang or translation.get_language() or self.lang
        return self.data.name.get(lang[:2], self.key)

    @property
    def course_name(self) -> str:
        return self.get_course_name()

    @staticmethod
    def relative_path_to(key: str = "", *paths: str) -> str:
        """
        Returns the path of course <course_key> relative to the course root directory.
        """
        return os.path.join(key, *paths)

    @staticmethod
    def path_to(key: str = "", *paths: str, source: ConfigSource = ConfigSource.PUBLISH) -> str:
        """
        Returns the path to a file under a course.
        Leave 'key' empty to get a path relative to the root directory instead of the course directory.
        """
        relative_path = CourseConfig.relative_path_to(key, *paths)
        if source == ConfigSource.PUBLISH:
            return os.path.join(settings.COURSES_PATH, relative_path)
        elif source == ConfigSource.STORE:
            return os.path.join(settings.STORE_PATH, relative_path)
        elif source == ConfigSource.BUILD:
            return os.path.join(settings.BUILD_PATH, relative_path)
        else:
            raise ValueError(f"Unknown config source '{source}'")

    @staticmethod
    def version_id_path(root: str, key: str = "") -> str:
        return os.path.join(root, key + ".version")

    def static_path_to(self, *paths: str) -> Optional[str]:
        if self.data.static_dir is Undefined:
            return None
        return os.path.join(self.data.static_dir, *paths)

    @staticmethod
    def get_for(courses: Iterable[CourseModel]) -> Tuple[List[CourseConfig], List[str]]:
        configs = []
        errors = []
        for course in courses:
            try:
                config = CourseConfig.get(course.key, raise_on_error=True)
            except ConfigError as e:
                LOGGER.exception("Failed to load course: %s", course.key)
                errors.append(f"Failed to load course {course.key}: {str(e)}")
            except ValidationError as e:
                LOGGER.exception("Failed to load course: %s", course.key)
                LOGGER.exception(validation_error_str(e))
                errors.append(f"Failed to load course {course.key} due to a validation error")
            else:
                configs.append(config)
                warnings = validation_warning_str(config)
                if warnings:
                    LOGGER.warning("Warnings in course config: %s", course.key)
                    LOGGER.warning(warnings)
                    errors.append(f"Course {course.key} has validation warnings")

        return configs, errors

    @staticmethod
    def all(courses: Optional[Iterable[Course]] = None):
        '''
        Gets all course configs.

        @rtype: C{list}
        @return: course configurations
        '''

        # Find all courses if exercises directory is modified.
        t = os.path.getmtime(settings.COURSES_PATH)
        if CourseConfig._dir_mtime < t:
            CourseConfig._courses.clear()

            CourseConfig.get_for(CourseModel.objects.all())

            CourseConfig._dir_mtime = t

        return CourseConfig._courses.values()

    @staticmethod
    def get(course_key: str, source: ConfigSource = ConfigSource.PUBLISH, *, raise_on_error: bool = False) -> Optional[CourseConfig]:
        '''
        Gets course config.

        @type course_key: C{str}
        @param course_key: a course key
        @type raise_on_error: bool
        @param raise_on_error: whether to raise an exception or return None on error
        @return: course config or None
        '''

        # Try cached version.
        if source == ConfigSource.PUBLISH and course_key in CourseConfig._courses:
            config = CourseConfig._courses[course_key]
            try:
                if config.mtime >= os.path.getmtime(config.file):
                    return config
            except OSError:
                pass

        LOGGER.debug('Loading course "%s"' % (course_key))

        try:
            config = CourseConfig.load(course_key, source)
        except ConfigError:
            if raise_on_error:
                raise
            else:
                return None

        if source == ConfigSource.PUBLISH:
            CourseConfig._courses[course_key] = config
            if not static_path(config).exists():
                symbolic_link(config)

        return config

    @staticmethod
    def load(course_key: str, source: ConfigSource = ConfigSource.PUBLISH) -> CourseConfig:
        """Loads a course form the specified source directory"""
        return CourseConfig._load(CourseConfig.path_to(source=source), course_key)

    @staticmethod
    def _load(root_dir: str, course_key: str) -> CourseConfig:
        """Loads a course config from the given root directory"""
        course_dir = os.path.join(root_dir, course_key)

        meta = load_meta(course_dir)
        f = ConfigParser.get_config(os.path.join(CourseConfig._conf_dir(course_dir, meta), INDEX))

        t, data = ConfigParser.parse(f)
        if data is None:
            raise ConfigError('Failed to parse configuration file "%s"' % (f))
        elif not isinstance(data, dict):
            raise ConfigError(f'The configuration data is invalid. It must be a dictionary. File "{f}"')

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

        grader_config_dir = CourseConfig._conf_dir(course_dir, meta)

        course = Course.parse_obj(data)
        course.postprocess(
            course_key = course_key,
            course_dir = course_dir,
            grader_config_dir = grader_config_dir,
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

        try:
            with open(CourseConfig.version_id_path(root_dir, course_key)) as file:
                version_id = file.read()
        except:
            version_id = None

        return CourseConfig(
            key = course_key,
            dir = course_dir,
            grader_config_dir = grader_config_dir,
            meta = meta,
            file = f,
            mtime = t,
            ptime = time.time(),
            version_id = version_id,
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

    def _check_include_file_timestamps(self, exercise_config: ExerciseConfig) -> bool:
        """Check the exercise modification time against the modification timestamps
        of the included configuration templates.

        Included configuration templates are set in the data["include"] field
        (if they are used).

        @param exercise_config: the exercise ExerciseConfig
        @return: True if the exercise is up-to-date
            (not older than the latest modification in included files)
        """
        course_dir = CourseConfig._conf_dir(self.dir, self.meta)

        max_include_timestamp = 0
        for data in exercise_config.data.values():
            for include_data in data.get("include", []):
                include_file = ConfigParser.get_config(os.path.join(course_dir, include_data["file"]))
                try:
                    max_include_timestamp = max(max_include_timestamp, os.path.getmtime(include_file))
                except OSError:
                    return False
        return exercise_config.mtime >= max_include_timestamp
