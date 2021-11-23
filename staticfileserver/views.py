from django.conf import settings
from django.contrib.staticfiles.views import serve as serve_apps
from django.http import Http404
from django.urls.base import resolve
from django.views.static import serve as serve_static


def serve(request, path):
    try:
        return serve_static(request, path, document_root=settings.STATIC_ROOT)
    except Http404:
        try:
            return serve_apps(request, path, insecure=True)
        except Http404:
            try:
                view, args, kwargs = resolve("/protected/"+path)
            except:
                raise Http404()

            return view(request, *args, *kwargs)
