import json
import logging
from django.conf import settings
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from util.login_required import login_required
from .forms import CourseForm
from .models import Course, UpdateStatus
from .builder import push_event
from .apps import ssh_key

logger = logging.getLogger("grader.gitmanager")


@login_required
def courses(request):
    return render(request, 'gitmanager/courses.html', {
        'courses': Course.objects.all(),
        'ssh_key': ssh_key,
    })


@login_required
def edit(request, key=None):
    if key:
        course = get_object_or_404(Course, key=key)
        form = CourseForm(request.POST or None, instance=course)
    else:
        course = None
        form = CourseForm(request.POST or None)
    for name in form.fields:
        form.fields[name].widget.attrs = {'class': 'form-control'}
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('manager-courses')
    return render(request, 'gitmanager/edit.html', {
        'course': course,
        'form': form,
    })


@login_required
def updates(request, key):
    course = get_object_or_404(Course, key=key)
    return render(request, 'gitmanager/updates.html', {
        'course': course,
        'updates': course.updates.order_by('-request_time').all(),
        'hook': request.build_absolute_uri(reverse('manager-hook', args=[key])),
    })


@login_required
def build_log_json(request, key):
    try:
        course = Course.objects.get(key=key)
    except Course.DoesNotExist:
        return JsonResponse({})
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


def hook(request, key):
    course = get_object_or_404(Course, key=key)

    if request.method == 'POST':
        branch = None
        if request.META.get('HTTP_X_GITLAB_EVENT'):
            try:
                data = json.loads(request.body.decode(request.encoding or settings.DEFAULT_CHARSET))
            except ValueError as e:
                logger.warning("Invalid json data from gitlab. Error: %s", e)
                pass
            else:
                branch = data.get('ref', '')
                branch = branch[11:] if branch.startswith('refs/heads/') else None

        if branch is not None and branch != course.git_branch:
            return HttpResponse(
                "ignored. update to '{}', but expected '{}'".format(branch, course.git_branch),
                status=400,
            )

        course.updates.create(
            course=course,
            request_ip=get_client_ip(request)
        )

        push_event(key)

    if request.META.get('HTTP_REFERER'):
        return redirect('manager-updates', course.key)

    return HttpResponse('ok')
