from django.conf.urls import include
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v0/auth/', include('djoser.urls')),
    path('api/v0/auth/', include('djoser.urls.authtoken')),
    path('api/v0/', include('idenick_rest_api_v0.urls')),
    re_path(r'^(.+/)*$', TemplateView.as_view(template_name='index.html')),
]

urlpatterns += staticfiles_urlpatterns()
