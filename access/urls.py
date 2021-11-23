from django.conf.urls import url

from access import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^model/([\w-]+)/([\w-]+)/([\w\d\_\-\.]*)$', views.exercise_model, name='model'),
    url(r'^exercise_template/([\w-]+)/([\w-]+)/([\w\d\_\-\.]+)$', views.exercise_template, name='exercise_template'),
    url(r'^([\w-]+)/$', views.course, name='course'),
    url(r'^([\w-]+)/aplus-json$', views.aplus_json, name='aplus-json'),
    url(r'^([\w-]+)/publish$', views.publish, name="publish"),
    # /protected/ is usually called after /static/ couldn't find the file
    # the assumption is that if the file is not found inside the STATIC_ROOT
    # folder, it is a protected file (or does not exist)
    url(rf'^protected/([\w-]+)/(.+)$', views.protected, name='protected'),
    url(r'^login$', views.LoginView.as_view(), name="login"),
]
