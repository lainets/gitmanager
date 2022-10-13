import json
from json.decoder import JSONDecodeError
import logging
import os.path
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aplus_auth.auth.django import Request
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.utils import translation
from django.urls import reverse
from django.views import View

from access.config import ConfigSource, CourseConfig
from access.course import Exercise, Chapter, Parent
from access.parser import ConfigError
from builder import builder
from builder.configure import configure_graders
from builder.models import Course
from util import export
from util.files import FileLock, FileResponse
from util.log import SecurityLog
from util.login_required import login_required


logger = logging.getLogger("access.views")


@login_required
def index(request):
    '''
    Signals that Git Manager is ready and lists available courses.
    '''
    # Only show courses user has access to
    course_keys = (course.key for course in Course.objects.all() if course.has_read_access(request, True))

    course_configs, errors = CourseConfig.get_many(course_keys)

    if request.is_ajax():
        return JsonResponse({
            "ready": True,
            "courses": [{"key": c.key, "name": c.data.name} for c in course_configs]
        })
    return render(request, 'access/ready.html', {
        "courses": course_configs,
        "errors": errors,
    })


@login_required
def course(request, course_key):
    '''
    Signals that the course is ready to be graded and lists available exercises.
    '''
    course = get_object_or_404(Course, key=course_key)
    if not course.has_read_access(request, True):
        return HttpResponse(status=403)

    error = None
    course_config = None
    exercises = None
    try:
        course_config = CourseConfig.get(course_key)
    except ConfigError as e:
        error = str(e)
    else:
        if course_config is None:
            error = "Failed to load course config (has it been built and published?)"
        else:
            exercises = course_config.get_exercise_list()

    if request.is_ajax():
        if course_config is None:
            data = {
                "ready": False,
                "errors": [error],
            }
        else:
            data = {
                "ready": True,
                "course_name": course_config.data.name,
                "exercises": _filter_fields(exercises, ["key", "title"]),
            }
        return JsonResponse(data)

    render_context = {
        'course_name': course_config.course_name if course_config is not None else course_key,
        'course': course_config.data if course_config is not None else {"name": course_key},
        'exercises': exercises,
        'plus_config_url': request.build_absolute_uri(reverse(
            'aplus-json', args=[course_key])),
        'error': error,
    }

    render_context["build_log_url"] = request.build_absolute_uri(reverse("build-log-json", args=(course_key, )))
    return render(request, 'access/course.html', render_context)


@login_required
def protected(request: Request, course_key: str, path: str):
    course = get_object_or_404(Course, key=course_key)
    if not course.has_read_access(request, True):
        return HttpResponse(status=403)

    config = CourseConfig.get_or_none(course_key)
    if config is None:
        raise Http404()

    static_path = config.static_path_to(path)
    if static_path is None:
        raise Http404()

    basepath = CourseConfig.relative_path_to(course_key, config.static_path_to() or "")
    filepath = CourseConfig.relative_path_to(course_key, static_path)
    # Check that the file is within the course's static folder
    try:
        Path(filepath).relative_to(basepath)
    except:
        raise Http404()

    return FileResponse(filepath)


def serve_exercise_file(request, course_key, exercise_key, basename, dict_key, type):
    course = get_object_or_404(Course, key=course_key)
    if not course.has_read_access(request, True):
        return HttpResponse(status=403)

    lang = request.GET.get('lang', None)
    try:
        (course, exercise, lang) = _get_course_exercise_lang(course_key, exercise_key, lang)
    except ConfigError as e:
        return HttpResponse(str(e), content_type='text/plain')

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
    except OSError as error:
        logger.error(f'Error in reading the exercise model file "{path}".', exc_info=error)
        content = str(error)

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
def aplus_json(request: HttpRequest, course_key: str) -> HttpResponse:
    '''
    Delivers the configuration as JSON for A+.
    '''
    SecurityLog.info(request, "APLUS-JSON", f"{course_key}")

    errors = []

    course = get_object_or_404(Course, key=course_key)
    if not course.has_read_access(request, True):
        return HttpResponse(status=403)

    config = None
    defaults_path = ""
    if os.path.exists(CourseConfig.path_to(course_key, source=ConfigSource.STORE)):
        try:
            config = CourseConfig.get(course_key, source=ConfigSource.STORE)
        except ConfigError as e:
            errors.append(f"Failed to load newly built course due to this error: {e}")
            errors.append("Attempting to load previous version of the course...")
            logger.warn(f"Failed to load newly built course due to this error: {e}")
        else:
            defaults_path = CourseConfig.defaults_path(course_key, source=ConfigSource.STORE)

    if config is None:
        try:
            config = CourseConfig.get(course_key, source=ConfigSource.PUBLISH)
        except ConfigError as e:
            logger.error(f"aplus_json: failed to get config for {course_key}")
            try:
                Course.objects.get(key=course_key)
            except:
                raise Http404()
            else:
                return JsonResponse({
                    "success": False,
                    "errors": errors + [f"Failed to load course (has it been built?) due to this error: {e}"],
                })

        defaults_path = CourseConfig.defaults_path(course_key, source=ConfigSource.PUBLISH)

    # configure graders if it was skipped during the build
    if course.skip_build_failsafes:
        # send configs to graders' stores
        exercise_defaults, errors = configure_graders(config)
        if errors:
            logger.exception(errors)
            return JsonResponse({"errors": errors, "success": False})

        path, defaults_path, _ = CourseConfig.file_paths(course_key, source=ConfigSource.PUBLISH)

        with FileLock(path):
            with open(defaults_path, "w") as f:
                json.dump(exercise_defaults, f)
    
    if Path(defaults_path).exists():
        try:
            exercise_defaults = json.load(open(defaults_path, "r"))
        except (JSONDecodeError, OSError) as e:
            return JsonResponse({
                "success": False,
                "errors": errors + ["Failed to load course exercise defaults JSON: " + str(e)],
            })
    else:
        errors.append("Could not find exercise defaults file. Try rebuilding the course")
        exercise_defaults = {}

    data = config.data.dict(exclude={"modules", "static_dir", "unprotected_paths"}, by_alias=True)

    # TODO: this should really be done before the course validation happens
    def children_recursion(config: CourseConfig, parent: Parent) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for o in parent.children:
            of = o.dict(exclude={"children"}, by_alias=True)
            if isinstance(o, Exercise) and o.config:
                try:
                    exercise = config.exercise_config(o.key)
                except ConfigError as e:
                    errors.append(str(e))
                    continue
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
        mf = m.dict(exclude={"children"}, by_alias=True)
        mf["children"] = children_recursion(config, m)
        modules.append(mf)
    data["modules"] = modules

    data["build_log_url"] = request.build_absolute_uri(reverse("build-log-json", args=(course_key, )))
    data["errors"] = errors
    data["publish_url"] = request.build_absolute_uri(reverse("publish", args=(course_key, )))
    return JsonResponse(data, encoder=export.JSONEncoder)


@login_required
def publish(request: HttpRequest, course_key: str) -> HttpResponse:
    SecurityLog.info(request, "PUBLISH", f"{course_key}")

    course = get_object_or_404(Course, key=course_key)
    if not course.has_write_access(request, True):
        return HttpResponse(status=403)

    try:
        errors = builder.publish(course_key)
    except Exception as e:
        logger.exception(e)
        return JsonResponse({"errors": str(e), "success": False})

    # link static dir and check correctness
    prodconfig = CourseConfig.get_or_none(course_key)
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
            # secure=not settings.DEBUG so that we do not need https when developing
            response.set_cookie("AuthToken", str(request.auth), secure=not settings.DEBUG, httponly=True)
            return response


def _get_course_exercise_lang(
        course_key: str,
        exercise_key: str,
        lang_code: Optional[str]
        ) -> Tuple[CourseConfig, Dict[str, Any], str]:
    # Keep only "en" from "en-gb" if the long language format is used.
    if lang_code:
        lang_code = lang_code[:2]
    config = CourseConfig.get_or_none(course_key)
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
