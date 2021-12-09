import io
import json
import logging
import os
import re
from typing import Callable, Dict, Optional, Tuple
from django.template.context import Context
import yaml

from django.template import Template
from django.template.exceptions import TemplateDoesNotExist, TemplateSyntaxError

from util.dict import get_rst_as_html
from util.localize import DEFAULT_LANG


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


class ConfigParser:
    '''
    Provides configuration data parsed and automatically updated on change.
    '''
    FORMATS: Dict[str, Callable] = {
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
    def parse(path: str, loader: Optional[Callable] = None) -> Tuple[float, dict]:
        '''
        Parses a dict from a file.

        @type path: C{str}
        @param path: a path to a file
        @type loader: C{function}
        @param loader: a configuration file stream parser
        @rtype: C{dict}
        @return: mtime of the file and an object representing the configuration file or None
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
            except (ValueError, yaml.YAMLError) as e:
                raise ConfigError("Configuration error in %s" % (path), e)
        return os.path.getmtime(path), data


    @staticmethod
    def _include(data: dict, target_file: str, course_dir: str) -> Tuple[float, dict]:
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
        include_data_list = data.get("include")
        if not isinstance(include_data_list, list):
            raise ConfigError(
                f'The value of the "include" field in the file "{target_file}" should be a list of dictionaries.',
            )

        mtime = 0.0
        for include_data in include_data_list:
            try:
                ConfigParser.check_fields(target_file, include_data, ("file",))

                include_file = ConfigParser.get_config(os.path.join(course_dir, include_data["file"]))
                loader = ConfigParser.FORMATS[os.path.splitext(include_file)[1][1:]]

                mtime = max(mtime, os.path.getmtime(include_file))

                if "template_context" in include_data:
                    # Load new data from rendered include file string
                    if not isinstance(include_data["template_context"], dict):
                        raise ConfigError(f"template_context must be a dict in file {target_file}")

                    render_context = Context(include_data["template_context"])
                    with open(include_file) as f:
                        template = Template(f.read())
                    rendered = template.render(Context(render_context))
                    new_data = loader(io.StringIO(rendered))
                else:
                    # Load new data directly from the include file
                    with open(include_file, 'r') as f:
                        new_data = loader(f)
            except (OSError, KeyError, ValueError, yaml.YAMLError, TemplateDoesNotExist, TemplateSyntaxError) as e:
                raise ConfigError(
                    f'Error in parsing the config file to be included into "{target_file}".', error=e,
                ) from e

            if not new_data:
                raise ConfigError(f'Included config file is empty: "{target_file}"')
            if not isinstance(new_data, dict):
                raise ConfigError(f'Included config is not of type dict: "{target_file}"')

            if include_data.get('force', False):
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

        return mtime, return_data


    @staticmethod
    def process_tags(data: dict, default_lang: str = DEFAULT_LANG) -> Dict[str, dict]:
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
            if isinstance(n, dict):
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
            elif isinstance(n, list):
                return [recursion(v, lang, collect_lang) for v in n]
            else:
                return n

        default = recursion(data, default_lang, True)
        root = { default_lang: default }
        for lang in (set(lang_keys) - set([default_lang])):
            root[lang] = recursion(data, lang)

        LOGGER.debug('Processed %d tags.', len(tags_processed))
        return root # type: ignore
