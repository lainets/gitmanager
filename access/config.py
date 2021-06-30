'''
The exercises and classes are configured in json/yaml.
Courses are listed in the database.
'''
from django.conf import settings
from django.template import loader as django_template_loader
import os, time, json, yaml, re
import logging
import copy

from util.dict import iterate_kvp_with_dfs, get_rst_as_html
from util.files import read_meta
from util.static import symbolic_link
from gitmanager.models import Course


META = "apps.meta"
INDEX = "index"
DEFAULT_LANG = "en"

LOGGER = logging.getLogger('main')


class ConfigError(Exception):
    '''
    Configuration errors.
    '''
    def __init__(self, value, error=None):
        self.value = value
        self.error = error

    def __str__(self):
        if self.error is not None:
            return "%s: %s" % (repr(self.value), repr(self.error))
        return repr(self.value)


class CourseConfig:
    _courses = {}
    _dir_mtime = 0


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
            for course in Course.objects.all():
                try:
                    CourseConfig._course_root(course.key)
                except ConfigError:
                    LOGGER.exception("Failed to load course: %s", course.key)
                    continue

        # Pick course data into list.
        course_list = []
        for c in CourseConfig._courses.values():
            course_list.append(c["data"])
        return course_list


    @staticmethod
    def course_entry(course_key):
        '''
        Gets a course entry.

        @type course_key: C{str}
        @param course_key: a course key
        @rtype: C{dict}
        @return: course configuration or None
        '''
        root = CourseConfig._course_root(course_key)
        return None if root is None else root["data"]


    @staticmethod
    def exercises(course_key):
        '''
        Gets course exercises for a course key.

        @type course_key: C{str}
        @param course_key: a course key
        @rtype: C{tuple}
        @return: course configuration or None, listed exercise configurations or None
        '''
        course_root = CourseConfig._course_root(course_key)
        if course_root is None:
            return (None, None)

        # Pick exercise data into list.
        exercise_list = []
        for exercise_key in course_root["data"]["exercises"]:
            _, exercise = CourseConfig.exercise_entry(course_root, exercise_key)
            if exercise is None:
                raise ConfigError('Invalid exercise key "%s" listed in "%s"'
                    % (exercise_key, course_root["file"]))
            exercise_list.append(exercise)
        return (course_root["data"], exercise_list)


    @staticmethod
    def exercise_entry(course, exercise_key, lang=None):
        '''
        Gets course and exercise entries for their keys.

        @type course: C{str|dict}
        @param course: a course key or root dict
        @type exercise_key: C{str}
        @param exercise_key: an exercise key
        @rtype: C{tuple}
        @return: course configuration or None, exercise configuration or None
        '''
        if isinstance(course, dict):
          course_root, course_key = course, course['data']['key']
        else:
          course_root, course_key = CourseConfig._course_root(course), course

        if course_root is None:
            return None, None
        if exercise_key not in course_root["data"]["exercises"]:
            return course_root["data"], None

        exercise_root = CourseConfig._exercise_root(course_root, exercise_key)
        if not exercise_root or "data" not in exercise_root or not exercise_root["data"]:
            return course_root["data"], None

        if lang == '_root':
            return course_root["data"], exercise_root["data"]

        # Try to find version for requested or configured language.
        for lang in (lang, course_root["lang"]):
            if lang in exercise_root["data"]:
                exercise = exercise_root["data"][lang]
                exercise["lang"] = lang
                return course_root["data"], exercise

        # Fallback to any existing language version.
        return course_root["data"], list(exercise_root["data"].values())[0]


    @staticmethod
    def course_meta(course_key):
        # Try cached version.
        if course_key in CourseConfig._courses:
            course_root = CourseConfig._courses[course_key]
            try:
                if course_root["mtime"] >= os.path.getmtime(course_root["file"]):
                    return course_root["course_meta"]
            except OSError:
                pass

        return read_meta(os.path.join(Course.path_to(course_key), META))


    @staticmethod
    def _course_root(course_key):
        '''
        Gets course dictionary root (meta and data).

        @type course_key: C{str}
        @param course_key: a course key
        @rtype: C{dict}
        @return: course root or None
        '''

        # Try cached version.
        if course_key in CourseConfig._courses:
            course_root = CourseConfig._courses[course_key]
            try:
                if course_root["mtime"] >= os.path.getmtime(course_root["file"]):
                    return course_root
            except OSError:
                pass

        LOGGER.debug('Loading course "%s"' % (course_key))
        meta = CourseConfig.course_meta(course_key)
        try:
            f = ConfigParser.get_config(os.path.join(CourseConfig._conf_dir(course_key, meta), INDEX))
        except ConfigError:
            return None

        t = os.path.getmtime(f)
        data = ConfigParser.parse(f)
        if data is None:
            raise ConfigError('Failed to parse configuration file "%s"' % (f))

        ConfigParser.check_fields(f, data, ["name"])
        data["key"] = course_key
        data["mtime"] = t
        data["dir"] = Course.path_to(course_key)

        if "static_url" not in data:
            data["static_url"] = "{}{}{}/".format(
                settings.STATIC_URL_HOST_INJECT,
                settings.STATIC_URL,
                course_key
            )

        if "modules" in data:
            keys = []
            config = {}
            def recurse_exercises(parent):
                if "children" in parent:
                    for exercise_vars in parent["children"]:
                        if "key" in exercise_vars:
                            exercise_key = str(exercise_vars["key"])
                            cfg = None
                            if "config" in exercise_vars:
                                cfg = exercise_vars["config"]
                            elif "type" in exercise_vars and "exercise_types" in data \
                                    and exercise_vars["type"] in data["exercise_types"] \
                                    and "config" in data["exercise_types"][exercise_vars["type"]]:
                                cfg = data["exercise_types"][exercise_vars["type"]]["config"]
                            if cfg:
                                keys.append(exercise_key)
                                config[exercise_key] = cfg
                        recurse_exercises(exercise_vars)
            for module in data["modules"]:
                recurse_exercises(module)
            data["exercises"] = keys
            data["config_files"] = config

        CourseConfig._courses[course_key] = course_root = {
            "meta": meta,
            "file": f,
            "mtime": t,
            "ptime": time.time(),
            "data": data,
            "lang": CourseConfig._default_lang(data),
            "exercises": {}
        }
        symbolic_link(settings.COURSES_PATH, data)
        return course_root


    @staticmethod
    def _exercise_root(course_root, exercise_key):
        '''
        Gets exercise dictionary root (meta and data).

        @type course_root: C{dict}
        @param course_root: a course root dictionary
        @type exercise_key: C{str}
        @param exercise_key: an exercise key
        @rtype: C{dict}
        @return: exercise root or None
        '''

        # Try cached version.
        if exercise_key in course_root["exercises"]:
            exercise_root = course_root["exercises"][exercise_key]
            try:
                if exercise_root["mtime"] >= os.path.getmtime(exercise_root["file"]):
                    return exercise_root
            except OSError:
                pass

        LOGGER.debug('Loading exercise "%s/%s"', course_root["data"]["key"], exercise_key)
        file_name = exercise_key
        if "config_files" in course_root["data"]:
            file_name = course_root["data"]["config_files"].get(exercise_key, exercise_key)
        if file_name.startswith("/"):
            f, t, data = CourseConfig.load_exercise(
                file_name[1:],
                CourseConfig._conf_dir(course_root["data"]["key"], {})
            )
        else:
            f, t, data = CourseConfig.load_exercise(
                file_name,
                CourseConfig._conf_dir(course_root["data"]["key"], course_root["meta"])
            )
        if not data:
            return None

        # Process key modifiers and create language versions of the data.
        data = ConfigParser.process_tags(data, course_root['lang'])
        for version in data.values():
            ConfigParser.check_fields(f, version, ["title", "view_type"])
            version["key"] = exercise_key
            version["mtime"] = t

        course_root["exercises"][exercise_key] = exercise_root = {
            "file": f,
            "mtime": t,
            "ptime": time.time(),
            "data": data
        }
        return exercise_root


    @staticmethod
    def _conf_dir(course_key, meta):
        '''
        Gets configuration directory for the course.

        @type course_key: C{str}
        @param course_key: course key
        @type meta: C{dict}
        @param meta: course meta data
        @rtype: C{str}
        @return: path to the course config directory
        '''
        if 'grader_config' in meta:
            return os.path.join(Course.path_to(course_key), meta['grader_config'])
        return Course.path_to(course_key)


    @staticmethod
    def _default_lang(data):
        l = data.get('language')
        if type(l) == list:
            data['lang'] = l[0]
        elif l == str:
            data['lang'] = l
        return data.get('lang', DEFAULT_LANG)

    @staticmethod
    def load_exercise(exercise_key, course_dir):
        '''
        Default loader to find and parse file.

        @type course_root: C{dict}
        @param course_root: a course root dictionary
        @type exercise_key: C{str}
        @param exercise_key: an exercise key
        @type course_dir: C{str}
        @param course_dir: a path to the course root directory
        @rtype: C{str}, C{dict}
        @return: exercise config file path, modified time and data dict
        '''
        config_file = ConfigParser.get_config(os.path.join(course_dir, exercise_key))
        data = ConfigParser.parse(config_file)
        if "include" in data:
            data = ConfigParser._include(data, config_file, course_dir)
        return config_file, os.path.getmtime(config_file), data


class ConfigParser:
    '''
    Provides configuration data parsed and automatically updated on change.
    '''
    FORMATS = {
        'json': json.load,
        'yaml': yaml.safe_load
    }
    PROCESSOR_TAG_REGEX = re.compile(r'^(.+)\|(\w+)$')
    TAG_PROCESSOR_DICT = {
        'i18n': lambda root, parent, value, **kwargs: value.get(kwargs['lang']),
        'rst': lambda root, parent, value, **kwargs: get_rst_as_html(value),
    }


    @staticmethod
    def check_fields(file_name, data, field_names):
        '''
        Verifies that a given dict contains a set of keys.

        @type file_name: C{str}
        @param file_name: a file name for targeted error message
        @type data: C{dict}
        @param data: a configuration entry
        @type field_names: C{tuple}
        @param field_names: required field names
        '''
        for name in field_names:
            if name not in data:
                raise ConfigError('Required field "%s" missing from "%s"' % (name, file_name))


    @staticmethod
    def get_config(path):
        '''
        Returns the full path to the config file identified by a path.

        @type path: C{str}
        @param path: a path to a config file, possibly without a suffix
        @rtype: C{str}
        @return: the full path to the corresponding config file
        @raises ConfigError: if multiple rivalling configs or none exist
        '''

        # Check for complete path.
        if os.path.isfile(path):
            ext = os.path.splitext(path)[1]
            if len(ext) > 0 and ext[1:] in ConfigParser.FORMATS:
                return path

        # Try supported format extensions.
        config_file = None
        if os.path.isdir(os.path.dirname(path)):
            for ext in ConfigParser.FORMATS.keys():
                f = "%s.%s" % (path, ext)
                if os.path.isfile(f):
                    if config_file != None:
                        raise ConfigError('Multiple config files for "%s"' % (path))
                    config_file = f
        if not config_file:
            raise ConfigError('No supported config at "%s"' % (path))
        return config_file


    @staticmethod
    def parse(path, loader=None):
        '''
        Parses a dict from a file.

        @type path: C{str}
        @param path: a path to a file
        @type loader: C{function}
        @param loader: a configuration file stream parser
        @rtype: C{dict}
        @return: an object representing the configuration file or None
        '''
        if not loader:
            try:
                loader = ConfigParser.FORMATS[os.path.splitext(path)[1][1:]]
            except:
                raise ConfigError('Unsupported format "%s"' % (path))
        data = None
        with open(path) as f:
            try:
                data = loader(f)
            except ValueError as e:
                raise ConfigError("Configuration error in %s" % (path), e)
        return data


    @staticmethod
    def _include(data, target_file, course_dir):
        '''
        Includes the config files defined in data["include"] into data.

        @type data: C{dict}
        @param data: target dict to which new data is included
        @type target_file: C{str}
        @param target_file: path to the include target, for error messages only
        @type course_dir: C{str}
        @param course_dir: a path to the course root directory
        @rtype: C{dict}
        @return: updated data
        '''
        return_data = data.copy()

        for include_data in data["include"]:
            ConfigParser.check_fields(target_file, include_data, ("file",))

            include_file = ConfigParser.get_config(os.path.join(course_dir, include_data["file"]))
            loader = ConfigParser.FORMATS[os.path.splitext(include_file)[1][1:]]

            if "template_context" in include_data:
                # Load new data from rendered include file string
                render_context = include_data["template_context"]
                template_name = os.path.join(course_dir, include_file)
                template_name = template_name[len(settings.COURSES_PATH)+1:] # FIXME: XXX: NOTE: TODO: Fix this hack
                rendered = django_template_loader.render_to_string(
                            template_name,
                            render_context
                           )
                new_data = loader(rendered)
            else:
                # Load new data directly from the include file
                new_data = loader(include_file)

            if "force" in include_data and include_data["force"]:
                return_data.update(new_data)
            else:
                for new_key, new_value in new_data.items():
                    if new_key not in return_data:
                        return_data[new_key] = new_value
                    else:
                        raise ConfigError(
                            "Key {0!r} with value {1!r} already exists in config file {2!r}, cannot overwrite with key {0!r} with value {3!r} from config file {4!r}, unless 'force' option of the 'include' key is set to True."
                            .format(
                                new_key,
                                return_data[new_key],
                                target_file,
                                new_value,
                                include_file))
        return return_data


    @staticmethod
    def process_tags(data, default_lang = DEFAULT_LANG):
        '''
        Processes a data dictionary according to embedded processor flags
        and creates a data dict version for each language intercepted.

        @type data: C{dict}
        @param data: a config data dictionary to process (in-place)
        @type default_lang: str
        @param default_lang: the default language
        '''
        lang_keys = []
        tags_processed = []

        def recursion(n, lang, collect_lang=False):
            t = type(n)
            if t == dict:
                d = {}
                for k in sorted(n.keys(), key=lambda x: (len(x), x)):
                    v = n[k]
                    m = ConfigParser.PROCESSOR_TAG_REGEX.match(k)
                    while m:
                        k, tag = m.groups()
                        tags_processed.append(tag)
                        if collect_lang and tag == 'i18n' and type(v) == dict:
                            lang_keys.extend(v.keys())
                        if tag not in ConfigParser.TAG_PROCESSOR_DICT:
                            raise ConfigError('Unsupported processor tag "%s"' % (tag))
                        v = ConfigParser.TAG_PROCESSOR_DICT[tag](d, n, v, lang=lang)
                        m = ConfigParser.PROCESSOR_TAG_REGEX.match(k)
                    d[k] = recursion(v, lang, collect_lang)
                return d
            elif t == list:
                return [recursion(v, lang, collect_lang) for v in n]
            else:
                return n

        default = recursion(data, default_lang, True)
        root = { default_lang: default }
        for lang in (set(lang_keys) - set([default_lang])):
            root[lang] = recursion(data, lang)

        LOGGER.debug('Processed %d tags.', len(tags_processed))
        return root

