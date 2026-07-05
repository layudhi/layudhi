from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from training.views import badge_login
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', badge_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('training.urls')),
]

if settings.DEBUG or getattr(settings, 'SERVE_MEDIA_IN_PRODUCTION', False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
