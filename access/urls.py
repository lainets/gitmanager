from django.conf.urls import url

from access import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^model/([\w-]+)/([\w-]+)/([\w\d\_\-\.]*)$', views.exercise_model, name='model'),
    url(r'^exercise_template/([\w-]+)/([\w-]+)/([\w\d\_\-\.]+)$', views.exercise_template, name='exercise_template'),
    url(r'^([\w-]+)/$', views.course, name='course'),
    url(r'^([\w-]+)/aplus-json$', views.aplus_json, name='aplus-json'),
    url(r'^login$', views.LoginView.as_view(), name="login"),
]
