from django.urls import path

from builder import views


urlpatterns = [
    path("", views.courses, name='manager-courses'),
    path("new/", views.edit, name='manager-edit'),
    path("<slug:key>/", views.edit, name='manager-edit'),
    path("api/<slug:key>/", views.EditCourse.as_view(), name='api-manager-edit'),
    path("<slug:key>/updates", views.updates, name='manager-updates'),
    path("<slug:key>/hook", views.git_hook, name='manager-git-hook'),
    path("<slug:key>/ui_hook", views.UI_hook, name='manager-ui-hook'),
    path("<slug:key>/build_log-json", views.build_log_json, name='build-log-json')
]
