from enum import Enum

from aplus_auth.payload import Permission
from django.db import models
from django.http.request import HttpRequest

from util.login_required import has_access


class Course(models.Model):
    '''
    A course repository served out for learning environments.
    '''

    key = models.SlugField(unique=True)
    # course instance id on A+
    remote_id = models.IntegerField(unique=True, blank=True, null=True)
    git_origin = models.CharField(blank=True, max_length=255)
    git_branch = models.CharField(max_length=40)
    update_hook = models.URLField(blank=True)
    email_on_error = models.BooleanField(default=True)
    update_automatically = models.BooleanField(default=True)

    class META:
        ordering = ['key']

    def has_access(self, request: HttpRequest, permission: Permission, default: bool = False) -> bool:
        if self.remote_id is None:
            return default

        return has_access(request, permission, self.remote_id)

    def has_write_access(self, request: HttpRequest, default: bool = False):
        return self.has_access(request, Permission.WRITE, default)

    def has_read_access(self, request: HttpRequest, default: bool = False):
        return self.has_access(request, Permission.READ, default)


class UpdateStatus(Enum):
    PENDING="PENDING"
    RUNNING="RUNNING"
    SUCCESS="SUCCESS"
    FAILED="FAILED"
    SKIPPED="SKIPPED"


class CourseUpdate(models.Model):
    '''
    An update to course repo from the origin.
    '''
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='updates')
    request_ip = models.CharField(max_length=40)
    request_time = models.DateTimeField(auto_now_add=True)
    updated_time = models.DateTimeField(default=None, null=True, blank=True)
    status = models.CharField(max_length=10, default=UpdateStatus.PENDING, choices=[(tag, tag.value) for tag in UpdateStatus])
    log = models.TextField(default=None, null=True, blank=True)

    class META:
        ordering = ['-request_time']

