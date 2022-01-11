from functools import partial, wraps
from typing import Callable
import urllib.parse

from aplus_auth import settings as auth_settings
from aplus_auth.auth.django import login_required as login_required_base
from aplus_auth.payload import Permission
from django.http import HttpRequest
from django.http.response import HttpResponse, HttpResponseBase, HttpResponseRedirect

login_redirect_url = "/login?referer={url}"

ViewType = Callable[..., HttpResponseBase]
login_required: Callable[[ViewType],ViewType] = login_required_base(redirect_url=login_redirect_url)


def login_required_method(func: ViewType = None, *, redirect_url=login_redirect_url, status=401) -> ViewType:
    if func is None:
        return partial(login_required_method, redirect_url=redirect_url, status=status)

    @wraps(func)
    def wrapper(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        nonlocal redirect_url, func
        if (not hasattr(request, "user") or not request.user.is_authenticated) and not auth_settings().DISABLE_LOGIN_CHECKS:
            if redirect_url:
                url = redirect_url.format(url=urllib.parse.quote_plus(request.path))
                return HttpResponseRedirect(url)
            else:
                return HttpResponse(status=status)
        return func(self, request, *args, **kwargs)
    return wrapper


def has_access(request: HttpRequest, permission: Permission, instance_id: int) -> bool:
    if auth_settings().DISABLE_LOGIN_CHECKS:
        return True

    if not hasattr(request, "auth") or request.auth is None:
        return False

    # if the key is self signed and the permissions are empty, we assume it is
    # a 'master' key with access to everything
    has_empty_perms = next(iter(request.auth.permissions), None) is None
    if has_empty_perms and request.auth.iss == auth_settings().UID:
        return True

    return request.auth.permissions.instances.has(permission, id=instance_id)
