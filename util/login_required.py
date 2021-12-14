from typing import Callable

from aplus_auth import settings as auth_settings
from aplus_auth.auth.django import login_required as login_required_base
from aplus_auth.payload import Permission
from django.http import HttpRequest
from django.http.response import HttpResponseBase


ViewType = Callable[..., HttpResponseBase]
login_required: Callable[[ViewType],ViewType] = login_required_base(redirect_url="/login?referer={url}")


def has_access(request: HttpRequest, permission: Permission, instance_id: int) -> bool:
    if auth_settings().DISABLE_LOGIN_CHECKS:
        return True

    if not hasattr(request, "auth") or request.auth is None:
        return False

    # if the key is self signed and the permissions are empty, we assume it is
    # a 'master' key with access to everything
    has_empty_perms = next(iter(request.auth.permissions), None) is None
    if has_empty_perms and request.auth.iss == auth_settings().PUBLIC_KEY:
        return True

    return request.auth.permissions.instances.has(permission, id=instance_id)
