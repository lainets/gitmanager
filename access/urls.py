from django.urls import path, register_converter

from access import views
from access.converters import BasenameConverter, ConfigSourceConverter

register_converter(BasenameConverter, "basename")
register_converter(ConfigSourceConverter, "config_source")

urlpatterns = [
    path("", views.index, name='index'),
    path(
        "model/<slug:course_key>/<slug:exercise_key>/<basename:basename>",
        views.exercise_model,
        name='model',
    ),
    path(
        "exercise_template/<slug:course_key>/<slug:exercise_key>/<basename:basename>",
        views.exercise_template,
        name='exercise_template',
    ),
    path("<slug:course_key>/", views.course, name='course'),
    path("<slug:course_key>/aplus-json", views.aplus_json, name='aplus-json'),
    path("<slug:course_key>/publish/<config_source:source>", views.publish, name="publish"),
    path("<slug:course_key>/publish/<config_source:source>/<str:version_id>", views.publish, name="publish"),
    # /protected/ is usually called after /static/ couldn't find the file
    # the assumption is that if the file is not found inside the STATIC_ROOT
    # folder, it is a protected file (or does not exist)
    path("protected/<slug:course_key>/<path:path>", views.protected, name='protected'),
    path("login", views.LoginView.as_view(), name="login"),
]
