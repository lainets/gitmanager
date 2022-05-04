import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional

from aplus_auth import settings as auth_settings
from aplus_auth.auth.django import Request
from aplus_auth.payload import Permission
from django.conf import settings
from django.forms.models import model_to_dict
from django.http.request import QueryDict
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View

from util.log import SecurityLog
from util.login_required import has_access, login_required, login_required_method
from .forms import CourseForm
from .models import Course, CourseUpdate
from .builder import push_event
from .apps import ssh_key


logger = logging.getLogger("builder.views")


def try_parse_int(item: str):
    try:
        return int(item)
    except:
        return None


@login_required
def courses(request):
    courses = (course for course in Course.objects.all() if course.has_read_access(request, True))

    return render(request, 'builder/courses.html', {
        'courses': courses,
        'ssh_key': ssh_key,
    })


@login_required
def edit(request, key = None):
    if key:
        course = get_object_or_404(Course, key=key)
        if not course.has_write_access(request, True):
            return HttpResponse(status=403)

        if "regenerate_secret" in request.POST:
            SecurityLog.info(request, f"EDIT-COURSE reset_webhook_secret")
            course.reset_webhook_secret()
            course.save()

        form = CourseForm(request.POST or None, instance=course)
    else:
        course = None
        form = CourseForm(request.POST or None)
        del form.fields["webhook_secret"]

    if request.method == 'POST' and form.is_valid():
        if "remote_id" in request.POST and not has_access(request, Permission.WRITE, form.instance.remote_id):
            return HttpResponse(f"No access to instance id {request.POST['remote_id']}", status=403)

        form.save(request)

        if "regenerate_secret" not in request.POST:
            return redirect('manager-courses')

    return render(request, 'builder/edit.html', {
        'course': course,
        'form': form,
    })


class EditCourse(View):
    """
    Edit course settings, or create a new course.

    GET to get course settings.

    POST to create a course.

    PUT to edit a course.

    Returns the course settings and the git hook URL in the 'git_hook' key.
    """
    def _check_access(self, request: Request, data: QueryDict, require_remote_id: bool = True) -> Optional[HttpResponse]:
        """
        Checks that the requester has write access to the remote_id specified in the POST data.
        """
        if "remote_id" in data:
            instance_id = try_parse_int(data["remote_id"])
            if instance_id is None:
                return JsonResponse({"success": False, "error": "remote_id is not an integer"})

            if not has_access(request, Permission.WRITE, instance_id):
                return JsonResponse({"success": False, "error": f"No access to instance {instance_id}"})
        elif not auth_settings().DISABLE_LOGIN_CHECKS and require_remote_id:
            return JsonResponse({"success": False, "error": "No remote_id in POST parameters"})

        return None

    def _get(self, request: Request, course: Course) -> Dict[str, Any]:
        obj = model_to_dict(course, fields=CourseForm.Meta.fields)
        obj["git_hook"] = request.build_absolute_uri(reverse('manager-git-hook', args=[course.key]))
        if not course.has_access(request, Permission.WRITE):
            # we do not want to give a secret that allows writing to a person without write access
            del obj["webhook_secret"]
        return obj

    @login_required_method(redirect_url=None)
    def get(self, request: Request, key: Optional[str] = None, remote_id: Optional[int] = None, **kwargs) -> HttpResponse:
        if key:
            course = get_object_or_404(Course, key=key)
        else:
            course = get_object_or_404(Course, remote_id=remote_id)

        if not course.has_access(request, Permission.READ):
            return JsonResponse({"success": False, "error": f"No access to instance {course.remote_id}"})

        return JsonResponse(self._get(request, course))

    @login_required_method(redirect_url=None)
    def post(self, request: Request, key: Optional[str] = None, remote_id: Optional[int] = None, **kwargs) -> HttpResponse:
        if not request.POST:
            return JsonResponse({"success": False, "error": "No POST parameters given"})

        if key and Course.objects.filter(key=key).exists():
            return HttpResponse(f"Course with key '{key}' already exists", status=400)
        elif remote_id and Course.objects.filter(remote_id=remote_id).exists():
            return HttpResponse(f"Course with id '{remote_id}' already exists", status=400)

        response = self._check_access(request, request.POST)
        if response is not None:
            return response

        if key and request.POST.get("key") != key:
            return HttpResponse("Key in POST params does not match key in URL", status=400)
        elif remote_id and try_parse_int(request.POST.get("remote_id")) != remote_id:
            return HttpResponse("Remote id in POST params does not match id in URL", status=400)

        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(request)
            return JsonResponse(self._get(request, course))

        return JsonResponse({"success": False, "error": form.errors})

    @login_required_method(redirect_url=None)
    def put(self, request: Request, key: Optional[str] = None, remote_id: Optional[int] = None, **kwargs) -> HttpResponse:
        data = QueryDict(request.body, mutable=True)
        if not data:
            return JsonResponse({"success": False, "error": "No POST parameters given"})

        if key:
            course = get_object_or_404(Course, key=key)
        else:
            course = get_object_or_404(Course, remote_id=remote_id)
        if not course.has_access(request, Permission.WRITE):
            return JsonResponse({"success": False, "error": f"No access to instance {course.remote_id}"})

        response = self._check_access(request, data, False)
        if response is not None:
            return response

        form = CourseForm(data, instance=course)
        if form.is_valid():
            course = form.save(request)
            return JsonResponse(self._get(request, course))

        return JsonResponse({"success": False, "error": form.errors})


@login_required
def updates(request, key):
    course = get_object_or_404(Course, key=key)
    if not course.has_read_access(request, True):
        return HttpResponse(status=403)
    return render(request, 'builder/updates.html', {
        'course': course,
        'updates': course.updates.order_by('-request_time').all(),
        'hook': request.build_absolute_uri(reverse('manager-git-hook', args=[key])),
        'aplus_json_url': request.build_absolute_uri(reverse('aplus-json', args=[key])),
        'has_write_access': course.has_write_access(request, False),
    })


@login_required
def build_log_json(request, key):
    try:
        course = get_object_or_404(Course, key=key)
    except Course.DoesNotExist:
        return JsonResponse({})
    if not course.has_read_access(request, True):
        return HttpResponse(status=403)
    latest_update = course.updates.order_by("-updated_time")[0]
    return JsonResponse({
        'build_log': latest_update.log,
        'request_ip': latest_update.request_ip,
        'request_time': latest_update.request_time,
        'updated': latest_update.status != CourseUpdate.Status.PENDING,
        'updated_time': latest_update.updated_time,
        'status': latest_update.status,
    })


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def verify_hmac(received_signature, secret, body) -> bool:
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received_signature, f"sha256={signature}")

def try_verify_github(request, course: Course) -> Optional[str]:
    received_signature = request.headers.get("X-Hub-Signature-256", None)
    if not received_signature:
        return "No X-Hub-Signature-256 header"

    if not verify_hmac(received_signature, course.webhook_secret, request.body):
        return "Signatures didn't match"

    return None

def try_verify_gitlab(request, course: Course) -> Optional[str]:
    secret = request.headers.get("X-Gitlab-Token", None)
    if not secret:
        return "No X-Gitlab-Token header"

    if not hmac.compare_digest(course.webhook_secret, secret):
        return "Secrets didn't match"

    return None


def get_post_data(request) -> Optional[Dict[str, Any]]:
    json_data = ""
    if request.content_type == "application/x-www-form-urlencoded":
        json_data = request.POST.get("payload")
    else:
        json_data = request.body.decode(request.encoding or settings.DEFAULT_CHARSET)

    try:
        data = json.loads(json_data)
    except ValueError as e:
        logger.warning(f"Invalid json data or unknown content type to webhook. Error: {e}")
        return None

    return data


def hook(request: Request, key: str, **kwargs) -> HttpResponse:
    """Git hook for git services"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    course = get_object_or_404(Course, key=key)

    if course.has_access(request, Permission.WRITE):
        SecurityLog.info(request, "INITIATE-BUILD", f"{key}")
    elif request.user.is_authenticated:
        return HttpResponse(f"No access to course {key}", status=403)
    else:
        branch = None
        if request.META.get('HTTP_X_GITLAB_EVENT'):
            if course.webhook_secret is None:
                logger.warning(f"webhook secret for course '{key}' is None. Skipping secret verification.")
            else:
                error = try_verify_gitlab(request, course)
                if error:
                    logger.warning(f"Hook verification failed: {error}")
                    return HttpResponse(error, status=403)

            data = get_post_data(request)
            if data:
                branch = data.get('ref', '').rpartition("/")[2]
        elif request.META.get('HTTP_X_GITHUB_EVENT'):
            if course.webhook_secret is None:
                logger.warning(f"webhook secret for course '{key}' is None. Skipping secret verification.")
            else:
                error = try_verify_github(request, course)
                if error:
                    logger.warning(f"Hook verification failed: {error}")
                    return HttpResponse(error, status=403)

            data = get_post_data(request)
            if data:
                branch = data.get('ref', '').rpartition("/")[2]
        else:
            logger.warning(f"Unknown git service: {request.headers}\n{request.body}")
            return HttpResponse("Unknown git service", status=400)

        if branch is not None and branch != course.git_branch:
            return HttpResponse(
                f"Ignored. Update to '{branch}', but expected '{course.git_branch}'",
                status=400,
            )

        SecurityLog.info(request, "INITIATE-BUILD", f"{key} {request.headers} {request.body}")

    course.updates.create(
        course=course,
        request_ip=get_client_ip(request)
    )

    request_params = request.POST.dict()
    request_params.update(request.GET.dict())

    params = {k: request_params[k] == "on" or request_params[k] == "true" for k in ("skip_git", "skip_build", "skip_notify") if k in request_params}
    if request_params.get("build_image"):
        params["build_image"] = request_params["build_image"]
    if request_params.get("build_command"):
        params["build_command"] = request_params["build_command"]

    push_event(key, **params)

    if request.META.get('HTTP_REFERER'):
        return redirect('manager-updates', course.key)

    return HttpResponse('ok')
