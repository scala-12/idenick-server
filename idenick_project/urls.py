from django.conf import settings
from django.conf.urls import include
from django.conf.urls import url
from django.contrib import admin
from django.urls import path, re_path
from django.views.generic import TemplateView
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v0/auth/', include('djoser.urls')),
    path('api/v0/auth/', include('djoser.urls.authtoken')),
    path('api/v0/', include('idenick_rest_api_v0.urls')),
    re_path(r'^(?!static)(.+/?)*$', TemplateView.as_view(template_name='index.html')),
    url(r'^static/(?P<path>.*)$', serve,
        {'document_root': settings.STATIC_REACT_STATIC, 'show_indexes': settings.DEBUG}),
]
