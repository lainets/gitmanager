import json
from json.decoder import JSONDecodeError
import logging
from pathlib import Path
from tempfile import TemporaryFile
from typing import Any, Dict, List, Optional, Tuple
from zipfile import ZipFile

from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render
from django.http.response import HttpResponse, JsonResponse, Http404
from django.utils import translation
from django.urls import reverse
from django.views import View
from pydantic import AnyHttpUrl
from aplus_auth.payload import Permission, Permissions
from aplus_auth.requests import post
from requests_toolbelt.multipart.encoder import MultipartEncoder

from access.config import CourseConfig
from access.course import Exercise, Chapter, Parent
from gitmanager.models import Course
from util import export
from util.files import zip_path
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


class JSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, AnyHttpUrl):
            return str(obj)
        return super().default(obj)


@login_required
def aplus_json(request, course_key: str):
    '''
    Delivers the configuration as JSON for A+.
    '''
    config = CourseConfig.get(course_key)
    if config is None:
        raise Http404()

    configures: Dict[str, List[Exercise]] = {}
    for exercise in config.exercises.values():
        conf = exercise.configure
        if not conf:
            continue
        url = conf.url
        if url not in configures:
            configures[url] = []
        configures[url].append(exercise)

    course_id: int = Course.objects.get(key=course_key).remote_id

    if course_id is None and configures:
        return HttpResponse("Remote id not set: cannot configure", status=500)

    exercise_defaults: Dict[str, Any] = {}
    errors = []
    for url, exercises in configures.items():

        tmp_file = TemporaryFile(mode="w+b")
        # no compression, only pack the files into a single package
        ziph = ZipFile(tmp_file, "w")

        logger.debug(f"Compressing for {url}")
        exercise_data: List[Dict[str, Any]] = []
        for exercise in exercises:
            exercise_data.append({
                "key": exercise.key,
                "config": exercise._config_obj.data if exercise._config_obj else None,
                "files": list(exercise.configure.files.keys()),
            })
            for name, path in exercise.configure.files.items():
                zip_path(ziph, Path(config.dir, path), name)

        ziph.close()
        tmp_file.seek(0)

        permissions = Permissions()
        permissions.instances.add(Permission.WRITE, id=course_id)

        data = MultipartEncoder({
            "course_id": str(course_id),
            "course_key": course_key,
            "exercises": json.dumps(exercise_data),
            "files": ("files", tmp_file, "application/octet-stream"),
        })
        logger.debug(f"Sending to {url}")
        try:
            headers = {"Prefer": "respond-async", "Content-Type": data.content_type}
            response = post(url, headers=headers, data=data, permissions=permissions)
        except Exception as e:
            logger.warn(f"Failed to configure: {e}")
            errors.append({"url": url, "error": f"Couldn't access {url}"})
        else:
            if response.status_code != 200 or not response.text:
                logger.warn(f"Failed to configure {url}: {response.status_code}\nResponse: {response.text}")
                errors.append({"url": url, "code": response.status_code, "error": response.text})
            else:
                try:
                    logger.debug(f"Loading from {url}")
                    defaults = json.loads(response.text)
                except JSONDecodeError as e:
                    logger.info(f"Couldn't load configure response:\n{e}")
                    logger.debug(f"{url} returned {response.text}")
                    errors.append({"url": url, "error": str(e)})
                else:
                    exercise_defaults = {
                        exercise.key: defaults[exercise.key]
                        for exercise in exercises
                        if exercise.key in defaults
                    }

    data = config.data.dict(exclude={"modules", "static_dir"})

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
    return JsonResponse(data, encoder=JSONEncoder)


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
