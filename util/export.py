from typing import Any, Dict, Tuple, cast
from util.static import static_url_path
from access.config import CourseConfig, ExerciseConfig
from itertools import zip_longest
import urllib.parse

from django.http import HttpRequest
from django.urls import reverse


def url_to_model(request: HttpRequest, course_key: str, exercise_key: str, parameter: str):
    return request.build_absolute_uri(
        reverse('model', args=[course_key, exercise_key, parameter])
    )


def url_to_template(request: HttpRequest, course_key: str, exercise_key: str, parameter: str):
    return request.build_absolute_uri(
        reverse('exercise_template', args=[course_key, exercise_key, parameter])
    )


def url_to_static(request: HttpRequest, course_key: str, path: str) -> str:
    ''' Creates an URL for a path in static files '''
    return request.build_absolute_uri(static_url_path(course_key, path))


def chapter(request: HttpRequest, course: CourseConfig, of: Dict[str, Any]) -> Dict[str, Any]:
    ''' Exports chapter data '''
    path = of.pop('static_content')
    if type(path) == dict:
        of['url'] = {
            lang: url_to_static(request, course.key, p)
            for lang,p in path.items()
        }
    else:
        of['url'] = url_to_static(request, course.key, path)
    return of


def exercise(
        request: HttpRequest,
        course: CourseConfig,
        exercise_root: ExerciseConfig,
        of: Dict[str, Any]
        ) -> Dict[str, Any]:
    """
    Exports exercise data.

    Note! The a-plus json syntax only supports identical exercises apart from
    translations. At the time of writing, mooc-grader does not enforce such
    design and configuration can be written that produces totally different
    exercise types per language. In this export, only the exercise details
    from the default language are exported along with any translations that
    match the exercise structure in other languages.
    """
    of.pop('config')
    of.pop('configure', None)
    languages,exercises = zip(*exercise_root.data.items())
    languages,exercises = cast(Tuple[Tuple[str,...],Tuple[Dict[str, Any],...]], (languages,exercises))
    exercise = exercises[0]

    if not 'title' in of and not 'name' in of:
        of['title'] = i18n_get(languages, exercises, 'title')
    if not 'description' in of:
        of['description'] = exercise.get('description', '')
    if 'url' in exercise:
        of['url'] = exercise['url']

    if 'exercise_info' in exercise:
        of['exercise_info'] = exercise['exercise_info']
    else:
        # DEPRECATED: exercise_info should already have the required data
        # it is not gitmanager's job to fill it
        form, i18n = form_fields(languages, exercises)
        of['exercise_info'] = {
            'form_spec': form,
            'form_i18n': i18n,
        }

        if 'radar_info' in exercise:
            of['exercise_info']['radar'] = exercise['radar_info']

    if 'model_answer' in exercise:
        of['model_answer'] = exercise['model_answer']
    elif 'model_files' in exercise:
        of['model_answer'] = i18n_urls(
            languages, exercises, 'model_files',
            url_to_model, request, course.key, exercise['key']
        )
    elif exercise.get('view_type', None) == 'access.types.stdsync.createForm':
        # DEPRECATED: model_answer should already have the required data it is
        # not gitmanager's job to know what 'access.types.stdsync.createForm' is

        # build an url to the grader
        if 'url' in of:
            parsed_exercise_url = urllib.parse.urlparse(of['url'])
            model_url = url_to_model(
                request, course.key, exercise['key'], ''
            )
            model_url = urllib.parse.urlparse(model_url)._replace(
                    scheme=parsed_exercise_url.scheme,
                    netloc=parsed_exercise_url.netloc
                ).geturl()
        else:
            model_url = ''

        if not model_url:
            of['model_answer'] = ''
        elif not exercise.get('show_model_answer', True):
            # Set the empty string here so that an existing value may be
            # removed from the A+ database when the course is imported there.
            of['model_answer'] = ''
        elif len(languages) == 1:
            of['model_answer'] = model_url
        else:
            of['model_answer'] = {
                l: model_url + '?lang=' + l
                for i,l in enumerate(languages)
            }

    if 'exercise_template' in exercise:
        of['exercise_template'] = exercise['exercise_template']
    elif 'template_files' in exercise:
        of['exercise_template'] = i18n_urls(
            languages, exercises, 'template_files',
            url_to_template, request, course.key, exercise['key']
        )

    return of


def form_fields(languages, exercises):
    ''' Describes a form that the configured exercise produces '''

    form = []
    i18n = {}

    def i18n_map(values):
        if all(v == "" for v in values):
            return ""
        key = str(values[0])
        if key in values[1:]:
            key = "i18n_" + "_".join(key.split())
        while key in i18n:
            key += "_duplicate"
        i18n[key] = {
            l: v
            for l,v in zip(languages, values)
        }
        return key

    def field_spec(fs, n):
        f = fs[0]
        field = {
            'key': f.get('key', 'field_' + str(n)),
            'type': f.get('type'),
            'title': i18n_map(list_get(fs, 'title', '')),
            'required': f.get('required', False),
        }

        mods = f.get('compare_method', '').split('-')
        if 'int' in mods:
            field['type'] = 'number'
        elif 'float' in mods:
            field['type'] = 'number'
        # Regexp does not validate input but checks the correct answer.
        #elif 'regexp' in mods:
        #    field['pattern'] = f.get('correct')

        if 'more' in f:
            field['description'] = i18n_map(list_get(fs, 'more', ''))

        if 'options' in f:
            titleMap = {}
            enum = []
            m = 0
            for os in list_enumerate(list_get(fs, 'options', []), {}):
                v = os[0].get('value', 'option_' + str(m))
                titleMap[v] = i18n_map(list_get(os, 'label', ''))
                enum.append(v)
                m += 1
            field['titleMap'] = titleMap
            field['enum'] = enum

        if 'extra_info' in f:
            es = list_get(fs, 'extra_info', {})
            extra = es[0]
            for key in ['validationMessage']:
                if key in extra:
                    extra[key] = i18n_map(list_get(es, key, ''))
            field.update(extra)

        if 'class' in field:
            field['htmlClass'] = field['class']
            del(field['class'])

        return field

    t = exercises[0].get('view_type', None)
    if t == 'access.types.stdsync.createForm':
        n = 0
        for fgs in list_enumerate(list_get(exercises, 'fieldgroups', []), {}):
            for fs in list_enumerate(list_get(fgs, 'fields', []), {}):
                t = fs[0].get('type', None)

                if t == 'table-radio' or t == 'table-checkbox':
                    for rows in list_enumerate(list_get(fs, 'rows', []), {}):
                        rfs = [f.copy() for f in fs]
                        for i,rf in enumerate(rfs):
                            row = rows[i]
                            rf['type'] = t[6:]
                            if 'key' in row:
                                rf['key'] = row['key']
                            if 'label' in row:
                                rf['title'] += ': ' + row['label']
                        form.append(field_spec(rfs, n))
                        n += 1

                        rf = rfs[0]
                        if 'more_text' in rf:
                            form.append({
                                'key': rf.get('key', 'field_' + str(n)) + '_more',
                                'type': 'text',
                                'title': i18n_map(list_get(rfs, 'more_text', '')),
                                'required': False,
                            })
                            n += 1
                else:
                    form.append(field_spec(fs, n))
                    n += 1

    elif t == 'access.types.stdasync.acceptPost':
        for fs in list_enumerate(list_get(exercises, 'fields', []), {}):
            f = fs[0]
            form.append({
                'key': f.get('name'),
                'type': 'textarea',
                'title': i18n_map(list_get(fs, 'title', '')),
                'requred': f.get('required', False),
            })

    elif t == 'access.types.stdasync.acceptFiles':
        for fs in list_enumerate(list_get(exercises, 'files', []), {}):
            f = fs[0]
            form.append({
                'key': f.get('field'),
                'type': 'file',
                'title': i18n_map(list_get(fs, 'name', '')),
                'required': f.get('required', True),
            })

    return form, i18n


def i18n_get(languages, values, key):
    if len(languages) == 1:
        return values[0].get(key)
    return {
        l: values[i].get(key)
        for i,l in enumerate(languages)
    }


def i18n_urls(languages, values, key, mapper, request, course_key, exercise_key):
    def urls(paths, lang=None):
        return ' '.join([
            mapper(request, course_key, exercise_key, path.split('/')[-1]) +
            ('?lang='+lang if lang else '')
            for path in paths
        ])
    if len(languages) == 1:
        return urls(values[0].get(key, []))
    return {
        l: urls(values[i].get(key, []), lang=l)
        for i,l in enumerate(languages)
    }


def list_get(dicts, key, default):
    return [
        d.get(key, default)
        for d in dicts
    ]


def list_enumerate(lists, default):
    return zip_longest(*lists, fillvalue=default)
