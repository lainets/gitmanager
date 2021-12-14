from django.conf.urls import url

from gitmanager import views


urlpatterns = [
    url(r'^$', views.courses, name='manager-courses'),
    url(r'^new/$', views.edit, name='manager-edit'),
    url(r'^([\w-]+)/$', views.edit, name='manager-edit'),
    url(r'^api/([\w-]+)/$', views.EditCourse.as_view(), name='api-manager-edit'),
    url(r'^([\w-]+)/updates$', views.updates, name='manager-updates'),
    url(r'^([\w-]+)/hook$', views.git_hook, name='manager-git-hook'),
    url(r'^([\w-]+)/ui_hook$', views.UI_hook, name='manager-ui-hook'),
    url(r'^([\w-]+)/build_log-json$', views.build_log_json, name='build-log-json')
]
