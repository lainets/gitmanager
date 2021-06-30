from django.shortcuts import render
from django.http.response import HttpResponse, JsonResponse, Http404
from django.utils import translation
from django.urls import reverse
import copy
import os

from access.config import CourseConfig as config
from util import export


def index(request):
    '''
    Signals that the grader is ready and lists available courses.
    '''
    course_configs = config.all()
    if request.is_ajax():
        return JsonResponse({
            "ready": True,
            "courses": _filter_fields(course_configs, ["key", "name"])
        })
    return render(request, 'access/ready.html', {
        "courses": course_configs,
    })


def course(request, course_key):
    '''
    Signals that the course is ready to be graded and lists available exercises.
    '''
    (course, exercises) = config.exercises(course_key)
    if course is None:
        raise Http404()
    if request.is_ajax():
        return JsonResponse({
            "ready": True,
            "course_name": course["name"],
            "exercises": _filter_fields(exercises, ["key", "title"]),
        })
    render_context = {
        'course': course,
        'exercises': exercises,
        'plus_config_url': request.build_absolute_uri(reverse(
            'aplus-json', args=[course['key']])),
    }

    render_context["build_log_url"] = request.build_absolute_uri(reverse("build-log-json", args=(course_key, )))
    return render(request, 'access/course.html', render_context)


def exercise_model(request, course_key, exercise_key, parameter):
    '''
    Presents a model answer for an exercise.
    '''
    lang = request.GET.get('lang', None)
    (course, exercise, lang) = _get_course_exercise_lang(course_key, exercise_key, lang)

    path = None

    if 'model_files' in exercise:
        def find_name(paths, name):
            models = [(path,path.split('/')[-1]) for path in paths]
            for path,name in models:
                if name == parameter:
                    return path
            return None
        path = find_name(exercise['model_files'], parameter)

    if path:
        try:
            with open(os.path.join(course['dir'], path)) as f:
                content = f.read()
        except FileNotFoundError as error:
            raise Http404("Model file missing") from error
        else:
            return HttpResponse(content, content_type='text/plain')

    raise Http404()


def exercise_template(request, course_key, exercise_key, parameter):
    '''
    Presents the exercise template.
    '''
    lang = request.GET.get('lang', None)
    (course, exercise, lang) = _get_course_exercise_lang(course_key, exercise_key, lang)

    path = None

    if 'template_files' in exercise:
        def find_name(paths, name):
            templates = [(path,path.split('/')[-1]) for path in paths]
            for path,name in templates:
                if name == parameter:
                    return path
            return None
        path = find_name(exercise['template_files'], parameter)

    if path:
        try:
            with open(os.path.join(course['dir'], path)) as f:
                content = f.read()
        except FileNotFoundError as error:
            raise Http404("Template file missing") from error
        return HttpResponse(content, content_type='text/plain')

    raise Http404()


def aplus_json(request, course_key):
    '''
    Delivers the configuration as JSON for A+.
    '''
    course = config.course_entry(course_key)
    if course is None:
        raise Http404()
    data = _copy_fields(course, [
        "archive_time",
        "assistants",
        "categories",
        "contact",
        "content_numbering",
        "course_description",
        "course_footer",
        "description",
        "end",
        "enrollment_audience",
        "enrollment_end",
        "enrollment_start",
        "head_urls",
        "index_mode",
        "lang",
        "lifesupport_time",
        "module_numbering",
        "name",
        "numerate_ignoring_modules",
        "start",
        "view_content_to",
    ])
    if "language" in course:
        data["lang"] = course["language"]

    def children_recursion(parent):
        if not "children" in parent:
            return []
        result = []
        for o in [o for o in parent["children"] if "key" in o]:
            of = _type_dict(o, course.get("exercise_types", {}))
            if "config" in of:
                _, exercise = config.exercise_entry(course["key"], str(of["key"]), '_root')
                of = export.exercise(request, course, exercise, of)
            elif "static_content" in of:
                of = export.chapter(request, course, of)
            of["children"] = children_recursion(o)
            result.append(of)
        return result

    modules = []
    if "modules" in course:
        for m in course["modules"]:
            mf = _type_dict(m, course.get("module_types", {}))
            mf["children"] = children_recursion(m)
            modules.append(mf)
    data["modules"] = modules

    data["build_log_url"] = request.build_absolute_uri(reverse("build-log-json", args=(course_key, )))
    return JsonResponse(data)


def _get_course_exercise_lang(course_key, exercise_key, lang_code):
    # Keep only "en" from "en-gb" if the long language format is used.
    if lang_code:
        lang_code = lang_code[:2]
    (course, exercise) = config.exercise_entry(course_key, exercise_key, lang=lang_code)
    if course is None or exercise is None:
        raise Http404()
    if not lang_code:
        lang_code = course.get('lang', DEFAULT_LANG)
    translation.activate(lang_code)
    return (course, exercise, lang_code)


def _filter_fields(dict_list, pick_fields):
    '''
    Filters picked fields from a list of dictionaries.

    @type dict_list: C{list}
    @param dict_list: a list of dictionaries
    @type pick_fields: C{list}
    @param pick_fields: a list of field names
    @rtype: C{list}
    @return: a list of filtered dictionaries
    '''
    result = []
    for entry in dict_list:
        new_entry = {}
        for name in pick_fields:
            new_entry[name] = entry[name]
        result.append(new_entry)
    return result


def _copy_fields(dict_item, pick_fields):
    '''
    Copies picked fields from a dictionary.

    @type dict_item: C{dict}
    @param dict_item: a dictionary
    @type pick_fields: C{list}
    @param pick_fields: a list of field names
    @rtype: C{dict}
    @return: a dictionary of picked fields
    '''
    result = {}
    for name in pick_fields:
        if name in dict_item:
            result[name] = copy.deepcopy(dict_item[name])
    return result

def _type_dict(dict_item, dict_types):
    '''
    Extends dictionary with a type reference.

    @type dict_item: C{dict}
    @param dict_item: a dictionary
    @type dict_types: C{dict}
    @param dict_types: a dictionary of type dictionaries
    @rtype: C{dict}
    @return: an extended dictionary
    '''
    base = {}
    if "type" in dict_item and dict_item["type"] in dict_types:
        base = copy.deepcopy(dict_types[dict_item["type"]])
    base.update(dict_item)
    if "type" in base:
        del base["type"]
    return base
