import json
import logging
import os.path
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aplus_auth.auth.django import Request
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse, Http404
from django.utils import translation
from django.urls import reverse
from django.views import View

from access.config import CourseConfig
from access.course import Exercise, Chapter, Parent
from gitmanager import builder
from gitmanager.models import Course
from util import export
from util.files import FileResponse
from util.login_required import login_required


logger = logging.getLogger("gitmanager")


@login_required
def index(request):
    '''
    Signals that the grader is ready and lists available courses.
    '''
    course_configs = CourseConfig.all()
    if request.is_ajax():
        return JsonResponse({
            "ready": True,
            "courses": [{"key": c.key, "name": c.data.name} for c in course_configs]
        })
    return render(request, 'access/ready.html', {
        "courses": course_configs,
    })


@login_required
def course(request, course_key):
    '''
    Signals that the course is ready to be graded and lists available exercises.
    '''
    course_config = CourseConfig.get(course_key)
    if course_config is None:
        raise Http404()
    exercises = course_config.get_exercise_list()
    if request.is_ajax():
        return JsonResponse({
            "ready": True,
            "course_name": course_config.data.name,
            "exercises": _filter_fields(exercises, ["key", "title"]),
        })
    render_context = {
        'course': course_config.data,
        'exercises': exercises,
        'plus_config_url': request.build_absolute_uri(reverse(
            'aplus-json', args=[course_config.key])),
    }

    render_context["build_log_url"] = request.build_absolute_uri(reverse("build-log-json", args=(course_key, )))
    return render(request, 'access/course.html', render_context)


@login_required
def protected(request: Request, course_key: str, path: str):
    if os.path.normpath(path).startswith("../"):
        raise Http404()

    try:
        course: Course = Course.objects.get(key=course_key)
    except Course.DoesNotExist:
        raise Http404()

    if not course.has_read_access(request, True):
        return HttpResponse(status=403)

    config = CourseConfig.get(course_key)
    if config is None:
        raise Http404()

    static_path = config.static_path_to(path)
    if static_path is None:
        raise Http404()

    return FileResponse(CourseConfig.relative_path_to(course_key, static_path))


def serve_exercise_file(request, course_key, exercise_key, basename, dict_key, type):
    lang = request.GET.get('lang', None)
    (course, exercise, lang) = _get_course_exercise_lang(course_key, exercise_key, lang)

    if dict_key not in exercise:
        raise Http404()

    try:
        path = next((path for path in exercise[dict_key] if path.split('/')[-1] == basename))
    except StopIteration:
        raise Http404()

    try:
        with open(CourseConfig.path_to(course.key, path)) as f:
            content = f.read()
    except FileNotFoundError as error:
        raise Http404(f"{type} file missing") from error
    else:
        return HttpResponse(content, content_type='text/plain')


@login_required
def exercise_model(request, course_key, exercise_key, basename):
    '''
    Presents a model answer for an exercise.
    '''
    return serve_exercise_file(request, course_key, exercise_key, basename, "model_files", "Model")


@login_required
def exercise_template(request, course_key, exercise_key, basename):
    '''
    Presents the exercise template.
    '''
    return serve_exercise_file(request, course_key, exercise_key, basename, "template_files", "Template")


@login_required
def aplus_json(request: HttpRequest, course_key: str):
    '''
    Delivers the configuration as JSON for A+.
    '''
    errors = []

    config = CourseConfig.load_from_store(course_key)
    if config is not None:
        defaults_path = CourseConfig.store_path_to(course_key + ".defaults.json")
    else:
        config = CourseConfig.load_from_publish(course_key)
        defaults_path = CourseConfig.path_to(course_key + ".defaults.json")

    if config is None:
        try:
            Course.objects.get(key=course_key)
        except:
            raise Http404()
        else:
            return JsonResponse({
                "success": False,
                "errors": ["Course has not been (successfully) built yet"],
            })

    if Path(defaults_path).exists():
        exercise_defaults = json.load(open(defaults_path, "r"))
    else:
        errors.append("Could not find exercise defaults file. Try rebuilding the course")
        exercise_defaults = {}

    data = config.data.dict(exclude={"modules", "static_dir", "unprotected_paths"})

    # TODO: this should really be done before the course validation happens
    def children_recursion(config: CourseConfig, parent: Parent) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for o in parent.children:
            of = o.dict(exclude={"children"})
            if isinstance(o, Exercise) and o.config:
                exercise = config.exercise_config(o.key)
                data = exercise_defaults.get(o.key, {})
                data.update(export.exercise(request, config, exercise, of))
            elif isinstance(o, Chapter):
                data = export.chapter(request, config, of)
            else: # any other exercise type
                data = of
            data["children"] = children_recursion(config, o)
            result.append(data)
        return result

    modules = []
    for m in config.data.modules:
        mf = m.dict(exclude={"children"})
        mf["children"] = children_recursion(config, m)
        modules.append(mf)
    data["modules"] = modules

    data["build_log_url"] = request.build_absolute_uri(reverse("build-log-json", args=(course_key, )))
    data["errors"] = errors
    data["publish_url"] = request.build_absolute_uri(reverse("publish", args=(course_key, )))
    return JsonResponse(data, encoder=export.JSONEncoder)


@login_required
def publish(request: HttpRequest, course_key: str) -> HttpResponse:
    try:
        errors = builder.publish(course_key)
    except Exception as e:
        logger.exception(e)
        return JsonResponse({"errors": str(e), "success": False})

    # link static dir and check correctness
    prodconfig = CourseConfig.get(course_key)
    if prodconfig is None:
        err = "Failed to read config after publishing. This shouldn't happen. You can try rebuilding the course"
        logger.error(err)
        return JsonResponse({"errors": err, "success": False})

    return JsonResponse({"errors": errors, "success": True})


class LoginView(View):
    def get(self, request):
        response = render(request, 'access/login.html')
        response.delete_cookie("AuthToken")
        return response

    def post(self, request):
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return HttpResponse("Invalid token", status=401)
        else:
            response = HttpResponse()
            response.set_cookie("AuthToken", str(request.auth))
            return response


def _get_course_exercise_lang(
        course_key: str,
        exercise_key: str,
        lang_code: Optional[str]
        ) -> Tuple[CourseConfig, Dict[str, Any], str]:
    # Keep only "en" from "en-gb" if the long language format is used.
    if lang_code:
        lang_code = lang_code[:2]
    config = CourseConfig.get(course_key)
    if config is None:
        raise Http404()
    exercise = config.exercise_data(exercise_key, lang=lang_code)
    if exercise is None:
        raise Http404()
    if not lang_code:
        lang_code = config.lang
    translation.activate(lang_code)
    return (config, exercise, lang_code)


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
