from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from django.shortcuts import redirect
from django.views.generic import TemplateView


def trigger_error(request):
    division_by_zero = 1 / 0

def redirect_admin(request):
    return redirect('/') 
urlpatterns = [
    path("api/v1/", include("apps.apis.urls")),
    path("call-test/", TemplateView.as_view(template_name="call_test.html"), name="call-test"),
    path('admin/', redirect_admin), 
    path("", admin.site.urls),
    
    # Schema & Docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui",),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("sentry-debug/", trigger_error),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static") 