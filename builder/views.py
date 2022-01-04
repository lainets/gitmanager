import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional

from aplus_auth.auth.django import Request
from aplus_auth.payload import Permission
from django.conf import settings
from django.forms.models import model_to_dict
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View

from util.login_required import has_access, login_required
from .forms import CourseForm
from .models import Course, UpdateStatus
from .builder import push_event
from .apps import ssh_key


logger = logging.getLogger("builder.views")


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
        form = CourseForm(request.POST or None, instance=course)
    else:
        course = None
        form = CourseForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        if "remote_id" in request.POST and not has_access(request, Permission.WRITE, form.instance.remote_id):
            return HttpResponse(f"No access to instance id {request.POST['remote_id']}", status=403)
        form.save()
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
    def _check_access(self,
            request: Request,
            course: Optional[Course] = None,
            permission: Permission = Permission.WRITE
            ) -> Optional[HttpResponse]:

        if course is not None and course.has_access(request, permission):
            return JsonResponse({"success": False, "error": f"No access to instance {course.remote_id}"})

        if not settings.APLUS_AUTH["DISABLE_LOGIN_CHECKS"]:
            if "remote_id" not in request.POST:
                return JsonResponse({"success": False, "error": "No remote_id in POST parameters"})

            try:
                instance_id = int(request.POST["remote_id"])
            except:
                return JsonResponse({"success": False, "error": "remote_id is not an integer"})

            if request.auth is None:
                return JsonResponse({"success": False, "error": "No JWT payload"})

            if not has_access(request, permission, instance_id):
                return JsonResponse({"success": False, "error": f"No access to instance {instance_id}"})

        return None

    def _get(self, request: Request, course: Course) -> Dict[str, Any]:
        obj = model_to_dict(course, fields=CourseForm.Meta.fields)
        obj["git_hook"] = request.build_absolute_uri(reverse('manager-git-hook', args=[course.key]))
        return obj

    @login_required
    def get(self, request: Request, key: str, **kwargs) -> HttpResponse:
        course = get_object_or_404(Course, key=key)

        response = self._check_access(request, None, Permission.READ)
        if response is not None:
            return response

        return JsonResponse(self._get(request, course))

    @login_required
    def post(self, request: Request, key: str, **kwargs) -> HttpResponse:
        if not request.POST:
            return JsonResponse({"success": False, "error": "No POST parameters given"})

        if Course.objects.exists(key=key):
            return HttpResponse(status=403)

        response = self._check_access(request)
        if response is not None:
            return response

        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save()
            return JsonResponse(self._get(request, course))

        return JsonResponse({"success": False, "error": form.errors})

    @login_required
    def put(self, request: Request, key: str, **kwargs) -> HttpResponse:
        if not request.POST:
            return JsonResponse({"success": False, "error": "No POST parameters given"})

        course = get_object_or_404(Course, key=key)

        response = self._check_access(request, course)
        if response is not None:
            return response

        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            course = form.save()
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
        'updated': latest_update.status != UpdateStatus.PENDING,
        'updated_time': latest_update.updated_time,
        'status': latest_update.status,
    })


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def hook(request, key: str, course: Course) -> None:
    """Extracts GET/POST params and calls push_event"""
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


@login_required
def UI_hook(request, key: str) -> HttpResponse:
    """Trigger build in UI"""
    course = get_object_or_404(Course, key=key)

    if not course.has_access(request, Permission.WRITE):
        return HttpResponse(f"No access to course {key}", status=403)

    if request.method == 'POST':
        hook(request, key, course)

    if request.META.get('HTTP_REFERER'):
        return redirect('manager-updates', course.key)

    return HttpResponse('ok')


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


def git_hook(request, key: str) -> HttpResponse:
    """Git hook for git services"""
    course = get_object_or_404(Course, key=key)

    if request.method == 'POST':
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

        hook(request, key, course)

    return HttpResponse('ok')
